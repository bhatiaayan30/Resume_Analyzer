from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots_txt",
    ),
    path(
        "sitemap.xml",
        TemplateView.as_view(template_name="sitemap.xml", content_type="application/xml"),
        name="sitemap_xml",
    ),
    path("admin/", admin.site.urls),
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("allauth.urls")),
    path("", include("analyzer.urls")),
]
