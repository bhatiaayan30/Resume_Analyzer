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

