import json
from unittest.mock import MagicMock, patch
import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from analyzer.models import ResumeAnalysis, InterviewSession, InterviewMessage
from analyzer.views import (
    generate_cover_letter_api,
    start_interview_api,
    send_interview_message_api,
    suggest_bullet_rewrite_api,
    recalculate_score_api,
    export_resume_pdf,
)

@pytest.fixture
def factory():
    return RequestFactory()

@pytest.fixture
def premium_user():
    user = User.objects.create_user(username="premiumuser", password="password")
    user.profile.is_premium = True
    user.profile.subscription_tier = 3 # Elite tier (can access all premium features)
    user.profile.save()
    return user

@pytest.fixture
def analysis_record(premium_user):
    return ResumeAnalysis.objects.create(
        user=premium_user,
        filename="resume.pdf",
        resume_text="John Doe\nPython Developer\nSkills: Python, SQL",
        job_desc_full="We need a Python Backend Developer.",
        job_desc_snippet="Python Backend Developer",
        status="completed",
        match_score=60
    )

# ──────────────────────────────────────────────────────────────
# 1. Cover Letter Customization Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.utils.Groq")
def test_generate_cover_letter_customized(mock_groq_class, factory, premium_user, analysis_record):
    mock_client = mock_groq_class.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "This is a customized bold and short cover letter."
    mock_client.chat.completions.create.return_value = mock_response

    url = reverse("generate_cover_letter", kwargs={"analysis_id": analysis_record.slug})
    request = factory.post(
        url,
        json.dumps({
            "tone": "Bold",
            "length": "Short",
            "highlights": "Led cloud migration",
            "force_regenerate": True
        }),
        content_type="application/json"
    )
    request.user = premium_user
    
    response = generate_cover_letter_api(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "cover_letter" in data
    assert "customized bold and short" in data["cover_letter"]

# ──────────────────────────────────────────────────────────────
# 2. Bullet Point Rewriter Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.utils.Groq")
def test_suggest_bullet_rewrite(mock_groq_class, factory, premium_user, analysis_record):
    mock_client = mock_groq_class.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '["Rewrite 1", "Rewrite 2", "Rewrite 3"]'
    mock_client.chat.completions.create.return_value = mock_response

    url = reverse("suggest_bullet_rewrite_api", kwargs={"analysis_id": analysis_record.slug})
    request = factory.post(
        url,
        json.dumps({"bullet_point": "I wrote python code"}),
        content_type="application/json"
    )
    request.user = premium_user

    response = suggest_bullet_rewrite_api(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "suggestions" in data
    assert len(data["suggestions"]) == 3
    assert data["suggestions"][0] == "Rewrite 1"

# ──────────────────────────────────────────────────────────────
# 3. Interview Session & Message Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.utils.Groq")
def test_interview_flow(mock_groq_class, factory, premium_user, analysis_record):
    mock_client = mock_groq_class.return_value
    
    # Mock first question generation
    mock_response_question = MagicMock()
    mock_response_question.choices[0].message.content = "What is your experience with Django?"
    
    # Mock feedback scoring evaluation
    mock_response_eval = MagicMock()
    mock_response_eval.choices[0].message.content = '{"score": 90, "feedback": "Excellent answer."}'
    
    mock_client.chat.completions.create.side_effect = [
        mock_response_question, # For starting interview
        mock_response_eval,     # For evaluating answer
        mock_response_question, # For generating next question after reply
    ]

    # Start Interview
    url_start = reverse("start_interview_api", kwargs={"analysis_id": analysis_record.slug})
    request_start = factory.post(url_start)
    request_start.user = premium_user
    
    response_start = start_interview_api(request_start, analysis_id=analysis_record.slug)
    assert response_start.status_code == 200
    data_start = json.loads(response_start.content)
    assert "session_id" in data_start
    assert len(data_start["messages"]) == 1
    assert data_start["messages"][0]["sender"] == "ai"
    assert data_start["messages"][0]["message"] == "What is your experience with Django?"

    session_id = data_start["session_id"]

    # Send message / reply
    url_send = reverse("send_interview_message_api", kwargs={"session_id": session_id})
    request_send = factory.post(
        url_send,
        json.dumps({"message": "I have built 3 websites with Django"}),
        content_type="application/json"
    )
    request_send.user = premium_user

    response_send = send_interview_message_api(request_send, session_id=session_id)
    assert response_send.status_code == 200
    data_send = json.loads(response_send.content)
    # History now: AI Q1, User A1, AI Q2
    assert len(data_send["messages"]) == 3
    user_msg = data_send["messages"][1]
    assert user_msg["sender"] == "user"
    assert user_msg["score"] == 90
    assert user_msg["feedback"] == "Excellent answer."

# ──────────────────────────────────────────────────────────────
# 4. Recalculate Match Score Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.tasks.analyze_with_ai")
def test_recalculate_score(mock_analyze_with_ai, factory, premium_user, analysis_record):
    # Mock the full AI re-evaluation
    mock_analyze_with_ai.return_value = (
        {
            "job_category": "Software Engineering",
            "match_score": 85,
            "matched_skills": [{"skill": "Python", "category": "hard", "matched": True}],
            "missing_skills": [],
            "experience_gaps": [],
            "suggestions": ["Add cloud skills"],
            "upskill_paths": [],
            "impact_critiques": [],
            "interview_questions": []
        },
        {"prompt_tokens": 120, "completion_tokens": 80}
    )

    url = reverse("recalculate_score_api", kwargs={"analysis_id": analysis_record.slug})
    request = factory.post(
        url,
        json.dumps({"resume_text": "Updated resume text with Python, SQL and Django."}),
        content_type="application/json"
    )
    request.user = premium_user

    response = recalculate_score_api(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert data["match_score"] == 85
    
    # Verify in DB
    analysis_record.refresh_from_db()
    assert analysis_record.match_score == 85
    assert "Updated resume text" in analysis_record.resume_text

# ──────────────────────────────────────────────────────────────
# 5. Premium PDF Export Templates Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_export_resume_pdf_templates(factory, premium_user, analysis_record):
    # Cache structured resume to avoid AI parser execution
    analysis_record.structured_resume = {
        "name": "John Doe",
        "contact": {"email": "john@example.com"},
        "experience": [{"role": "Python Dev", "company": "Acme", "duration": "1 year", "bullets": ["Built Python apps"]}],
        "education": [],
        "skills": {"languages": ["Python"]}
    }
    analysis_record.save()

    for layout in ["minimal", "executive", "modern"]:
        url = reverse("export_resume_pdf", kwargs={"analysis_id": analysis_record.slug}) + f"?template={layout}"
        request = factory.get(url)
        request.user = premium_user

        response = export_resume_pdf(request, analysis_id=analysis_record.slug)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert f"Optimized_Resume_{layout}.pdf" in response["Content-Disposition"]
