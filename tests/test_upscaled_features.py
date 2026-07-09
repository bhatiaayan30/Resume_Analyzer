import json
import datetime
from unittest.mock import MagicMock, patch
import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory
from django.urls import reverse

from analyzer.models import ResumeAnalysis, InterviewSession, InterviewMessage, LocalizedResume
from analyzer.authenticity_engine import parse_single_date, run_chronological_checks, audit_authenticity
from analyzer.views import (
    get_premium_permissions,
    portfolio_view,
    export_portfolio_html,
    start_interview_api,
    send_interview_message_api,
)

@pytest.fixture
def factory():
    return RequestFactory()

@pytest.fixture
def guest_analysis_record():
    return ResumeAnalysis.objects.create(
        user=None,
        filename="guest_resume.pdf",
        resume_text="Guest candidate resume text.",
        job_desc_full="Job requiring Python.",
        job_desc_snippet="Job requiring Python.",
        status="completed",
        match_score=65,
        structured_resume={
            "name": "Guest Candidate",
            "contact": {"email": "guest@example.com"},
            "experience": [{"role": "Developer", "company": "Company A", "duration": "June 2021 - Present", "bullets": ["Built Python apps"]}],
            "skills": {"languages": ["Python"]}
        }
    )

# ──────────────────────────────────────────────────────────────
# 1. Date Parsing Tests
# ──────────────────────────────────────────────────────────────
def test_parse_single_date_iso_and_abbreviations():
    # ISO formats
    d1 = parse_single_date("2021-06")
    assert d1 == datetime.date(2021, 6, 1)

    d2 = parse_single_date("2020/03")
    assert d2 == datetime.date(2020, 3, 1)

    # Abbreviations
    d3 = parse_single_date("sept 2022")
    assert d3 == datetime.date(2022, 9, 1)

    # Fallback to year only
    d4 = parse_single_date("2023")
    assert d4 == datetime.date(2023, 1, 1)

# ──────────────────────────────────────────────────────────────
# 2. Chronological Overlap Exclusions
# ──────────────────────────────────────────────────────────────
def test_chronological_overlap_exclusions():
    # 1. Non-conflicting (Internship / Freelance)
    experience_non_conflict = [
        {
            "role": "Software Intern",
            "company": "Company A",
            "duration": "June 2021 - Dec 2021",
            "bullets": ["Did intern work"]
        },
        {
            "role": "Freelance Developer",
            "company": "Self-employed",
            "duration": "July 2021 - Present",
            "bullets": ["Wrote freelance code"]
        }
    ]
    checks_non_conflict = run_chronological_checks(experience_non_conflict)
    issues_non_conflict = [c["issue"] for c in checks_non_conflict]
    assert "Timeline Overlap" not in issues_non_conflict

    # 2. Conflicting (Two full-time senior/lead roles)
    experience_conflict = [
        {
            "role": "Lead Architect",
            "company": "Company A",
            "duration": "June 2021 - Dec 2021",
            "bullets": ["Led architecture"]
        },
        {
            "role": "Senior Engineer",
            "company": "Company B",
            "duration": "July 2021 - Present",
            "bullets": ["Built senior systems"]
        }
    ]
    checks_conflict = run_chronological_checks(experience_conflict)
    issues_conflict = [c["issue"] for c in checks_conflict]
    assert "Timeline Overlap" in issues_conflict

# ──────────────────────────────────────────────────────────────
# 3. Phrasing Check false-positive mitigation
# ──────────────────────────────────────────────────────────────
def test_ai_phrasing_false_positive_mitigation():
    # Short text with high density buzzwords (e.g. 15 words, 2 buzzwords)
    short_text = "We delve deep to leverage a robust tapestry of spearheaded synergy."
    # With 11 words, 5 buzzwords: density = (5/11)*1000 = 454
    # Without scaling, kw_prob would be 85%
    # With scaling, kw_prob should be capped at 45% because total word count is < 100
    
    audit = audit_authenticity(short_text, {})
    assert audit["ai_probability"] <= 45

    # Short uniform bullets mean word count check
    # 4 bullets of 4 words each (uniform length, std_dev = 0)
    # Average bullet length = 4 words (< 8)
    # So it should NOT flag "Hyper-uniform bullet point lengths"
    structured_resume = {
        "experience": [
            {
                "role": "Developer",
                "bullets": [
                    "Wrote python backend code",
                    "Fixed database query bugs",
                    "Deployed serverless cloud services",
                    "Helped team members succeed"
                ]
            }
        ]
    }
    audit_bullets = audit_authenticity("Some random text with length above 100 " * 20, structured_resume)
    evidence_strings = " ".join(audit_bullets["ai_probability_evidence"])
    assert "Hyper-uniform bullet point lengths" not in evidence_strings

# ──────────────────────────────────────────────────────────────
# 4. Guest Permissions & Views
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_guest_permissions_unauthenticated(guest_analysis_record):
    anon_user = AnonymousUser()
    perms = get_premium_permissions(anon_user, guest_analysis_record)
    assert perms["can_download_pdf"] is True
    assert perms["can_cover_letter"] is True
    assert perms["can_interview"] is True

@pytest.mark.django_db
def test_guest_permissions_authenticated(guest_analysis_record):
    user = User.objects.create_user(username="normaluser", password="password")
    perms = get_premium_permissions(user, guest_analysis_record)
    assert perms["can_download_pdf"] is True
    assert perms["can_cover_letter"] is True
    assert perms["can_interview"] is True

@pytest.mark.django_db
def test_guest_portfolio_view_no_lock(factory, guest_analysis_record):
    url = reverse("portfolio_view", kwargs={"analysis_id": guest_analysis_record.slug})
    request = factory.get(url)
    request.user = AnonymousUser()

    response = portfolio_view(request, analysis_id=guest_analysis_record.slug)
    assert response.status_code == 200
    assert b"Guest Candidate" in response.content
    assert b"Premium Web Portfolio" not in response.content # Lock screen should not be active

@pytest.mark.django_db
def test_guest_portfolio_export_html(factory, guest_analysis_record):
    url = reverse("export_portfolio_html", kwargs={"analysis_id": guest_analysis_record.slug})
    request = factory.get(url)
    request.user = AnonymousUser()

    response = export_portfolio_html(request, analysis_id=guest_analysis_record.slug)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/html"
    assert b"Guest Candidate" in response.content

# ──────────────────────────────────────────────────────────────
# 5. Guest Mock Interview Session
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.utils.Groq")
def test_guest_mock_interview_flow(mock_groq_class, factory, guest_analysis_record):
    mock_client = mock_groq_class.return_value
    
    mock_response_question = MagicMock()
    mock_response_question.choices[0].message.content = "What Python framework do you prefer?"
    
    mock_response_eval = MagicMock()
    mock_response_eval.choices[0].message.content = '{"score": 85, "feedback": "Great framework preference."}'
    
    mock_client.chat.completions.create.side_effect = [
        mock_response_question,
        mock_response_eval,
        mock_response_question,
    ]

    # Start Interview as Guest
    url_start = reverse("start_interview_api", kwargs={"analysis_id": guest_analysis_record.slug})
    request_start = factory.post(url_start)
    request_start.user = AnonymousUser()

    response_start = start_interview_api(request_start, analysis_id=guest_analysis_record.slug)
    assert response_start.status_code == 200
    data_start = json.loads(response_start.content)
    assert "session_id" in data_start
    session_id = data_start["session_id"]

    # Verify session in DB has user=None
    session_db = InterviewSession.objects.get(id=session_id)
    assert session_db.user is None

    # Reply/Send message as Guest
    url_send = reverse("send_interview_message_api", kwargs={"session_id": session_id})
    request_send = factory.post(
        url_send,
        json.dumps({"message": "I prefer using Django for rapid development."}),
        content_type="application/json"
    )
    request_send.user = AnonymousUser()

    response_send = send_interview_message_api(request_send, session_id=session_id)
    assert response_send.status_code == 200
    data_send = json.loads(response_send.content)
    assert len(data_send["messages"]) == 3
    assert data_send["messages"][1]["sender"] == "user"
    assert data_send["messages"][1]["score"] == 85
    assert data_send["messages"][1]["feedback"] == "Great framework preference."
