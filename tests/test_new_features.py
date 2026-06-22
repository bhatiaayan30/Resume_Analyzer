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
    portfolio_view,
    export_portfolio_html,
    localize_resume_api,
    compare_versions_view,
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

# ──────────────────────────────────────────────────────────────
# 6. Smart Bullet Validation Output Test
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.utils.Groq")
def test_suggest_bullet_rewrite_validation(mock_groq_class, factory, premium_user, analysis_record):
    mock_client = mock_groq_class.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "validation": {
            "score": 85,
            "action_verb": "Engineered",
            "action_verb_strength": "Strong",
            "has_metrics": True,
            "critique": "Strong bullet point with metrics.",
            "star_situation_task": "Situation clear",
            "star_action": "Action clear",
            "star_result": "Result clear",
            "xyz_accomplished": "Accomplished X",
            "xyz_measured": "Measured Y",
            "xyz_doing": "By doing Z"
        },
        "suggestions": ["Rewrite A", "Rewrite B", "Rewrite C"]
    })
    mock_client.chat.completions.create.return_value = mock_response

    url = reverse("suggest_bullet_rewrite_api", kwargs={"analysis_id": analysis_record.slug})
    request = factory.post(
        url,
        json.dumps({"bullet_point": "Engineered Python systems increasing speed by 50%"}),
        content_type="application/json"
    )
    request.user = premium_user

    response = suggest_bullet_rewrite_api(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "suggestions" in data
    assert "validation" in data
    assert data["validation"]["score"] == 85
    assert data["validation"]["action_verb_strength"] == "Strong"
    assert len(data["suggestions"]) == 3


# ──────────────────────────────────────────────────────────────
# 7. Personal Portfolio Web Generator Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_portfolio_preview_owner(factory, premium_user, analysis_record):
    analysis_record.structured_resume = {
        "name": "John Doe",
        "contact": {"email": "john@example.com"},
        "experience": [{"role": "Python Dev", "company": "Acme", "duration": "1 year", "bullets": ["Built Python apps"]}],
        "education": [{"degree": "B.S.", "institution": "Acme Uni", "school": "Acme Uni", "duration": "4 years"}],
        "skills": {"languages": ["Python"]},
        "projects": [{"name": "My Project", "tech_stack": "Python, Django", "duration": "2 months", "bullets": ["Built something cool"]}],
        "certifications": [{"name": "AWS Certified", "issuer": "AWS", "year": "2025"}],
        "languages_spoken": ["English - Professional"]
    }
    analysis_record.save()

    # Free or premium owner should be able to view their preview
    url = reverse("portfolio_view", kwargs={"analysis_id": analysis_record.slug})
    request = factory.get(url)
    request.user = premium_user
    
    response = portfolio_view(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    assert b"Web Portfolio Preview" in response.content
    assert b"John Doe" in response.content
    assert b"My Project" in response.content
    assert b"AWS Certified" in response.content
    assert b"English - Professional" in response.content

@pytest.mark.django_db
def test_portfolio_preview_public_premium(factory, premium_user, analysis_record):
    # Public recruiter (unauthenticated) viewing a premium user's resume
    url = reverse("portfolio_view", kwargs={"analysis_id": analysis_record.slug})
    request = factory.get(url)
    from django.contrib.auth.models import AnonymousUser
    request.user = AnonymousUser()
    
    response = portfolio_view(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    assert b"John Doe" in response.content
    assert b"Premium Web Portfolio" not in response.content

@pytest.mark.django_db
def test_portfolio_preview_public_free_locked(factory):
    # Public recruiter (unauthenticated) viewing a free user's second resume scan (which is locked)
    free_user = User.objects.create_user(username="freeuser", password="password")
    free_user.profile.is_premium = False
    free_user.profile.subscription_tier = 0
    free_user.profile.save()
    
    # First scan gets the one-time free pass
    ResumeAnalysis.objects.create(
        user=free_user,
        filename="first_free_resume.pdf",
        resume_text="Jane Doe\nFirst Scan",
        status="completed",
        match_score=40
    )
    
    # Second scan is restricted
    free_record = ResumeAnalysis.objects.create(
        user=free_user,
        filename="free_resume.pdf",
        resume_text="Jane Doe\nPython Developer",
        status="completed",
        match_score=50
    )
    
    url = reverse("portfolio_view", kwargs={"analysis_id": free_record.slug})
    request = factory.get(url)
    from django.contrib.auth.models import AnonymousUser
    request.user = AnonymousUser()
    
    response = portfolio_view(request, analysis_id=free_record.slug)
    assert response.status_code == 200
    assert b"Premium Web Portfolio" in response.content # Lock screen active

@pytest.mark.django_db
def test_portfolio_export_html_success(factory, premium_user, analysis_record):
    url = reverse("export_portfolio_html", kwargs={"analysis_id": analysis_record.slug})
    request = factory.get(url)
    request.user = premium_user
    
    response = export_portfolio_html(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/html"
    assert "Portfolio_" in response["Content-Disposition"]
    assert b"John Doe" in response.content


# ──────────────────────────────────────────────────────────────
# 8. AI Resume Translator & Market Localizer Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.views.localize_resume_data")
def test_localize_resume_api(mock_localize, factory, premium_user, analysis_record):
    mock_localize.return_value = {
        "name": "Juan Perez",
        "contact": {"email": "juan@example.com"},
        "summary": "Desarrollador Python en Alemania.",
        "experience": [{"role": "Desarrollador", "company": "Acme", "duration": "1 año", "bullets": ["Creado sistemas de Python"]}],
        "education": [],
        "skills": {"languages": ["Python"]}
    }

    url = reverse("localize_resume_api", kwargs={"analysis_id": analysis_record.slug})
    request = factory.post(
        url,
        json.dumps({"language": "Spanish", "target_market": "Germany"}),
        content_type="application/json"
    )
    request.user = premium_user

    response = localize_resume_api(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "localization_id" in data
    assert data["translated_resume"]["name"] == "Juan Perez"
    assert data["translated_resume"]["summary"] == "Desarrollador Python en Alemania."

@pytest.mark.django_db
def test_export_localized_pdf(factory, premium_user, analysis_record):
    from analyzer.models import LocalizedResume
    loc = LocalizedResume.objects.create(
        analysis=analysis_record,
        language="Spanish",
        target_market="Germany",
        translated_resume={
            "name": "Juan Perez",
            "contact": {"email": "juan@example.com"},
            "experience": [{"role": "Desarrollador", "company": "Acme", "duration": "1 año", "bullets": ["Creado sistemas"]}],
            "education": [],
            "skills": {"languages": ["Python"]}
        }
    )

    url = reverse("export_resume_pdf", kwargs={"analysis_id": analysis_record.slug}) + f"?template=minimal&localization_id={loc.slug}"
    request = factory.get(url)
    request.user = premium_user

    response = export_resume_pdf(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "Optimized_Resume_minimal.pdf" in response["Content-Disposition"]

@pytest.mark.django_db
def test_localized_portfolio_preview(factory, premium_user, analysis_record):
    from analyzer.models import LocalizedResume
    loc = LocalizedResume.objects.create(
        analysis=analysis_record,
        language="Spanish",
        target_market="Germany",
        translated_resume={
            "name": "Juan Perez",
            "contact": {"email": "juan@example.com"},
            "experience": [{"role": "Desarrollador", "company": "Acme", "duration": "1 año", "bullets": ["Creado sistemas"]}],
            "education": [],
            "skills": {"languages": ["Python"]}
        }
    )

    url = reverse("portfolio_view", kwargs={"analysis_id": analysis_record.slug}) + f"?localization_id={loc.slug}"
    request = factory.get(url)
    request.user = premium_user

    response = portfolio_view(request, analysis_id=analysis_record.slug)
    assert response.status_code == 200
    assert b"Juan Perez" in response.content
    assert b"Desarrollador" in response.content


# ──────────────────────────────────────────────────────────────
# 9. Side-by-Side Version Comparison & Diff Tracker Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_compare_versions_view_selection(factory, premium_user, analysis_record):
    url = reverse("compare_versions")
    request = factory.get(url)
    request.user = premium_user
    
    response = compare_versions_view(request)
    assert response.status_code == 200
    assert b"Select Resumes to Compare" in response.content

@pytest.mark.django_db
def test_compare_versions_view_diff(factory, premium_user, analysis_record):
    # Create a second record to compare against
    second_record = ResumeAnalysis.objects.create(
        user=premium_user,
        filename="resume_tailored.pdf",
        resume_text="John Doe\nSenior Python Developer\nSkills: Python, Django, Cloud",
        status="completed",
        match_score=85
    )
    
    url = reverse("compare_versions") + f"?left={analysis_record.slug}&right={second_record.slug}"
    request = factory.get(url)
    request.user = premium_user
    
    response = compare_versions_view(request)
    assert response.status_code == 200
    # Check that both texts and the score gap are passed
    assert b"resume_tailored.pdf" in response.content
    assert b"Senior Python Developer" in response.content
    assert b"+25%" in response.content # 85% - 60% = +25%

@pytest.mark.django_db
def test_compare_versions_view_ownership_safety(factory, premium_user, analysis_record):
    other_user = User.objects.create_user(username="otheruser", password="password")
    other_record = ResumeAnalysis.objects.create(
        user=other_user,
        filename="other.pdf",
        resume_text="Other user resume text.",
        status="completed",
        match_score=40
    )
    
    # Trying to compare ours with someone else's should fail with 404
    url = reverse("compare_versions") + f"?left={analysis_record.slug}&right={other_record.slug}"
    request = factory.get(url)
    request.user = premium_user
    
    from django.http import Http404
    with pytest.raises(Http404):
        compare_versions_view(request)


# ──────────────────────────────────────────────────────────────
# 10. AI Writing & Credential Fraud Scanner Tests
# ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
@patch("analyzer.tasks.analyze_with_ai")
def test_fraud_audit_extraction_and_permissions(mock_analyze_with_ai, factory, premium_user, analysis_record):
    # Mock AI analysis data including fraud_audit
    mock_analyze_with_ai.return_value = (
        {
            "job_category": "Software Engineering",
            "match_score": 85,
            "matched_skills": [{"skill": "Python", "category": "hard", "matched": True}],
            "missing_skills": [],
            "experience_gaps": [],
            "suggestions": [],
            "upskill_paths": [],
            "impact_critiques": [],
            "interview_questions": [],
            "fraud_audit": {
                "ai_probability": 35,
                "ai_probability_evidence": ["Stylistic marker: spearheaded"],
                "chronological_consistency": [
                    {"status": "warning", "issue": "Overlap", "details": "Worked two jobs concurrently."}
                ],
                "metrics_credibility": [
                    {"metric": "Grew userbase by 900%", "credibility": "medium", "critique": "Unusually high growth."}
                ]
            }
        },
        {"prompt_tokens": 100, "completion_tokens": 50}
    )

    from analyzer.tasks import process_resume_analysis
    process_resume_analysis(str(analysis_record.slug))

    analysis_record.refresh_from_db()
    assert analysis_record.fraud_audit["ai_probability"] == 35
    assert analysis_record.fraud_audit["ai_probability_evidence"] == ["Stylistic marker: spearheaded"]
    assert len(analysis_record.fraud_audit["chronological_consistency"]) == 1
    assert analysis_record.fraud_audit["chronological_consistency"][0]["issue"] == "Overlap"

    # Test permissions
    from analyzer.views import get_premium_permissions
    
    # 1. Premium Elite user has access
    perms = get_premium_permissions(premium_user, analysis_record)
    assert perms["can_audit"] is True

    # 2. Regular user with tier 2 (Pro) has access
    pro_user = User.objects.create_user(username="prouser", password="password")
    pro_user.profile.is_premium = True
    pro_user.profile.subscription_tier = 2
    pro_user.profile.save()
    
    analysis_record.user = pro_user
    analysis_record.save()
    perms_pro = get_premium_permissions(pro_user, analysis_record)
    assert perms_pro["can_audit"] is True

    # 3. Regular user with tier 1 (Starter) does not have access
    starter_user = User.objects.create_user(username="starteruser", password="password")
    starter_user.profile.is_premium = True
    starter_user.profile.subscription_tier = 1
    starter_user.profile.save()
    
    # Create a dummy first scan in the past so analysis_record is restricted
    from django.utils import timezone
    dummy_scan = ResumeAnalysis.objects.create(
        user=starter_user,
        filename="dummy_first_scan.pdf",
        resume_text="Starter First Scan",
        status="completed",
        match_score=40
    )
    ResumeAnalysis.objects.filter(id=dummy_scan.id).update(
        created_at=timezone.now() - timezone.timedelta(hours=1)
    )
    
    analysis_record.user = starter_user
    analysis_record.save()
    perms_starter = get_premium_permissions(starter_user, analysis_record)
    assert perms_starter["can_audit"] is False


