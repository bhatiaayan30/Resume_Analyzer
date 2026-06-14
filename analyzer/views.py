"""
views.py — HTTP request handlers.

Rule: keep views thin. Validation lives here; all business
logic (text extraction, AI calls) lives in utils.py so it
can be unit-tested without an HTTP request.
"""
import os
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .utils import extract_text, analyze_with_ai
from .models import ResumeAnalysis

def index(request):
    """Serve the upload form (Step 1)."""
    return render(request, 'analyzer/index.html')


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
    resume_file = request.FILES.get('resume')
    job_desc    = request.POST.get('job_description', '').strip()

    # Helper to render errors back to the index page
    def render_error(error_msg, status_code):
        return render(request, 'analyzer/index.html', {'error': error_msg}, status=status_code)

    # ── 1. Validate presence ───────────────────────────────────
    if not resume_file or not job_desc:
        return render_error('Both a resume file and a job description are required.', 400)

    # ── 2. Validate file type ──────────────────────────────────
    # Always validate server-side — the browser's accept= attribute
    # is trivially bypassed.
    ext = os.path.splitext(resume_file.name)[1].lower()
    if ext not in ['.pdf', '.docx']:
        return render_error(f'Unsupported file type "{ext}". Please upload a PDF or DOCX.', 400)

    # ── 3. Validate file size (2 MB cap) ──────────────────────
    if resume_file.size > 2 * 1024 * 1024:
        return render_error('File too large. Maximum size is 2 MB.', 400)

    # ── 4. Extract text ────────────────────────────────────────
    try:
        resume_text, ats_format_issues = extract_text(resume_file, ext)
    except ValueError as exc:
        # e.g. scanned PDF with no text layer
        return render_error(str(exc), 422)

    # ── 5. AI analysis ─────────────────────────────────────────
    try:
        analysis = analyze_with_ai(resume_text, job_desc)
        analysis['ats_format_issues'] = ats_format_issues
    except Exception as exc:
        import traceback
        import sys
        print(f"[analyzer] AI error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return render_error('AI analysis failed. Please try again in a moment.', 503)

    # ── 6. Save history & Render results ───────────────────────
    ResumeAnalysis.objects.create(
        filename=resume_file.name,
        job_desc_snippet=job_desc[:120],
        **analysis,
    )

    return render(request, 'analyzer/results.html', {
        'analysis': analysis,
        'job_desc_snippet': job_desc[:120],   # shown as a subtitle on results page
        'filename': resume_file.name,
    })

def history(request):
    """Serve the history of past analyses."""
    analyses = ResumeAnalysis.objects.all()
    return render(request, 'analyzer/history.html', {'analyses': analyses})
