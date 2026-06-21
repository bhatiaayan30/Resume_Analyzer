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
import razorpay
from django.conf import settings

from .models import JobDescription, Persona, ResumeAnalysis, ResumeVersion, UserProfile, Coupon
from .utils import analyze_with_ai, extract_text, generate_cover_letter
from .tasks import process_resume_analysis

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
            used_scans = ResumeAnalysis.objects.filter(user=request.user).count()

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


from .ats_knowledge import ATS_FLAG_EXPLANATIONS

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
            "perms": get_premium_permissions(request.user, analysis_id),
        },
    )


def get_premium_permissions(user, analysis_id):
    """
    Returns a dictionary of permissions for the given user and analysis.
    """
    record = get_object_or_404(ResumeAnalysis, slug=analysis_id)
    perms = {
        "can_cover_letter": False,
        "can_interview": False,
        "can_critique": False,
        "can_download_pdf": False,
        "record": record,
    }

    # Helper to unlock all features
    def unlock_all():
        perms["can_cover_letter"] = True
        perms["can_interview"] = True
        perms["can_critique"] = True
        perms["can_download_pdf"] = True

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


from django import forms

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
    perms = get_premium_permissions(request.user, analysis_id)
    if not perms["can_cover_letter"]:
        return JsonResponse({"error": "Premium subscription required to generate cover letters."}, status=403)

    record = perms["record"]

    if record.cover_letter:
        return JsonResponse({"cover_letter": record.cover_letter})

    try:
        letter = generate_cover_letter(record.resume_text, record.job_desc_full)
        record.cover_letter = letter
        record.save()
        return JsonResponse({"cover_letter": letter})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def export_cover_letter_pdf(request, analysis_id):
    """Generates a PDF of the cover letter and returns it as a download."""
    perms = get_premium_permissions(request.user, analysis_id)
    if not perms["can_cover_letter"]:
        return HttpResponse("Premium subscription required.", status=403)

    record = perms["record"]

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
    perms = get_premium_permissions(request.user, analysis_id)
    if not perms["can_download_pdf"]:
        return HttpResponse("Pro, Elite, or Unlimited subscription required to download PDF report.", status=403)

    record = perms["record"]

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
        return HttpResponse("We had some errors <pre>" + html_string + "</pre>")

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Match_Report_{record.id}.pdf"'
    return response



# ── Razorpay Payments ────────────────────────────────────────────

from django.utils import timezone

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

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

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
from collections import Counter

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
