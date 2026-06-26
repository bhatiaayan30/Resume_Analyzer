"""
views.py — HTTP request handlers.

Rule: keep views thin. Validation lives here; all business
logic (text extraction, AI calls) lives in utils.py so it
can be unit-tested without an HTTP request.
"""

import json
import os

# Monkey-patch reportlab to allow xhtml2pdf to import ShowBoundaryValue on newer reportlab versions
try:
    import reportlab.platypus.frames
    if not hasattr(reportlab.platypus.frames, 'ShowBoundaryValue'):
        from reportlab.pdfgen.canvas import ShowBoundaryValue
        reportlab.platypus.frames.ShowBoundaryValue = ShowBoundaryValue
except ImportError:
    pass

from collections import Counter

import razorpay
from django import forms
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .ats_knowledge import ATS_FLAG_EXPLANATIONS
from .models import Coupon, JobDescription, OTP, Persona, ResumeAnalysis, ResumeVersion, UserProfile, InterviewSession, InterviewMessage, LocalizedResume
from .tasks import process_resume_analysis
from .utils import (
    analyze_with_ai, extract_text, generate_cover_letter, generate_otp, send_email_otp, send_sms_otp,
    suggest_bullet_rewrites, generate_next_interview_question, evaluate_interview_answer, parse_resume_to_json,
    get_ai_summary_suggestions, get_ai_experience_bullets, localize_resume_data
)

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def index(request):
    """Serve the upload form (Step 1) or landing page."""
    if request.user.is_authenticated:
        recent_scans = ResumeAnalysis.objects.filter(user=request.user).order_by('created_at')
        return render(request, "analyzer/index.html", {"recent_scans": recent_scans})
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
        from django.core.cache import cache
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        cache_key = f"guest_scan_{ip}"
        scan_count = cache.get(cache_key, request.session.get('scan_count', 0))
        
        if scan_count >= 1:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
                return JsonResponse({"status": "limit_reached", "reason": "unauthenticated"}, status=403)
            return redirect('account_login')
            
        request.session['scan_count'] = scan_count + 1
        cache.set(cache_key, scan_count + 1, timeout=86400 * 30) # 30 days
    else:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
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
            from django.utils import timezone
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            used_scans = ResumeAnalysis.objects.filter(user=request.user, created_at__gte=thirty_days_ago).count()

        if used_scans >= limit:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
                return JsonResponse({"status": "limit_reached", "reason": "upgrade_required"}, status=403)
            return redirect('pricing')

    # ── 1. Validate presence ───────────────────────────────────
    resume_input_type = request.POST.get("resume_input_type", "file")
    resume_text_input = request.POST.get("resume_text", "").strip()

    if not job_desc:
        return render_error("A job description is required.", 400)

    if resume_input_type == "file":
        if not resume_file:
            return render_error("A resume file is required.", 400)

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
            from .utils import check_searchability
            resume_text, ats_format_issues, searchability_checks = extract_text(resume_file, ext)
        except ValueError as exc:
            return render_error(str(exc), 422)
            
        filename = resume_file.name
    elif resume_input_type == "image":
        resume_image = request.FILES.get("resume_image")
        if not resume_image:
            return render_error("A resume photo is required.", 400)

        # ── 3. Validate file size (10 MB cap for images) ──────────
        if resume_image.size > 10 * 1024 * 1024:
            return render_error("Image too large. Maximum size is 10 MB.", 400)

        # ── 4. Extract text via OCR ────────────────────────────────
        try:
            from .utils import extract_text_from_image, check_searchability
            image_bytes = resume_image.read()
            mime_type = resume_image.content_type or "image/jpeg"
            resume_text = extract_text_from_image(image_bytes, mime_type)
            ats_format_issues = ["image_upload"] # Indicates formatting could not be fully parsed
            searchability_checks = check_searchability(resume_text)
            filename = resume_image.name
        except Exception as exc:
            return render_error(str(exc), 422)
    elif resume_input_type == "cloud":
        if not resume_text_input:
            return render_error("Cloud resume data is required.", 400)
            
        resume_text = resume_text_input
        ats_format_issues = []
        from .utils import check_searchability
        searchability_checks = check_searchability(resume_text)
        filename = request.POST.get("cloud_filename", "").strip() or "Cloud Import"
    else:
        if not resume_text_input:
            return render_error("Resume text is required.", 400)
            
        resume_text = resume_text_input
        ats_format_issues = []
        from .utils import check_searchability
        searchability_checks = check_searchability(resume_text)
        filename = "Pasted Text"

    # ── 5. Create Pending Record ────────────────────────────────
    analysis_record = ResumeAnalysis.objects.create(
        user=request.user if request.user.is_authenticated else None,
        filename=filename,
        resume_text=resume_text,
        job_desc_full=job_desc,
        job_desc_snippet=job_desc[:120],
        status='pending',
        ats_format_issues=ats_format_issues,
        searchability_checks=searchability_checks
    )

    # ── 6. Process Synchronously for Vercel ─────────────────────
    process_resume_analysis(str(analysis_record.slug))

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({"status": "success", "analysis_id": str(analysis_record.slug)})
    else:
        # Fallback for non-JS
        return redirect('analysis_results', analysis_id=str(analysis_record.slug))


def analysis_status(request, analysis_id):
    """API endpoint to poll the status of an async analysis."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    if record.user and request.user != record.user:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)
    return JsonResponse({"status": record.status})


def analysis_results(request, analysis_id):
    """Serve the results page for a completed analysis."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    if record.user and request.user != record.user:
        return redirect('index')
    
    if record.status == 'error':
        return render(request, "analyzer/index.html", {"error": "AI analysis failed during background processing. Please try again."})

    # Enrich ATS format issues
    enriched_issues = []
    for issue_key in record.ats_format_issues:
        enriched_issues.append({
            "key": issue_key,
            "explanation": ATS_FLAG_EXPLANATIONS.get(issue_key, str(issue_key))
        })

    # Separate Hard and Soft Skills
    hard_matched = [s for s in record.matched_skills if isinstance(s, dict) and s.get('category', '').lower() == 'hard']
    soft_matched = [s for s in record.matched_skills if isinstance(s, dict) and s.get('category', '').lower() == 'soft']
    hard_missing = [s for s in record.missing_skills if isinstance(s, dict) and s.get('category', '').lower() == 'hard']
    soft_missing = [s for s in record.missing_skills if isinstance(s, dict) and s.get('category', '').lower() == 'soft']
    
    # Legacy fallback for old records
    if record.matched_skills and isinstance(record.matched_skills[0], str):
        hard_matched = [{"skill": s, "category": "hard"} for s in record.matched_skills]
    if record.missing_skills and isinstance(record.missing_skills[0], str):
        hard_missing = [{"skill": s, "category": "hard"} for s in record.missing_skills]

    # Before/After Diff Logic
    diff_data = None
    if record.user:
        # Find previous scan with same job desc snippet (proxy for same JD) for this user
        prev_scan = ResumeAnalysis.objects.filter(
            user=record.user,
            job_desc_snippet=record.job_desc_snippet,
            created_at__lt=record.created_at,
            status='completed'
        ).order_by('-created_at').first()

        if prev_scan:
            score_delta = record.match_score - prev_scan.match_score
            
            # Extract simple lists of skills for diffing
            def extract_skills(skill_list):
                if not skill_list: return set()
                if isinstance(skill_list[0], dict):
                    return {s.get('skill', '') for s in skill_list}
                return set(skill_list)

            curr_matched = extract_skills(record.matched_skills)
            prev_matched = extract_skills(prev_scan.matched_skills)
            newly_matched = curr_matched - prev_matched
            
            prev_flags = set(prev_scan.ats_format_issues)
            curr_flags = set(record.ats_format_issues)
            resolved_flags = prev_flags - curr_flags

            diff_data = {
                "score_delta": score_delta,
                "newly_matched_count": len(newly_matched),
                "newly_matched": list(newly_matched),
                "resolved_flags_count": len(resolved_flags),
            }

    return render(
        request,
        "analyzer/results.html",
        {
            "analysis": record,
            "job_desc_snippet": record.job_desc_snippet,
            "filename": record.filename,
            "ats_format_issues_enriched": enriched_issues,
            "hard_matched": hard_matched,
            "soft_matched": soft_matched,
            "hard_missing": hard_missing,
            "soft_missing": soft_missing,
            "diff_data": diff_data,
            "perms": get_premium_permissions(request.user, record),
        },
    )


def get_premium_permissions(user, record):
    """
    Returns a dictionary of permissions for the given user and analysis record.
    Accepts a ResumeAnalysis instance directly to avoid redundant DB queries.
    """
    perms = {
        "can_cover_letter": False,
        "can_interview": False,
        "can_critique": False,
        "can_download_pdf": False,
        "can_audit": False,
        "record": record,
    }

    # Helper to unlock all features
    def unlock_all():
        perms["can_cover_letter"] = True
        perms["can_interview"] = True
        perms["can_critique"] = True
        perms["can_download_pdf"] = True
        perms["can_audit"] = True

    # 1. Unauthenticated user checking their one-time free scan
    if not user.is_authenticated:
        if record.user is None:
            unlock_all()
        return perms

    # 2. Authenticated user trying to access someone else's record
    if record.user and user != record.user:
        return perms
        
    # 3. Check if this is the user's first scan (One Time Free)
    first_scan = ResumeAnalysis.objects.filter(user=user).order_by('created_at').first()
    if first_scan and first_scan.id == record.id:
        unlock_all()
        return perms
        
    # 4. Check regular premium status
    if hasattr(user, 'profile') and user.profile.is_premium:
        tier = user.profile.subscription_tier
        if tier >= 2: # Pro, Elite, Unlimited
            perms["can_cover_letter"] = True
            perms["can_interview"] = True
            perms["can_download_pdf"] = True
            perms["can_audit"] = True
        if tier >= 3: # Elite, Unlimited
            perms["can_critique"] = True
            
    return perms


@login_required
def history(request):
    """
    Renders the history of past analyses for the logged-in user.
    Includes chronological data for the user's progress tracking line chart.
    """
    analyses = ResumeAnalysis.objects.filter(user=request.user).order_by("-created_at")
    
    # Chronological completed scans for the evolution chart
    chart_analyses = ResumeAnalysis.objects.filter(user=request.user, status='completed').order_by('created_at')
    
    chart_dates = [a.created_at.strftime('%m/%d') for a in chart_analyses]
    chart_scores = [a.match_score for a in chart_analyses]
    
    context = {
        "analyses": analyses,
        "chart_dates_json": chart_dates,
        "chart_scores_json": chart_scores,
        "has_chart_data": len(chart_scores) >= 2
    }
    
    return render(request, "analyzer/history.html", context)


@login_required
@require_http_methods(["POST"])
def delete_analysis(request, analysis_id):
    """
    Deletes an analysis record for the logged-in user.
    """
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id, user=request.user)
    record.delete()
    return redirect('history')


@login_required
@ensure_csrf_cookie
def settings_view(request):
    """
    Renders the settings page showing user personal info, and handles updates.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    total_scans = ResumeAnalysis.objects.filter(user=request.user).count()
    error = None
    success = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()

        if not username:
            error = "Username cannot be empty."
        else:
            from django.contrib.auth.models import User
            if User.objects.filter(username=username).exclude(id=request.user.id).exists():
                error = "Username is already taken."
            else:
                try:
                    # Update User
                    request.user.username = username
                    request.user.email = email
                    request.user.save()

                    # Update UserProfile
                    profile.phone_number = phone_number
                    profile.save()
                    success = "Profile updated successfully!"
                except Exception as e:
                    error = f"An error occurred: {str(e)}"

    return render(request, "analyzer/settings.html", {
        "profile": profile,
        "total_scans": total_scans,
        "error": error,
        "success": success
    })


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

def signup_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                from django.db import IntegrityError

                user = form.save()
                # Specify the backend since we have multiple
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect("index")
            except IntegrityError:
                form.add_error("username", "An account with that username already exists.")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@require_http_methods(["POST"])
def generate_cover_letter_api(request, analysis_id):
    """API endpoint for the React component to generate a cover letter asynchronously."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    perms = get_premium_permissions(request.user, record)
    if not perms["can_cover_letter"]:
        return JsonResponse({"error": "Premium subscription required to generate cover letters."}, status=403)

    # Decode JSON body if options are sent, otherwise fallback to empty dict
    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}

    tone = body.get("tone", "Professional")
    length = body.get("length", "Medium")
    highlights = body.get("highlights", "")
    force_regenerate = body.get("force_regenerate", False)

    if record.cover_letter and not force_regenerate:
        return JsonResponse({"cover_letter": record.cover_letter})

    try:
        letter = generate_cover_letter(
            record.resume_text, 
            record.job_desc_full, 
            tone=tone, 
            length=length, 
            highlights=highlights
        )
        record.cover_letter = letter
        record.save()
        return JsonResponse({"cover_letter": letter})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def export_cover_letter_pdf(request, analysis_id):
    """Generates a PDF of the cover letter and returns it as a download."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    perms = get_premium_permissions(request.user, record)
    if not perms["can_cover_letter"]:
        return HttpResponse("Premium subscription required.", status=403)

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


def export_report_pdf(request, analysis_id):
    """Generates a PDF of the match report and returns it as a download."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    perms = get_premium_permissions(request.user, record)
    if not perms["can_download_pdf"]:
        return HttpResponse("Pro, Elite, or Unlimited subscription required to download PDF report.", status=403)

    if record.status != 'completed':
        return HttpResponse("Report not ready yet.", status=400)

    from django.template.loader import render_to_string
    import io
    from xhtml2pdf import pisa

    # Prepare context for the template
    matched_skills = record.matched_skills if record.matched_skills else []
    missing_skills = record.missing_skills if record.missing_skills else []
    
    # Normalize skill dicts/strings
    matched = [{"skill": s.get('skill', '') if isinstance(s, dict) else s} for s in matched_skills]
    missing = [{"skill": s.get('skill', '') if isinstance(s, dict) else s} for s in missing_skills]

    context = {
        "analysis": record,
        "matched_skills": matched,
        "missing_skills": missing,
    }

    # Render HTML
    html_string = render_to_string("analyzer/report_pdf.html", context)

    # Generate PDF
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html_string, dest=buffer)

    if pisa_status.err:
        return HttpResponse("Failed to generate PDF. Please try again later.", status=500)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Match_Report_{record.id}.pdf"'
    return response



# ── Razorpay Payments ────────────────────────────────────────────

def pricing_view(request):
    """Serve the pricing / upgrade page."""
    current_tier = 0
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.is_premium and profile.current_period_end and profile.current_period_end > timezone.now():
            current_tier = profile.subscription_tier

    return render(request, "analyzer/pricing.html", {
        "RAZORPAY_KEY_ID": settings.RAZORPAY_KEY_ID,
        "current_tier": current_tier
    })

@login_required
def create_razorpay_order(request):
    """Initiates a Razorpay Order session for one-time payments."""
    tier = int(request.GET.get('tier', 1))
    annual = request.GET.get('annual', 'false').lower() == 'true'
    coupon_code = request.GET.get('coupon', '').strip()

    # Determine base price
    base_prices = {
        1: {'monthly': 49, 'annual': 499},
        2: {'monthly': 149, 'annual': 1499},
        3: {'monthly': 299, 'annual': 2999},
        4: {'monthly': 999, 'annual': 9999},
    }
    
    if tier not in base_prices:
        return render(request, "analyzer/pricing.html", {"error": "Invalid tier selected."})
    
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    now = timezone.now()
    is_active = profile.is_premium and profile.current_period_end and profile.current_period_end > now

    prorated_credit = 0

    if is_active:
        current_tier = profile.subscription_tier
        if tier <= current_tier:
            return render(request, "analyzer/pricing.html", {
                "error": f"You are already on a higher or equal plan (Tier {current_tier}). Downgrading is not permitted while active.",
                "RAZORPAY_KEY_ID": settings.RAZORPAY_KEY_ID,
                "current_tier": current_tier
            })
        
        # Upgrade: calculate proration
        days_remaining = max(0, (profile.current_period_end - now).days)
        start_date_for_math = profile.current_period_start or (profile.current_period_end - timezone.timedelta(days=30))
        total_days = max(1, (profile.current_period_end - start_date_for_math).days)
        
        was_annual = total_days > 50
        current_base = base_prices.get(current_tier, base_prices[1])
        current_price = current_base['annual'] if was_annual else current_base['monthly']
        
        daily_rate = current_price / total_days
        prorated_credit = int(days_remaining * daily_rate)

    price_inr = base_prices[tier]['annual'] if annual else base_prices[tier]['monthly']

    # Apply Coupon
    discount = 0
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
            if coupon.is_valid():
                discount = int(price_inr * (coupon.discount_percent / 100.0))
                # Note: We will increment `coupon.uses` ONLY when payment is successful (in webhook)
            else:
                return render(request, "analyzer/pricing.html", {"error": "Coupon is invalid or expired."})
        except Coupon.DoesNotExist:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            return render(request, "analyzer/pricing.html", {"error": "Coupon not found.", "current_tier": getattr(profile, 'subscription_tier', 0)})

    final_price_inr = max(1, price_inr - discount - prorated_credit)
    amount_in_paise = final_price_inr * 100

    try:
        # Create an Order in Razorpay
        order = razorpay_client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": f"receipt_tier_{tier}",
            "notes": {
                "tier": tier,
                "annual": str(annual).lower(),
                "user_id": request.user.id,
                "coupon_code": coupon_code
            }
        })
        
        return render(request, "analyzer/razorpay_checkout.html", {
            "order_id": order['id'],
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "user_email": request.user.email,
            "amount": amount_in_paise,
            "tier": tier,
            "annual": annual,
            "discount_applied": discount > 0,
            "final_price_inr": final_price_inr
        })
    except Exception as e:
        return render(request, "analyzer/pricing.html", {"error": str(e)})

@csrf_exempt
def razorpay_webhook(request):
    """Handles Razorpay Webhook events."""
    payload = request.body.decode('utf-8')
    sig_header = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    
    try:
        razorpay_client.utility.verify_webhook_signature(payload, sig_header, settings.RAZORPAY_WEBHOOK_SECRET)
    except Exception as e:
        return HttpResponse(status=400)

    import json
    import datetime
    from dateutil.relativedelta import relativedelta
    from django.contrib.auth.models import User
    
    event = json.loads(payload)
    
    # Listen for order payment capture
    if event['event'] == 'payment.captured':
        payment_entity = event['payload']['payment']['entity']
        notes = payment_entity.get('notes', {})
        
        user_id = notes.get('user_id')
        tier = int(notes.get('tier', 0))
        is_annual = notes.get('annual') == 'true'
        coupon_code = notes.get('coupon_code')
        
        if user_id and tier > 0:
            try:
                user = User.objects.get(id=user_id)
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.is_premium = True
                profile.subscription_tier = tier
                
                now = datetime.datetime.now(datetime.timezone.utc)
                if profile.current_period_end and profile.current_period_end > now:
                    start_date = profile.current_period_end
                else:
                    start_date = now
                    profile.current_period_start = now
                    
                if is_annual:
                    profile.current_period_end = start_date + relativedelta(years=1)
                else:
                    profile.current_period_end = start_date + relativedelta(months=1)
                    
                # Reset start date to today if they are upgrading to a new tier, to restart proration math correctly
                profile.current_period_start = now
                profile.save()
                
                # Update coupon usage atomically
                if coupon_code:
                    try:
                        from django.db.models import F
                        Coupon.objects.filter(code__iexact=coupon_code).update(uses=F('uses') + 1)
                    except Exception:
                        pass
            except User.DoesNotExist:
                pass
                
        return HttpResponse(status=200)

    return HttpResponse(status=200)

def verify_coupon(request):
    """Returns coupon validity and discount percentage."""
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    from django.core.cache import cache
    cache_key = f"coupon_rl_{client_ip}"
    attempts = cache.get(cache_key, 0)
    
    if attempts > 20:
        return JsonResponse({"valid": False, "error": "Too many attempts. Please try again later."})
        
    cache.set(cache_key, attempts + 1, 300) # 5 min timeout

    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({"valid": False, "error": "No code provided"})
    
    try:
        coupon = Coupon.objects.get(code__iexact=code)
        if coupon.is_valid():
            return JsonResponse({"valid": True, "discount": coupon.discount_percent})
        else:
            return JsonResponse({"valid": False, "error": "Coupon expired or usage limit reached"})
    except Coupon.DoesNotExist:
        return JsonResponse({"valid": False, "error": "Invalid coupon code"})

# ── Public API ───────────────────────────────────────────────────

@csrf_exempt
def api_analyze(request):
    """
    Public API endpoint for Resume Analyzer.
    Accepts POST with 'resume_text' and 'job_desc'.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    expected_key = getattr(settings, "APP_API_KEY", "")
    if not expected_key or auth_header != f"Bearer {expected_key}":
        return JsonResponse({"error": "Unauthorized"}, status=401)
        
    resume_text = request.POST.get("resume_text", "")
    job_desc = request.POST.get("job_desc", "")
    
    if not resume_text or not job_desc:
        try:
            data = json.loads(request.body)
            resume_text = data.get("resume_text", "")
            job_desc = data.get("job_desc", "")
        except json.JSONDecodeError:
            pass

    if not resume_text or not job_desc:
        return JsonResponse({"error": "resume_text and job_desc are required"}, status=400)
        
    try:
        from .utils import analyze_with_ai
        analysis_data, usage_data = analyze_with_ai(resume_text, job_desc)
        return JsonResponse({
            "status": "success", 
            "data": analysis_data,
            "usage": usage_data
        })
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

@login_required
def market_insights(request):
    """
    Global Market Trends Dashboard (Premium Feature).
    Aggregates anonymized skill data across all user scans.
    Supports filtering by AI-classified job category.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not (profile.is_active_premium() and profile.subscription_tier >= 1):
        return redirect('pricing')

    from django.core.cache import cache
    
    CATEGORIES = [
        "Software Engineering",
        "Data & Analytics",
        "Product Management",
        "Sales & Marketing",
        "Design & UX",
        "Finance & Business",
        "Healthcare",
        "Other"
    ]
    
    category = request.GET.get('category', '').strip()
    selected_category = category if category in CATEGORIES else "All"
    
    # Try cache first to avoid Memory DoS
    cache_key = f"market_insights_dashboard_{selected_category.replace(' ', '_')}"
    context = cache.get(cache_key)
    
    if not context:
        analyses = ResumeAnalysis.objects.filter(status='completed')
        if selected_category != "All":
            analyses = analyses.filter(category=selected_category)
            
        analyses = analyses.values('match_score', 'matched_skills', 'missing_skills')
        total_scans = analyses.count()
        
        if total_scans == 0:
            context = {
                "total_scans": 0,
                "avg_score": 0,
                "top_matched_labels": [],
                "top_matched_data": [],
                "top_missing_labels": [],
                "top_missing_data": [],
                "selected_category": selected_category,
                "categories": CATEGORIES,
                "error": f"Not enough data yet for category '{selected_category}'." if selected_category != "All" else "Not enough data yet."
            }
        else:
            total_score = 0
            matched_counter = Counter()
            missing_counter = Counter()

            for a in analyses.iterator():
                total_score += a['match_score']
                for ms in (a['matched_skills'] or []):
                    skill_name = ms.get('skill', ms) if isinstance(ms, dict) else ms
                    matched_counter[str(skill_name).title()] += 1
                    
                for ms in (a['missing_skills'] or []):
                    skill_name = ms.get('skill', ms) if isinstance(ms, dict) else ms
                    missing_counter[str(skill_name).title()] += 1

            avg_score = total_score / total_scans
            top_matched = matched_counter.most_common(10)
            top_missing = missing_counter.most_common(10)

            context = {
                "total_scans": total_scans,
                "avg_score": round(avg_score, 1),
                "top_matched_labels": [x[0] for x in top_matched],
                "top_matched_data": [x[1] for x in top_matched],
                "top_missing_labels": [x[0] for x in top_missing],
                "top_missing_data": [x[1] for x in top_missing],
                "selected_category": selected_category,
                "categories": CATEGORIES,
            }
            
            # Cache for 1 hour (3600 seconds)
            cache.set(cache_key, context, 3600)

    # Dynamic items (always set or overridden to make sure template works correctly)
    context["selected_category"] = selected_category
    context["categories"] = CATEGORIES

    return render(request, "analyzer/insights.html", context)

@login_required
@require_http_methods(["POST"])
def request_otp(request):
    """Generate and send OTP for email or phone."""
    import json
    from datetime import timedelta
    from django.utils import timezone
    try:
        data = json.loads(request.body)
        purpose = data.get('purpose')
        if purpose not in ['email', 'phone']:
            return JsonResponse({"status": "error", "message": "Invalid purpose"}, status=400)
        if purpose == 'phone':
            phone_number = data.get('phone_number')
            if not phone_number:
                # Use existing phone number from profile if available
                phone_number = getattr(request.user.profile, 'phone_number', None)
                if not phone_number:
                    return JsonResponse({"status": "error", "message": "Phone number required"}, status=400)
            request.user.profile.phone_number = phone_number
            request.user.profile.save()
            
        # Invalidate old OTPs
        OTP.objects.filter(user=request.user, purpose=purpose, is_used=False).update(is_used=True)
        
        # Generate new OTP
        code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        OTP.objects.create(user=request.user, code=code, purpose=purpose, expires_at=expires_at)
        
        # Send OTP
        if purpose == 'email':
            send_email_otp(request.user, code)
        else:
            send_sms_otp(request.user, code, request.user.profile.phone_number)
            
        return JsonResponse({"status": "success", "message": f"OTP sent to {purpose}"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def verify_otp(request):
    """Verify the submitted OTP code."""
    import json
    from django.utils import timezone
    try:
        data = json.loads(request.body)
        purpose = data.get('purpose')
        if purpose not in ['email', 'phone']:
            return JsonResponse({"status": "error", "message": "Invalid purpose"}, status=400)
        code = data.get('code')
        
        if not code:
            return JsonResponse({"status": "error", "message": "OTP code is required"}, status=400)
            
        otp_obj = OTP.objects.filter(
            user=request.user, 
            purpose=purpose, 
            code=code, 
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if not otp_obj:
            return JsonResponse({"status": "error", "message": "Invalid or expired OTP"}, status=400)
            
        # Mark as used
        otp_obj.is_used = True
        otp_obj.save()
        
        # Update user profile
        if purpose == 'email':
            request.user.profile.email_verified = True
        elif purpose == 'phone':
            request.user.profile.phone_verified = True
        request.user.profile.save()
        
        return JsonResponse({"status": "success", "message": f"{purpose.capitalize()} verified successfully!"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def payment_failed(request):
    """Render a dedicated error page when payment fails."""
    error = request.GET.get('error', 'Payment transaction failed. Please try again.')
    code = request.GET.get('code', 'payment_failed')
    order_id = request.GET.get('order_id', '')
    payment_id = request.GET.get('payment_id', '')
    return render(request, "analyzer/payment_failed.html", {
        "error": error,
        "code": code,
        "order_id": order_id,
        "payment_id": payment_id,
    })


def contact_view(request):
    """Render the Contact Us support page."""
    return render(request, "analyzer/contact.html")


@login_required
@require_http_methods(["POST"])
def start_interview_api(request, analysis_id):
    """Starts a new mock interview session or resumes an active one."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    perms = get_premium_permissions(request.user, record)
    if not perms["can_interview"]:
        return JsonResponse({"error": "Upgrade to Pro, Elite, or Unlimited to access Mock Interviews."}, status=403)

    session = InterviewSession.objects.filter(user=request.user, analysis=record, status="active").first()
    is_new = False

    if not session:
        session = InterviewSession.objects.create(user=request.user, analysis=record)
        is_new = True

    messages = session.messages.all()

    if is_new or messages.count() == 0:
        # Generate the first interview question
        first_question = generate_next_interview_question(record.resume_text, record.job_desc_full, [])
        InterviewMessage.objects.create(session=session, sender="ai", message=first_question)
        messages = session.messages.all()

    messages_data = [
        {
            "id": msg.id,
            "sender": msg.sender,
            "message": msg.message,
            "feedback": msg.feedback,
            "score": msg.score,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in messages
    ]

    return JsonResponse({
        "session_id": session.id,
        "messages": messages_data,
    })


@login_required
@require_http_methods(["POST"])
def send_interview_message_api(request, session_id):
    """Handles candidate's reply, evaluates it, and generates the next question."""
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    try:
        body = json.loads(request.body)
        user_answer = body.get("message", "").strip()
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not user_answer:
        return JsonResponse({"error": "Answer cannot be empty"}, status=400)

    # Get the last AI message (the question asked)
    last_ai_msg = session.messages.filter(sender="ai").last()
    question = last_ai_msg.message if last_ai_msg else "Tell me about your background."

    # Evaluate the user's answer
    evaluation = evaluate_interview_answer(question, user_answer, session.analysis.job_desc_full)
    
    # Save the user's message with score and feedback
    user_msg = InterviewMessage.objects.create(
        session=session,
        sender="user",
        message=user_answer,
        feedback=evaluation.get("feedback", ""),
        score=evaluation.get("score", 70)
    )

    # Fetch updated history for generating the next question
    chat_history = [
        {"sender": m.sender, "message": m.message}
        for m in session.messages.all()
    ]

    # Generate the next question
    next_question = generate_next_interview_question(
        session.analysis.resume_text,
        session.analysis.job_desc_full,
        chat_history
    )

    # Save next question
    InterviewMessage.objects.create(session=session, sender="ai", message=next_question)

    # Return all messages in the session
    messages_data = [
        {
            "id": msg.id,
            "sender": msg.sender,
            "message": msg.message,
            "feedback": msg.feedback,
            "score": msg.score,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in session.messages.all()
    ]

    return JsonResponse({
        "session_id": session.id,
        "messages": messages_data,
    })


@login_required
@require_http_methods(["POST"])
def suggest_bullet_rewrite_api(request, analysis_id):
    """Returns 3 optimized rewrites and STAR/XYZ validation for a specific resume bullet point."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    try:
        body = json.loads(request.body)
        bullet_point = body.get("bullet_point", "").strip()
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not bullet_point:
        return JsonResponse({"error": "Bullet point cannot be empty"}, status=400)

    result = suggest_bullet_rewrites(bullet_point, record.job_desc_full)
    if isinstance(result, list):
        from .utils import generate_offline_validation
        result = {
            "suggestions": result,
            "validation": generate_offline_validation(bullet_point)
        }
    return JsonResponse(result)



@login_required
@require_http_methods(["POST"])
def recalculate_score_api(request, analysis_id):
    """Saves edited resume text and recalculates match analytics synchronously."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    try:
        body = json.loads(request.body)
        new_resume_text = body.get("resume_text", "").strip()
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not new_resume_text:
        return JsonResponse({"error": "Resume text cannot be empty"}, status=400)

    try:
        # Update text
        record.resume_text = new_resume_text
        record.status = 'pending'
        record.save()

        # Recalculate synchronously
        process_resume_analysis(str(record.slug))
        
        # Refresh record
        record.refresh_from_db()
        return JsonResponse({
            "status": "success",
            "match_score": record.match_score,
            "category": record.category,
            "matched_skills": record.matched_skills,
            "missing_skills": record.missing_skills,
            "suggestions": record.suggestions,
            "experience_gaps": record.experience_gaps,
            "impact_critiques": record.impact_critiques,
            "ats_format_issues": record.ats_format_issues
        })
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
def export_resume_pdf(request, analysis_id):
    """Parses resume to structured JSON if missing, and outputs standard resume PDF layouts."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    perms = get_premium_permissions(request.user, record)
    if not perms["can_download_pdf"]:
        return HttpResponse("Pro, Elite, or Unlimited subscription required to download resume PDF.", status=403)

    template_layout = request.GET.get("template", "minimal").lower()
    if template_layout not in ["minimal", "executive", "modern"]:
        template_layout = "minimal"

    # Check for localization
    localization_id = request.GET.get("localization_id")
    if localization_id:
        loc = get_object_or_404(LocalizedResume, slug=localization_id, analysis=record)
        resume_data = loc.translated_resume
    else:
        # If structured JSON is not cached, parse the plain text resume
        if not record.structured_resume:
            structured_data = parse_resume_to_json(record.resume_text)
            record.structured_resume = structured_data
            record.save()
        resume_data = record.structured_resume

    from django.template.loader import render_to_string
    import io
    from xhtml2pdf import pisa

    context = {
        "resume": resume_data,
    }

    # Render HTML template
    template_name = f"analyzer/resume_pdf_{template_layout}.html"
    html_string = render_to_string(template_name, context)

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html_string, dest=buffer)

    if pisa_status.err:
        return HttpResponse("Failed to generate resume PDF. Please try again.", status=500)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Optimized_Resume_{template_layout}.pdf"'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Resume Builder Wizard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def resume_builder_view(request):
    """Renders the step-by-step guided resume builder wizard."""
    analysis_id = request.GET.get("edit")
    initial_data = {}
    if analysis_id:
        try:
            import uuid
            record = ResumeAnalysis.objects.get(slug=uuid.UUID(analysis_id), user=request.user)
            initial_data = record.structured_resume or {}
        except (ResumeAnalysis.DoesNotExist, ValueError):
            pass
    return render(request, "analyzer/builder_wizard.html", {
        "initial_data_json": json.dumps(initial_data),
    })


@login_required
@require_http_methods(["POST"])
def parse_resume_for_builder_api(request):
    """
    Accepts an uploaded resume, extracts text, parses to structured JSON via Groq AI,
    and returns the structured data to prefill the builder workspace.
    """
    resume_file = request.FILES.get("resume")
    if not resume_file:
        return JsonResponse({"error": "No resume file provided."}, status=400)

    # Validate file extension
    ext = os.path.splitext(resume_file.name)[1].lower()
    if ext not in [".pdf", ".docx"]:
        return JsonResponse({"error": "Unsupported file format. Please upload PDF or DOCX."}, status=400)

    # Validate file size (2 MB cap)
    if resume_file.size > 2 * 1024 * 1024:
        return JsonResponse({"error": "File size exceeds 2 MB limit."}, status=400)

    try:
        # Extract text using our existing utility function
        resume_text, _, _ = extract_text(resume_file, ext)
        if not resume_text:
            return JsonResponse({"error": "Could not extract text from this file."}, status=422)

        # Parse text into structured resume JSON via our existing utility function
        structured_data = parse_resume_to_json(resume_text)
        
        return JsonResponse({"status": "success", "resume": structured_data})

    except Exception as exc:
        return JsonResponse({"error": f"Failed to parse resume: {str(exc)}"}, status=500)


@login_required
@require_http_methods(["POST"])
def save_builder_resume_api(request):
    """Saves the wizard JSON payload into a ResumeAnalysis and ResumeVersion."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Candidate name is required."}, status=400)

    # Rebuild plain text from structured data for ATS re-analysis
    lines = [name]
    contact = data.get("contact", {})
    if contact.get("email"):
        lines.append(contact["email"])
    if contact.get("phone"):
        lines.append(contact["phone"])
    if contact.get("location"):
        lines.append(contact["location"])
    summary = data.get("summary", "")
    if summary:
        lines.append("\nSUMMARY\n" + summary)
    for exp in data.get("experience", []):
        lines.append(f"\n{exp.get('role', '')} at {exp.get('company', '')} | {exp.get('duration', '')}")
        for b in exp.get("bullets", []):
            lines.append(f"• {b}")
    for edu in data.get("education", []):
        lines.append(f"\n{edu.get('degree', '')} — {edu.get('institution', '')} | {edu.get('duration', '')}")
    skills = data.get("skills", {})
    all_skills = []
    for cat in ["languages", "frameworks", "tools", "other"]:
        all_skills.extend(skills.get(cat, []))
    if all_skills:
        lines.append("\nSKILLS\n" + ", ".join(all_skills))
    plain_text = "\n".join(lines)

    # Create a ResumeVersion entry
    resume_version = ResumeVersion.objects.create(
        user=request.user,
        filename=f"{name}_wizard_resume.txt",
        encrypted_text=plain_text,
    )

    target_job_title = data.get("target_job_title", "").strip() or "Professional"
    target_industry = data.get("target_industry", "").strip() or "General"
    job_desc = f"Looking for a qualified {target_job_title} in the {target_industry} industry. Key responsibilities include executing domain-specific projects, collaborating with teams, and applying relevant technical skills."

    # Create the ResumeAnalysis entry with structured data pre-cached, in pending status
    analysis = ResumeAnalysis.objects.create(
        user=request.user,
        filename=f"{name}_wizard_resume",
        resume_text=plain_text,
        job_desc_full=job_desc,
        job_desc_snippet=job_desc[:120],
        status="pending",
        resume_version=resume_version,
        structured_resume=data,
    )

    # Process AI analysis synchronously to populate critiques, score, and interview questions
    try:
        process_resume_analysis(str(analysis.slug))
    except Exception as exc:
        print(f"[save_builder_resume_api] AI processing fallback error: {exc}")
        analysis.status = "completed"
        analysis.save()

    return JsonResponse({
        "status": "success",
        "analysis_id": str(analysis.slug),
        "redirect_url": f"/results/{analysis.slug}/",
    })


@login_required
@require_http_methods(["POST"])
def suggest_summary_api(request):
    """Returns 3 AI-generated professional summary options."""
    try:
        body = json.loads(request.body)
        job_title = body.get("job_title", "").strip()
        industry = body.get("industry", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    if not job_title:
        return JsonResponse({"error": "job_title is required."}, status=400)

    suggestions = get_ai_summary_suggestions(job_title, industry or "General")
    return JsonResponse({"suggestions": suggestions})


@login_required
@require_http_methods(["POST"])
def suggest_bullets_api(request):
    """Returns 15 metrics-driven pre-written bullets grouped by category, with AI fallback."""
    try:
        body = json.loads(request.body)
        job_title = body.get("job_title", "").strip()
        company_type = body.get("company_type", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    if not job_title:
        return JsonResponse({"error": "job_title is required."}, status=400)

    from .models import PreWrittenBullet

    # 1. Look up exact matches
    bullet_objs = PreWrittenBullet.objects.filter(job_role__iexact=job_title)

    # 2. Look up contains/fuzzy matches if exact fails
    if not bullet_objs.exists():
        cleaned_title = job_title.lower()
        for prefix in ["senior", "junior", "lead", "staff", "associate", "principal", "expert"]:
            cleaned_title = cleaned_title.replace(prefix, "").strip()
        
        bullet_objs = PreWrittenBullet.objects.filter(job_role__icontains=cleaned_title)

    # 3. If database hits found, format and return them
    if bullet_objs.exists():
        bullets_list = []
        categories_dict = {}
        for obj in bullet_objs:
            bullets_list.append(obj.bullet_text)
            if obj.category not in categories_dict:
                categories_dict[obj.category] = []
            categories_dict[obj.category].append(obj.bullet_text)

        categorized = [
            {"category": cat, "bullets": blts}
            for cat, blts in categories_dict.items()
        ]
        
        return JsonResponse({
            "bullets": bullets_list[:15], # Flat list for backward compatibility
            "categorized": categorized
        })

    # 4. Fallback to LLM generation
    bullets = get_ai_experience_bullets(job_title, company_type or "tech startup")

    # Cache AI results in the database
    for text in bullets:
        try:
            PreWrittenBullet.objects.get_or_create(
                job_role=job_title,
                category="AI Recommendations",
                bullet_text=text
            )
        except Exception:
            pass

    return JsonResponse({
        "bullets": bullets,
        "categorized": [{"category": "AI Recommendations", "bullets": bullets}]
    })


def portfolio_view(request, analysis_id):
    """Renders the personal portfolio preview (interactive web page)."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    
    # Determine ownership
    is_owner = False
    if request.user.is_authenticated and record.user == request.user:
        is_owner = True
    elif not request.user.is_authenticated and record.user is None:
        is_owner = True

    # If the viewer is not the owner, check if the owner has premium status (sharing permission)
    if not is_owner:
        if record.user is not None:
            owner_perms = get_premium_permissions(record.user, record)
            can_view_publicly = owner_perms.get("can_download_pdf", False)
        else:
            can_view_publicly = False

        if not can_view_publicly:
            # Render premium-lock screen for recruiters/public
            return render(request, "analyzer/portfolio.html", {
                "record": record,
                "lock_screen": True,
                "is_owner": False,
                "is_export": False,
            })

    # Check for localization
    localization_id = request.GET.get("localization_id")
    if localization_id:
        loc = get_object_or_404(LocalizedResume, slug=localization_id, analysis=record)
        resume_data = loc.translated_resume
    else:
        # Cache structured resume to avoid repeated parser calls
        if not record.structured_resume:
            record.structured_resume = parse_resume_to_json(record.resume_text)
            record.save()
        resume_data = record.structured_resume

    context = {
        "record": record,
        "resume": resume_data,
        "is_owner": is_owner,
        "is_export": False,
        "lock_screen": False,
        "localization_id": localization_id,
    }
    return render(request, "analyzer/portfolio.html", context)


def export_portfolio_html(request, analysis_id):
    """Generates and downloads a self-contained, single-file HTML version of the portfolio."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    
    # Ownership and premium permission checks
    is_owner = request.user.is_authenticated and record.user == request.user
    if not is_owner:
        return HttpResponse("Access denied: Only the owner can export this portfolio.", status=403)

    perms = get_premium_permissions(request.user, record)
    if not perms.get("can_download_pdf", False):
        return HttpResponse("Pro, Elite, or Unlimited subscription required to export portfolio HTML.", status=403)

    # Check for localization
    localization_id = request.GET.get("localization_id")
    if localization_id:
        loc = get_object_or_404(LocalizedResume, slug=localization_id, analysis=record)
        resume_data = loc.translated_resume
    else:
        # Ensure structured resume is cached
        if not record.structured_resume:
            record.structured_resume = parse_resume_to_json(record.resume_text)
            record.save()
        resume_data = record.structured_resume

    from django.template.loader import render_to_string
    context = {
        "record": record,
        "resume": resume_data,
        "is_owner": False,
        "is_export": True,
        "lock_screen": False,
    }
    
    html_content = render_to_string("analyzer/portfolio.html", context)
    
    # Clean filename for export
    clean_name = "".join(c for c in record.filename if c.isalnum() or c in "._-").split(".")[0]
    response = HttpResponse(html_content, content_type="text/html")
    response["Content-Disposition"] = f'attachment; filename="Portfolio_{clean_name}.html"'
    return response


@require_http_methods(["POST"])
def localize_resume_api(request, analysis_id):
    """API endpoint to translate and localize a resume to a target language and market."""
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    
    # Ownership safety check: allow guests to localize guest records
    if record.user and record.user != request.user:
        return JsonResponse({"error": "Access denied: You are not the owner of this resume."}, status=403)

    # Check permission (guests on their first scan get it, premium/pro users get it)
    perms = get_premium_permissions(request.user, record)
    if not perms["can_download_pdf"]:
        return JsonResponse({"error": "Pro, Elite, or Unlimited subscription required to translate resumes."}, status=403)

    try:
        body = json.loads(request.body)
        target_lang = body.get("language", "").strip()
        target_market = body.get("target_market", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    if not target_lang or not target_market:
        return JsonResponse({"error": "language and target_market are required."}, status=400)

    # Cache structured resume JSON if not already present
    if not record.structured_resume:
        record.structured_resume = parse_resume_to_json(record.resume_text)
        record.save()

    # Call AI localizer
    translated_data = localize_resume_data(record.structured_resume, target_lang, target_market)
    
    # Save/Cache in database
    loc = LocalizedResume.objects.create(
        analysis=record,
        language=target_lang,
        target_market=target_market,
        translated_resume=translated_data
    )

    return JsonResponse({
        "status": "success",
        "localization_id": str(loc.slug),
        "translated_resume": loc.translated_resume
    })


@login_required
def compare_versions_view(request):
    """Renders side-by-side comparison of two resume analyses, showing line diffs and target alignments."""
    # Fetch all completed analyses for this user to populate selectors
    analyses = ResumeAnalysis.objects.filter(user=request.user, status='completed').order_by('-created_at')
    
    left_id = request.GET.get("left")
    right_id = request.GET.get("right")
    
    left_analysis = None
    right_analysis = None
    left_diff = None
    right_diff = None
    score_gap = None
    
    if left_id and right_id:
        left_analysis = get_object_or_404(ResumeAnalysis, slug=left_id, user=request.user)
        right_analysis = get_object_or_404(ResumeAnalysis, slug=right_id, user=request.user)
        
        # Calculate score gap
        score_gap = right_analysis.match_score - left_analysis.match_score
        
        # Generate aligned split diff HTML
        from .diff_engine import generate_split_diff
        left_diff, right_diff = generate_split_diff(left_analysis.resume_text, right_analysis.resume_text)
        
    context = {
        "analyses": analyses,
        "left_analysis": left_analysis,
        "right_analysis": right_analysis,
        "left_diff": left_diff,
        "right_diff": right_diff,
        "score_gap": score_gap,
        "left_id": left_id,
        "right_id": right_id,
    }
    return render(request, "analyzer/compare.html", context)


def authenticity_audit_view(request):
    """Renders the Authenticity Audit page, supporting interactive simulations for guests and users."""
    if request.method == "POST":
        # Handle simulated analysis
        resume_name = request.FILES.get("resume").name if request.FILES.get("resume") else "uploaded_resume.pdf"
        
        # Simulated high-fidelity authenticity response data
        result = {
            "status": "success",
            "filename": resume_name,
            "authenticity_score": 74,
            "ai_writing_probability": 38,
            "red_flags": [
                {
                    "type": "Timeline Gap",
                    "severity": "medium",
                    "description": "Unexplained 7-month chronological gap between Senior Frontend Developer and Full-Stack Lead roles.",
                    "mitigation": "Clarify employment gap or add freelance/contract activities if applicable during this time."
                },
                {
                    "type": "Credential Inflation",
                    "severity": "high",
                    "description": "AWS Certified Solutions Architect certification lists a verification ID that does not match official registry records.",
                    "mitigation": "Check the verification code or date format. Ensure ID matches the AWS certification center registry."
                },
                {
                    "type": "Vague Metrics",
                    "severity": "low",
                    "description": "Stated 'Spearheaded critical initiatives to improve site performance' without key quantitative metrics (e.g. % speedup).",
                    "mitigation": "Quantify outcomes (e.g. 'boosted load time by 34% or reduced query latency by 120ms')."
                }
            ],
            "authenticity_checks": {
                "linkedin_match": "mismatch", # match, mismatch, unverified
                "employment_history": "80% match (duration mismatch on 1 role)",
                "education_verification": "verified (Bachelor of Science, Computer Science)",
                "reference_checks": "2 pending, 1 positive response"
            }
        }
        return JsonResponse(result)
        
    return render(request, "analyzer/authenticity_audit.html")


def screening_room_view(request):
    """Renders the interactive AI Screening Room / Mock Interview simulator."""
    return render(request, "analyzer/screening_room.html")


def auto_vet_view(request):
    """Renders the Auto-Vet Agent bulk candidate screening dashboard."""
    if request.method == "POST" and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Simulated recruiter bulk parse screening results
        candidates = [
            {
                "name": "Jane Smith",
                "role": "Full-Stack Developer",
                "fit_score": 87,
                "authenticity_score": 92,
                "top_skills": ["React", "Node.js", "PostgreSQL", "Docker"],
                "flags": 0,
                "status": "Shortlisted"
            },
            {
                "name": "John Doe",
                "role": "Backend Engineer",
                "fit_score": 78,
                "authenticity_score": 64,
                "top_skills": ["Python", "Django", "AWS", "Redis"],
                "flags": 2,
                "status": "Under Review"
            },
            {
                "name": "Robert Chen",
                "role": "Lead Architect",
                "fit_score": 91,
                "authenticity_score": 96,
                "top_skills": ["System Design", "Go", "Kubernetes", "gRPC"],
                "flags": 0,
                "status": "Shortlisted"
            },
            {
                "name": "Sarah Miller",
                "role": "Frontend Specialist",
                "fit_score": 62,
                "authenticity_score": 81,
                "top_skills": ["TypeScript", "Next.js", "Tailwind CSS"],
                "flags": 1,
                "status": "Rejected"
            }
        ]
        return JsonResponse({"status": "success", "candidates": candidates})
        
    return render(request, "analyzer/auto_vet.html")


def skills_gap_view(request):
    """Renders the Skills Gap Analysis visualization and competency mapping page."""
    if request.method == "POST" and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Simulated skills gap matching data
        data = {
            "status": "success",
            "fit_score": 76,
            "categories": [
                {
                    "name": "Core Technical Skills",
                    "match": 80,
                    "matched": ["React", "JavaScript", "HTML5/CSS3", "Git"],
                    "missing": ["TypeScript", "Next.js"]
                },
                {
                    "name": "Backend & Database",
                    "match": 65,
                    "matched": ["Node.js", "Express"],
                    "missing": ["GraphQL", "MongoDB", "Redis"]
                },
                {
                    "name": "DevOps & Cloud",
                    "match": 40,
                    "matched": ["Docker"],
                    "missing": ["AWS", "CI/CD Pipelines", "Terraform"]
                }
            ],
            "learning_resources": [
                {"skill": "TypeScript", "resource": "Official TypeScript Deep Dive Guide (Free)", "link": "https://www.typescriptlang.org/"},
                {"skill": "Next.js", "resource": "Next.js Learn Dashboard (Interactive)", "link": "https://nextjs.org/learn"},
                {"skill": "AWS", "resource": "AWS Cloud Practitioner Essentials (Free 6h Course)", "link": "https://aws.amazon.com/training/"},
                {"skill": "GraphQL", "resource": "Apollo Odyssey GraphQL Tutorials", "link": "https://odyssey.apollographql.com/"}
            ]
        }
        return JsonResponse(data)
        
    return render(request, "analyzer/skills_gap.html")


def chrome_extension_view(request):
    """Renders the Chrome Extension download and product tour page."""
    return render(request, "analyzer/chrome_extension.html")


