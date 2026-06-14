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
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .models import ResumeAnalysis
from .utils import analyze_with_ai, extract_text, generate_cover_letter


def index(request):
    """Serve the upload form (Step 1) or landing page."""
    if request.user.is_authenticated:
        return render(request, "analyzer/index.html")
    return render(request, "analyzer/landing.html")


@login_required
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

    # Helper to render errors back to the index page
    def render_error(error_msg, status_code):
        return render(request, "analyzer/index.html", {"error": error_msg}, status=status_code)

    # ── 1. Validate presence ───────────────────────────────────
    if not resume_file or not job_desc:
        return render_error("Both a resume file and a job description are required.", 400)

    # ── 2. Validate file type (Extension & Magic Numbers) ──────
    ext = os.path.splitext(resume_file.name)[1].lower()
    if ext not in [".pdf", ".docx"]:
        return render_error(f'Unsupported file type "{ext}". Please upload a PDF or DOCX.', 400)

    # Security: Verify the actual file signature (magic numbers) to prevent spoofing
    # PDF files start with b'%PDF-'
    # DOCX files are ZIP archives and start with b'PK\x03\x04'
    header = resume_file.read(10)
    resume_file.seek(0)  # Reset file pointer after reading!

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
        # e.g. scanned PDF with no text layer
        return render_error(str(exc), 422)

    # ── 5. AI analysis ─────────────────────────────────────────
    try:
        analysis = analyze_with_ai(resume_text, job_desc)
        analysis["ats_format_issues"] = ats_format_issues
    except Exception as exc:
        import sys
        import traceback

        print(f"[analyzer] AI error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return render_error("AI analysis failed. Please try again in a moment.", 503)

    # ── 6. Save history & Render results ───────────────────────
    analysis_record = ResumeAnalysis.objects.create(
        user=request.user,
        filename=resume_file.name,
        resume_text=resume_text,
        job_desc_full=job_desc,
        job_desc_snippet=job_desc[:120],
        **analysis,
    )

    return render(
        request,
        "analyzer/results.html",
        {
            "analysis": analysis_record,  # Pass the model instance so we have its ID for the React API
            "job_desc_snippet": job_desc[:120],
            "filename": resume_file.name,
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
