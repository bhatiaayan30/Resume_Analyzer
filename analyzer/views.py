"""
views.py — HTTP request handlers.

Rule: keep views thin. Validation lives here; all business
logic (text extraction, AI calls) lives in utils.py so it
can be unit-tested without an HTTP request.
"""

import os

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.conf import settings

from .models import ResumeAnalysis, UserProfile
from .utils import analyze_with_ai, extract_text, generate_cover_letter
from django_q.tasks import async_task
from .tasks import process_resume_analysis

stripe.api_key = settings.STRIPE_SECRET_KEY


def index(request):
    """Serve the upload form (Step 1) or landing page."""
    if request.user.is_authenticated:
        return render(request, "analyzer/index.html")
    return render(request, "analyzer/landing.html")


@require_http_methods(["POST"])
def analyze(request):
    """
    Accept a resume file (PDF/DOCX) and job description text.
    Returns a rendered results page with the AI analysis.

    Status codes used:
        400 → bad input (missing fields, wrong file type, file too large)
        422 → file uploaded but text extraction failed (e.g. scanned PDF)
        503 → AI API call failed or timed out
    """
    resume_file = request.FILES.get("resume")
    job_desc = request.POST.get("job_description", "").strip()

    # Helper to render errors back as JSON
    def render_error(error_msg, status_code):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return JsonResponse({"status": "error", "message": error_msg}, status=status_code)
        return render(request, "analyzer/index.html", {"error": error_msg}, status=status_code)

    # ── 0. Freemium Limits ─────────────────────────────────────
    if not request.user.is_authenticated:
        scan_count = request.session.get('scan_count', 0)
        if scan_count >= 1:
            return render_error("You have reached your limit of 1 free scan. Please log in to continue.", 403)
        request.session['scan_count'] = scan_count + 1
    else:
        profile = request.user.profile
        tier = profile.subscription_tier
        if tier == 4:
            limit = float('inf')
        elif tier == 3:
            limit = 100
        elif tier == 2:
            limit = 50
        elif tier == 1:
            limit = 20
        else:
            limit = 2

        if profile.current_period_start:
            used_scans = ResumeAnalysis.objects.filter(user=request.user, created_at__gte=profile.current_period_start).count()
        else:
            used_scans = ResumeAnalysis.objects.filter(user=request.user).count()

        if used_scans >= limit:
            return render_error("You have reached your scan limit. Please upgrade your plan to continue.", 403)

    # ── 1. Validate presence ───────────────────────────────────
    if not resume_file or not job_desc:
        return render_error("Both a resume file and a job description are required.", 400)

    # ── 2. Validate file type (Extension & Magic Numbers) ──────
    ext = os.path.splitext(resume_file.name)[1].lower()
    if ext not in [".pdf", ".docx"]:
        return render_error(f'Unsupported file type "{ext}". Please upload a PDF or DOCX.', 400)

    header = resume_file.read(10)
    resume_file.seek(0)

    if ext == ".pdf" and not header.startswith(b"%PDF-"):
        return render_error("Invalid PDF file. The file appears to be corrupted or spoofed.", 400)
    if ext == ".docx" and not header.startswith(b"PK\x03\x04"):
        return render_error("Invalid DOCX file. The file appears to be corrupted or spoofed.", 400)

    # ── 3. Validate file size (2 MB cap) ──────────────────────
    if resume_file.size > 2 * 1024 * 1024:
        return render_error("File too large. Maximum size is 2 MB.", 400)

    # ── 4. Extract text ────────────────────────────────────────
    try:
        resume_text, ats_format_issues = extract_text(resume_file, ext)
    except ValueError as exc:
        return render_error(str(exc), 422)

    # ── 5. Create Pending Record ────────────────────────────────
    analysis_record = ResumeAnalysis.objects.create(
        user=request.user if request.user.is_authenticated else None,
        filename=resume_file.name,
        resume_text=resume_text,
        job_desc_full=job_desc,
        job_desc_snippet=job_desc[:120],
        status='pending',
        ats_format_issues=ats_format_issues
    )

    # ── 6. Queue Async Task ─────────────────────────────────────
    async_task(process_resume_analysis, analysis_record.id)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({"status": "success", "analysis_id": analysis_record.id})
    else:
        # Fallback for non-JS
        return redirect('analysis_results', analysis_id=analysis_record.id)


def analysis_status(request, analysis_id):
    """API endpoint to poll the status of an async analysis."""
    record = get_object_or_404(ResumeAnalysis, id=analysis_id)
    if record.user and request.user != record.user:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)
    return JsonResponse({"status": record.status})


def analysis_results(request, analysis_id):
    """Serve the results page for a completed analysis."""
    record = get_object_or_404(ResumeAnalysis, id=analysis_id)
    if record.user and request.user != record.user:
        return redirect('index')
    
    if record.status == 'error':
        return render(request, "analyzer/index.html", {"error": "AI analysis failed during background processing. Please try again."})
        
    return render(
        request,
        "analyzer/results.html",
        {
            "analysis": record,
            "job_desc_snippet": record.job_desc_snippet,
            "filename": record.filename,
        },
    )


@login_required
def history(request):
    """Serve the history of past analyses."""
    analyses = ResumeAnalysis.objects.filter(user=request.user)
    return render(request, "analyzer/history.html", {"analyses": analyses})


def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                from django.db import IntegrityError

                user = form.save()
                login(request, user)
                return redirect("index")
            except IntegrityError:
                form.add_error("username", "An account with that username already exists.")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def generate_cover_letter_api(request, analysis_id):
    """API endpoint for the React component to generate a cover letter asynchronously."""
    if not request.user.profile.is_premium:
        return JsonResponse({"error": "Premium subscription required to generate cover letters."}, status=403)

    record = get_object_or_404(ResumeAnalysis, id=analysis_id, user=request.user)

    if record.cover_letter:
        return JsonResponse({"cover_letter": record.cover_letter})

    try:
        letter = generate_cover_letter(record.resume_text, record.job_desc_full)
        record.cover_letter = letter
        record.save()
        return JsonResponse({"cover_letter": letter})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
def export_cover_letter_pdf(request, analysis_id):
    """Generates a PDF of the cover letter and returns it as a download."""
    record = get_object_or_404(ResumeAnalysis, id=analysis_id, user=request.user)

    if not record.cover_letter:
        return HttpResponse("Cover letter not generated yet.", status=400)

    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18
    )
    styles = getSampleStyleSheet()
    Story = []

    text = record.cover_letter.replace("\n", "<br />")
    Story.append(Paragraph(text, styles["Normal"]))

    doc.build(Story)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Cover_Letter_{record.id}.pdf"'
    return response


# ── Stripe Payments ────────────────────────────────────────────

def pricing_view(request):
    """Serve the pricing / upgrade page."""
    return render(request, "analyzer/pricing.html", {
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY
    })

@login_required
def create_checkout_session(request):
    """Initiates a Stripe Checkout session."""
    price_id = request.GET.get('price_id', settings.STRIPE_PRICE_ID_49)
    try:
        checkout_session = stripe.checkout.Session.create(
            customer=request.user.profile.stripe_customer_id if request.user.profile.stripe_customer_id else None,
            customer_email=request.user.email if not request.user.profile.stripe_customer_id else None,
            payment_method_types=['card'],
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=request.build_absolute_uri('/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/pricing/'),
            client_reference_id=request.user.id,
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return render(request, "analyzer/pricing.html", {"error": str(e)})

@login_required
def create_portal_session(request):
    """Initiates a Stripe Customer Portal session."""
    try:
        portalSession = stripe.billing_portal.Session.create(
            customer=request.user.profile.stripe_customer_id,
            return_url=request.build_absolute_uri('/'),
        )
        return redirect(portalSession.url, code=303)
    except Exception as e:
        return render(request, "analyzer/index.html", {"error": str(e)})

@csrf_exempt
def stripe_webhook(request):
    """Handles Stripe Webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        if user_id:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=user_id)
                profile = user.profile
                profile.stripe_customer_id = session.get('customer')
                sub_id = session.get('subscription')
                profile.stripe_subscription_id = sub_id
                profile.is_premium = True

                sub = stripe.Subscription.retrieve(sub_id)
                price_id = sub.plan.id
                if price_id == settings.STRIPE_PRICE_ID_999:
                    profile.subscription_tier = 4
                elif price_id == settings.STRIPE_PRICE_ID_299:
                    profile.subscription_tier = 3
                elif price_id == settings.STRIPE_PRICE_ID_149:
                    profile.subscription_tier = 2
                elif price_id == settings.STRIPE_PRICE_ID_49:
                    profile.subscription_tier = 1
                else:
                    profile.subscription_tier = 1
                    
                import datetime
                profile.current_period_start = datetime.datetime.fromtimestamp(sub.current_period_start, tz=datetime.timezone.utc)
                profile.current_period_end = datetime.datetime.fromtimestamp(sub.current_period_end, tz=datetime.timezone.utc)

                profile.save()
            except User.DoesNotExist:
                pass

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        try:
            profile = UserProfile.objects.get(stripe_subscription_id=subscription.get('id'))
            profile.is_premium = False
            profile.subscription_tier = 0
            profile.save()
        except UserProfile.DoesNotExist:
            pass
            
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        try:
            profile = UserProfile.objects.get(stripe_subscription_id=subscription.get('id'))
            if subscription.get('status') in ['active', 'trialing']:
                profile.is_premium = True
                price_id = subscription.get('plan').get('id')
                if price_id == settings.STRIPE_PRICE_ID_999:
                    profile.subscription_tier = 4
                elif price_id == settings.STRIPE_PRICE_ID_299:
                    profile.subscription_tier = 3
                elif price_id == settings.STRIPE_PRICE_ID_149:
                    profile.subscription_tier = 2
                elif price_id == settings.STRIPE_PRICE_ID_49:
                    profile.subscription_tier = 1
                    
                import datetime
                profile.current_period_start = datetime.datetime.fromtimestamp(subscription.get('current_period_start'), tz=datetime.timezone.utc)
                profile.current_period_end = datetime.datetime.fromtimestamp(subscription.get('current_period_end'), tz=datetime.timezone.utc)
            else:
                profile.is_premium = False
                profile.subscription_tier = 0
            profile.save()
        except UserProfile.DoesNotExist:
            pass

    return HttpResponse(status=200)
