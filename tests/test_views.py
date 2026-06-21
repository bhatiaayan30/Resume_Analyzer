import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory
from django.urls import reverse

from analyzer.views import index, signup_view, payment_failed


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.mark.django_db
def test_landing_page_anonymous(factory):
    """Anonymous users should see the landing page."""
    request = factory.get(reverse("index"))
    request.user = AnonymousUser()
    response = index(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_authenticated(factory):
    """Authenticated users should see the dashboard form."""
    user = User.objects.create_user(username="testuser", password="password")
    request = factory.get(reverse("index"))
    request.user = user
    response = index(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_view_get(factory):
    """Sign up page should return 200."""
    request = factory.get(reverse("signup"))
    response = signup_view(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_payment_failed_view(factory):
    """Payment failed page should return 200 with error information."""
    request = factory.get(reverse("payment_failed") + "?error=Insufficient%20funds&code=BAD_FUNDS&order_id=ord_123&payment_id=pay_456")
    request.user = AnonymousUser()
    response = payment_failed(request)
    assert response.status_code == 200
    assert b"Insufficient funds" in response.content
    assert b"BAD_FUNDS" in response.content
    assert b"ord_123" in response.content
    assert b"pay_456" in response.content


@pytest.mark.django_db
def test_free_tier_monthly_limit(factory):
    """A basic free user (tier 0) is allowed 2 scans/month and blocked on the 3rd."""
    from analyzer.views import analyze
    from analyzer.models import ResumeAnalysis
    user = User.objects.create_user(username="freeuser", password="password")
    
    # Create 2 scans in the last 30 days
    ResumeAnalysis.objects.create(user=user, filename="res1.pdf", status="completed", match_score=70)
    ResumeAnalysis.objects.create(user=user, filename="res2.pdf", status="completed", match_score=75)
    
    # Request a 3rd scan
    from django.core.files.uploadedfile import SimpleUploadedFile
    pdf_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test resume data here")
    
    request = factory.post(reverse("analyze"), {
        "resume_input_type": "file",
        "resume": pdf_file,
        "job_description": "We need a Software Engineer with Python skills.",
    })
    request.user = user
    request.session = {}
    request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    
    response = analyze(request)
    assert response.status_code == 403
    import json
    data = json.loads(response.content)
    assert data["status"] == "limit_reached"


