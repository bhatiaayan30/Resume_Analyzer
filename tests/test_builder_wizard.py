import json
from unittest.mock import MagicMock, patch
import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from analyzer.models import ResumeAnalysis, ResumeVersion
from analyzer.views import (
    resume_builder_view,
    save_builder_resume_api,
    suggest_summary_api,
    suggest_bullets_api,
)

@pytest.fixture
def factory():
    return RequestFactory()

@pytest.fixture
def premium_user():
    user = User.objects.create_user(username="wizarduser", password="password")
    user.profile.is_premium = True
    user.profile.save()
    return user

@pytest.fixture
def existing_analysis(premium_user):
    return ResumeAnalysis.objects.create(
        user=premium_user,
        filename="custom_resume",
        resume_text="Hello World",
        status="completed",
        structured_resume={
            "name": "Jane Doe",
            "contact": {"email": "jane@example.com"},
            "summary": "Experienced engineer",
            "experience": [],
            "education": [],
            "skills": {"languages": ["Python"]}
        }
    )

@pytest.mark.django_db
def test_resume_builder_view_renders(factory, premium_user):
    url = reverse("resume_builder")
    request = factory.get(url)
    request.user = premium_user

    response = resume_builder_view(request)
    assert response.status_code == 200
    assert b"Interactive Resume Builder" in response.content

@pytest.mark.django_db
def test_resume_builder_view_with_edit(factory, premium_user, existing_analysis):
    url = reverse("resume_builder") + f"?edit={existing_analysis.slug}"
    request = factory.get(url)
    request.user = premium_user

    response = resume_builder_view(request)
    assert response.status_code == 200
    assert b"Jane Doe" in response.content
    assert b"jane@example.com" in response.content

@pytest.mark.django_db
@patch("analyzer.views.process_resume_analysis")
def test_save_builder_resume_api_valid(mock_process, factory, premium_user):
    url = reverse("save_builder_resume_api")
    payload = {
        "name": "Alex Smith",
        "contact": {
            "email": "alex@example.com",
            "phone": "1234567890",
            "location": "Boston, MA"
        },
        "summary": "Passionate Software Engineer.",
        "experience": [
            {
                "role": "Backend Developer",
                "company": "Tech Corp",
                "duration": "2022 - Present",
                "bullets": ["Designed APIs", "Improved database performance"]
            }
        ],
        "education": [],
        "skills": {
            "languages": ["Python", "SQL"],
            "frameworks": ["Django"],
            "tools": ["Git"],
            "other": []
        }
    }
    
    request = factory.post(
        url,
        json.dumps(payload),
        content_type="application/json"
    )
    request.user = premium_user

    response = save_builder_resume_api(request)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "analysis_id" in data
    assert "redirect_url" in data
    
    # Assert DB entries are created
    analysis = ResumeAnalysis.objects.get(slug=data["analysis_id"])
    assert analysis.user == premium_user
    assert analysis.structured_resume["name"] == "Alex Smith"
    assert "Alex Smith" in analysis.resume_text
    assert "Tech Corp" in analysis.resume_text
    
    version = ResumeVersion.objects.filter(user=premium_user).first()
    assert version is not None
    assert "Alex Smith" in version.encrypted_text

@pytest.mark.django_db
def test_save_builder_resume_api_validation_error(factory, premium_user):
    url = reverse("save_builder_resume_api")
    payload = {
        "contact": {"email": "alex@example.com"}
    }
    request = factory.post(
        url,
        json.dumps(payload),
        content_type="application/json"
    )
    request.user = premium_user

    response = save_builder_resume_api(request)
    assert response.status_code == 400
    data = json.loads(response.content)
    assert "error" in data
    assert "Candidate name is required" in data["error"]

@pytest.mark.django_db
@patch("analyzer.views.get_ai_summary_suggestions")
def test_suggest_summary_api(mock_suggest, factory, premium_user):
    mock_suggest.return_value = ["Summary 1", "Summary 2", "Summary 3"]
    url = reverse("suggest_summary_api")
    request = factory.post(
        url,
        json.dumps({"job_title": "Product Manager", "industry": "Finance"}),
        content_type="application/json"
    )
    request.user = premium_user

    response = suggest_summary_api(request)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "suggestions" in data
    assert len(data["suggestions"]) == 3
    assert data["suggestions"][0] == "Summary 1"
    mock_suggest.assert_called_once_with("Product Manager", "Finance")

@pytest.mark.django_db
@patch("analyzer.views.get_ai_experience_bullets")
def test_suggest_bullets_api(mock_suggest, factory, premium_user):
    mock_suggest.return_value = ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5"]
    url = reverse("suggest_bullets_api")
    request = factory.post(
        url,
        json.dumps({"job_title": "Data Scientist", "company_type": "Retail"}),
        content_type="application/json"
    )
    request.user = premium_user

    response = suggest_bullets_api(request)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "bullets" in data
    assert len(data["bullets"]) == 5
    assert data["bullets"][0] == "Bullet 1"
    mock_suggest.assert_called_once_with("Data Scientist", "Retail")
