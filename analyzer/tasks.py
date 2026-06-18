import sys
import traceback
from .models import ResumeAnalysis
from .utils import analyze_with_ai

def process_resume_analysis(analysis_id: int):
    """
    Background task to process a resume.
    """
    try:
        analysis_record = ResumeAnalysis.objects.get(id=analysis_id)
        analysis_record.status = 'processing'
        analysis_record.save()

        # Decrypt text to run analysis
        resume_text = analysis_record.resume_text
        job_desc = analysis_record.job_desc_full

        analysis_data, usage_data = analyze_with_ai(resume_text, job_desc)

        # Update record with results
        analysis_record.prompt_tokens = usage_data.get("prompt_tokens", 0)
        analysis_record.completion_tokens = usage_data.get("completion_tokens", 0)

        # Update record with results
        analysis_record.match_score = analysis_data.get("match_score", 0)
        analysis_record.matched_skills = analysis_data.get("matched_skills", [])
        analysis_record.missing_skills = analysis_data.get("missing_skills", [])
        analysis_record.experience_gaps = analysis_data.get("experience_gaps", [])
        analysis_record.suggestions = analysis_data.get("suggestions", [])
        analysis_record.upskill_paths = analysis_data.get("upskill_paths", [])
        analysis_record.impact_critiques = analysis_data.get("impact_critiques", [])
        analysis_record.interview_questions = analysis_data.get("interview_questions", [])
        
        analysis_record.status = 'completed'
        analysis_record.save()

    except Exception as exc:
        print(f"[analyzer.tasks] AI processing error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if 'analysis_record' in locals():
            analysis_record.status = 'error'
            analysis_record.save()
        raise
