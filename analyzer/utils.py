"""
utils.py — business logic for the Resume Analyzer.

Keeping extraction + AI logic here (not in views.py) means
these functions can be tested independently without HTTP.

Usage:
    from analyzer.utils import extract_text, analyze_with_ai
"""

import json
import os
from typing import Dict, Any, Tuple, List

import fitz  # PyMuPDF
import pdfplumber
from docx import Document
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

from analyzer.prompt_builder import (
    build_analysis_prompt,
    build_cover_letter_system_prompt,
    build_cover_letter_user_prompt,
)

# ──────────────────────────────────────────────────────────────
# Text extraction
# ──────────────────────────────────────────────────────────────


def extract_text(file_obj: Any, ext: str) -> Tuple[str, List[str]]:
    """
    Extract plain text from an uploaded PDF or DOCX file object.

    Args:
        file_obj : Django InMemoryUploadedFile
        ext      : '.pdf' or '.docx'  (lowercase, includes the dot)

    Returns:
        tuple: (Plain text string, list of ATS format warnings)

    Raises:
        ValueError: if the file has no extractable text.
    """
    ats_format_issues = []

    if ext == ".pdf":
        file_obj.seek(0)
        file_bytes = file_obj.read()

        has_tables = False
        has_images = False
        text = ""

        try:
            # Primary robust extraction with PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages = []
            for page in doc:
                # Basic layout-aware extraction
                page_text = page.get_text("text")
                pages.append(page_text)

                # Check for images
                if page.get_images():
                    has_images = True
                    
                # Check for tables
                if hasattr(page, "find_tables") and len(page.find_tables().tables) > 0:
                    has_tables = True

            text = "\n".join(pages).strip()
        except Exception as e:
            raise ValueError(f"Failed to read PDF: {str(e)}")

        if has_tables:
            ats_format_issues.append(
                "Resume contains tables. Most corporate ATS parsers (like Workday) cannot reliably extract text from inside tables, leading to missing information."
            )
        if has_images:
            ats_format_issues.append(
                "Resume contains images or complex graphics. ATS systems strip all visual elements, and image-based text is completely ignored."
            )

        if not text:
            # Most common user error — scanned / image-based PDF
            raise ValueError(
                "This PDF has no text layer — it's probably a scanned document. "
                "Please upload a text-based PDF, or run it through an OCR tool "
                "(e.g. Adobe Acrobat, Google Drive) and re-export."
            )

        # Garbled text check
        alnum_count = sum(c.isalnum() for c in text)
        if len(text) > 0 and (alnum_count / len(text)) < 0.5:
            raise ValueError(
                "The extracted text appears garbled or heavily formatted with non-standard characters. "
                "The PDF might have font encoding issues."
            )

        return text, ats_format_issues

    elif ext == ".docx":
        doc = Document(file_obj)
        if len(doc.tables) > 0:
            ats_format_issues.append(
                "Your DOCX resume contains tables. ATS systems often scramble or fail to read text embedded inside tables."
            )

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise ValueError("The DOCX file appears to be empty.")
        return "\n".join(paragraphs), ats_format_issues

    raise ValueError(f"Unsupported extension: {ext!r}")


# ──────────────────────────────────────────────────────────────
# AI analysis
# ──────────────────────────────────────────────────────────────


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def analyze_with_ai(resume_text: str, job_description: str) -> Dict[str, Any]:
    """
    Send resume + job description to Groq and return structured analysis.

    Returns a dict with keys:
        match_score     : int  (0–100)
        matched_skills  : list[str]
        missing_skills  : list[str]
        experience_gaps : list[str]
        suggestions     : list[str]   — specific, actionable improvements
        upskill_paths   : list[dict]  — suggested learning paths
        impact_critiques: list[dict]  — bullet point writing critiques

    Raises:
        RuntimeError         : GROQ_API_KEY is not set.
        json.JSONDecodeError : AI returned non-JSON.
    """
    from django.conf import settings

    api_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. " "Add it to your .env file."
        )

    client = Groq(api_key=api_key)


    # ── Fetch Prompt from Builder ─────────────
    prompt = build_analysis_prompt(resume_text, job_description)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You output strictly valid JSON without markdown wrapping."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        result_text = response.choices[0].message.content
        return json.loads(result_text)
    except Exception as exc:
        raise RuntimeError(f"AI Analysis Failed: {exc}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_cover_letter(resume_text: str, job_desc: str) -> str:
    """
    Uses Groq (Llama-3) to write a highly customized cover letter based on the resume and job description.
    """
    from django.conf import settings

    api_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key)

    system_prompt = build_cover_letter_system_prompt()
    user_prompt = build_cover_letter_user_prompt(resume_text, job_desc)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )

    return response.choices[0].message.content.strip()
