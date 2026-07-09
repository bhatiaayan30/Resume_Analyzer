import json
from unittest.mock import patch, MagicMock
import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse
from django.http import Http404

from analyzer.models import ResumeAnalysis
from analyzer.views import (
    auto_tailor_resume_api,
    builder_skills_gap_api,
    export_cover_letter_pdf,
)

@pytest.fixture
def factory():
    return RequestFactory()

@pytest.fixture
def premium_user():
    user = User.objects.create_user(username="premuser", password="password")
    user.profile.is_premium = True
    user.profile.save()
    return user

@pytest.fixture
def test_resume_json():
    return {
        "name": "Alex Mercer",
        "contact": {"email": "alex@example.com"},
        "summary": "DevOps Engineer",
        "experience": [
            {
                "role": "Systems Engineer",
                "company": "CloudCorp",
                "duration": "2023 - Present",
                "bullets": ["Maintained AWS infrastructure."]
            }
        ],
        "education": [],
        "skills": {
            "languages": ["Python"],
            "frameworks": [],
            "tools": ["AWS"],
            "other": []
        }
    }

@pytest.mark.django_db
@patch("analyzer.utils.tailor_resume_data")
def test_auto_tailor_resume_api(mock_tailor, factory, premium_user, test_resume_json):
    mock_tailor.return_value = {"summary": "Tailored Summary"}
    
    url = reverse("auto_tailor_resume_api")
    data = {
        "resume": test_resume_json,
        "job_description": "We need a Python developer who knows AWS and Django."
    }
    request = factory.post(url, json.dumps(data), content_type="application/json")
    request.user = premium_user
    
    response = auto_tailor_resume_api(request)
    assert response.status_code == 200
    res_data = json.loads(response.content)
    assert res_data["status"] == "success"
    assert res_data["resume"]["summary"] == "Tailored Summary"

@pytest.mark.django_db
@patch("analyzer.utils.analyze_skills_gap")
def test_builder_skills_gap_api(mock_skills, factory, premium_user, test_resume_json):
    mock_skills.return_value = {
        "fit_score": 85,
        "categories": [],
        "learning_resources": [],
        "pathwayNodes": []
    }
    
    url = reverse("builder_skills_gap_api")
    data = {
        "resume": test_resume_json,
        "job_description": "Python, AWS, Django."
    }
    request = factory.post(url, json.dumps(data), content_type="application/json")
    request.user = premium_user
    
    response = builder_skills_gap_api(request)
    assert response.status_code == 200
    res_data = json.loads(response.content)
    assert res_data["status"] == "success"
    assert res_data["skills_gap"]["fit_score"] == 85

@pytest.mark.django_db
@patch("xhtml2pdf.pisa.CreatePDF")
def test_export_cover_letter_pdf(mock_pisa, factory, premium_user):
    # Mock CreatePDF return value status object
    mock_status = MagicMock()
    mock_status.err = 0
    mock_pisa.return_value = mock_status
    
    # Create resume analysis record
    record = ResumeAnalysis.objects.create(
        user=premium_user,
        filename="prem_resume",
        resume_text="Hello World",
        status="completed",
        cover_letter="Dear Hiring Manager,\nI am writing to express my interest...",
        structured_resume={
            "name": "Alex Mercer",
            "contact": {"email": "alex@example.com"},
            "style": {
                "selectedTemplate": "jakes_resume",
                "fontChoice": "font-inter",
                "textColor": "#1e293b",
                "themeColor": "#7c3aed"
            }
        }
    )
    
    url = reverse("export_cover_letter_pdf", kwargs={"analysis_id": record.slug})
    request = factory.get(url)
    request.user = premium_user
    
    response = export_cover_letter_pdf(request, analysis_id=record.slug)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
