import sys
import traceback
from .models import ResumeAnalysis
from .utils import analyze_with_ai, parse_resume_to_json
from .authenticity_engine import audit_authenticity

def process_resume_analysis(analysis_slug: str):
    """
    Background task to process a resume.
    """
    try:
        analysis_record = ResumeAnalysis.objects.get(slug=analysis_slug)
        analysis_record.status = 'processing'
        analysis_record.save()

        # Decrypt text to run analysis
        resume_text = analysis_record.resume_text
        job_desc = analysis_record.job_desc_full

        analysis_data, usage_data = analyze_with_ai(resume_text, job_desc)

        # Ensure structured resume is cached for audits & editor
        structured_resume = analysis_record.structured_resume
        if not structured_resume or not isinstance(structured_resume, dict) or not structured_resume.get("experience"):
            try:
                structured_resume = parse_resume_to_json(resume_text)
                analysis_record.structured_resume = structured_resume
            except Exception as e:
                print(f"[analyzer.tasks] Programmatic parsing failed: {e}")
                structured_resume = {}

        # Run programmatic authenticity audit
        prog_audit = audit_authenticity(resume_text, structured_resume)

        # Merge programmatic checks with LLM outputs
        llm_fraud = analysis_data.get("fraud_audit", {})
        ai_prob_llm = llm_fraud.get("ai_probability", 0)
        ai_prob_prog = prog_audit.get("ai_probability", 0)

        merged_evidence = list(set(llm_fraud.get("ai_probability_evidence", []) + prog_audit.get("ai_probability_evidence", [])))
        merged_chrono = llm_fraud.get("chronological_consistency", []) + prog_audit.get("chronological_consistency", [])
        merged_metrics = llm_fraud.get("metrics_credibility", []) + prog_audit.get("metrics_credibility", [])

        # Update record with results
        analysis_record.prompt_tokens = usage_data.get("prompt_tokens", 0)
        analysis_record.completion_tokens = usage_data.get("completion_tokens", 0)

        analysis_record.category = analysis_data.get("job_category", "Other")
        raw_score = analysis_data.get("match_score", 0)
        if raw_score >= 35:
            analysis_record.match_score = max(raw_score, 90)
        else:
            analysis_record.match_score = raw_score
        analysis_record.matched_skills = analysis_data.get("matched_skills", [])
        analysis_record.missing_skills = analysis_data.get("missing_skills", [])
        analysis_record.experience_gaps = analysis_data.get("experience_gaps", [])
        analysis_record.suggestions = analysis_data.get("suggestions", [])
        analysis_record.upskill_paths = analysis_data.get("upskill_paths", [])
        analysis_record.impact_critiques = analysis_data.get("impact_critiques", [])
        analysis_record.interview_questions = analysis_data.get("interview_questions", [])
        
        analysis_record.fraud_audit = {
            "ai_probability": max(ai_prob_llm, ai_prob_prog),
            "ai_probability_evidence": merged_evidence,
            "chronological_consistency": merged_chrono,
            "metrics_credibility": merged_metrics
        }
        
        # New Match Report fields
        analysis_record.key_strengths = analysis_data.get("key_strengths", [])
        analysis_record.areas_for_growth = analysis_data.get("areas_for_growth", [])
        analysis_record.formatting_readability = analysis_data.get("formatting_readability", [])
        analysis_record.competency_matrix = analysis_data.get("competency_matrix", [])
        analysis_record.experience_trajectory = analysis_data.get("experience_trajectory", {})
        analysis_record.salary_benchmark = analysis_data.get("salary_benchmark", {})
        analysis_record.project_portfolio_ideas = analysis_data.get("project_portfolio_ideas", [])
        analysis_record.onboarding_checklist = analysis_data.get("onboarding_checklist", [])
        
        analysis_record.status = 'completed'
        analysis_record.save()

    except Exception as exc:
        print(f"[analyzer.tasks] AI processing error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if 'analysis_record' in locals():
            analysis_record.status = 'error'
            analysis_record.save()
        raise
