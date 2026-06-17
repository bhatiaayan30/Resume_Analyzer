"""
utils.py — business logic for the Resume Analyzer.

Keeping extraction + AI logic here (not in views.py) means
these functions can be tested independently without HTTP.

Usage:
    from analyzer.utils import extract_text, analyze_with_ai
"""

import json
import os

import fitz  # PyMuPDF
import pdfplumber
from docx import Document
from groq import Groq

# ──────────────────────────────────────────────────────────────
# Text extraction
# ──────────────────────────────────────────────────────────────


def extract_text(file_obj, ext: str) -> str:
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


def analyze_with_ai(resume_text: str, job_description: str) -> dict:
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


    # ── Sanitize Inputs (Prevent Prompt Injection) ─────────────
    safe_resume_text = resume_text.replace("<", "[").replace(">", "]")
    safe_job_desc = job_description.replace("<", "[").replace(">", "]")

    prompt = f"""
    You are an expert ATS (Applicant Tracking System) simulator and elite technical recruiter.
    Analyze the following resume against the job description using advanced semantic matching (do not rely purely on exact keywords, understand synonyms and context).
    
    Identify:
    - Overused words, passive voice, and weak verbs in the Experience section.
    - Lack of quantification (metrics, numbers) in achievements.
    - Generate 10 to 15 highly tailored interview questions covering technical skills, behavioral situations, and experience gaps.
    
    Return ONLY a JSON object exactly matching this schema:
    {{
        "match_score": <integer 0-100, calculate a weighted score based on skills, experience overlap, and formatting>,
        "matched_skills": [<list of strings>],
        "missing_skills": [<list of strings>],
        "experience_gaps": [<list of strings>],
        "impact_critiques": [
            {{"section": "Summary/Experience", "original_bullet": "string of original weak bullet point", "critique": "string identifying weak verbs, passive voice, or lack of metrics", "suggested_rewrite": "string of rewritten high-impact bullet point"}}
        ],
        "suggestions": [<list of strings for overall improvement>],
        "upskill_paths": [
            {{"skill": "string", "learning_strategy": "string detailing how to learn this skill", "recommended_resources": [{{"name": "string resource name", "url": "string URL to the resource"}}]}}
        ],
        "interview_questions": [
            {{"question": "string containing a tailored interview question based on the resume and JD", "answer": "detailed string with key points the candidate should cover"}}
        ]
    }}

    Job Description:
    {safe_job_desc[:10000]}

    Resume:
    {safe_resume_text[:30000]}
    """

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


def generate_cover_letter(resume_text: str, job_desc: str) -> str:
    """
    Uses Groq (Llama-3) to write a highly customized cover letter based on the resume and job description.
    """
    from django.conf import settings

    api_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key)

    system_prompt = (
        "You are an expert career coach and executive resume writer. "
        "Your task is to write a highly professional, modern, and engaging cover letter. "
        "Focus on bridging the gap between the candidate's existing experience and the job description. "
        "Do NOT use generic templates like 'To whom it may concern'. "
        "Ensure the tone is confident but not arrogant. "
        "Output ONLY the text of the cover letter. Do not include any Markdown blocks, just the raw text."
    )

    user_prompt = f"""
    --- RESUME ---
    {resume_text}

    --- JOB DESCRIPTION ---
    {job_desc}

    Write the cover letter now:
    """

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
