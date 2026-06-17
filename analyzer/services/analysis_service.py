import os
from typing import Any, Tuple, Optional

from django.core.files.uploadedfile import UploadedFile
from django_q.tasks import async_task

from analyzer.models import ResumeAnalysis
from analyzer.utils import extract_text
from analyzer.tasks import process_resume_analysis


def initiate_analysis(user: Any, resume_file: UploadedFile, job_desc: str) -> Tuple[Optional[ResumeAnalysis], str]:
    """
    Validates the file, extracts text, creates the Pending record, and queues the async task.
    Returns: (ResumeAnalysis instance or None, error message string)
    """
    ext = os.path.splitext(resume_file.name)[1].lower()
    if ext not in [".pdf", ".docx"]:
        return None, f'Unsupported file type "{ext}". Please upload a PDF or DOCX.'

    header = resume_file.read(10)
    resume_file.seek(0)

    if ext == ".pdf" and not header.startswith(b"%PDF-"):
        return None, "Invalid PDF file. The file appears to be corrupted or spoofed."
    if ext == ".docx" and not header.startswith(b"PK\x03\x04"):
        return None, "Invalid DOCX file. The file appears to be corrupted or spoofed."

    if resume_file.size > 2 * 1024 * 1024:
        return None, "File too large. Maximum size is 2 MB."

    try:
        resume_text, ats_format_issues = extract_text(resume_file, ext)
    except ValueError as exc:
        return None, str(exc)

    analysis_record = ResumeAnalysis.objects.create(
        user=user if user.is_authenticated else None,
        filename=resume_file.name,
        resume_text=resume_text,
        job_desc_full=job_desc,
        job_desc_snippet=job_desc[:120],
        status='pending',
        ats_format_issues=ats_format_issues
    )

    # Queue Async Task
    async_task(process_resume_analysis, analysis_record.id)

    return analysis_record, ""
