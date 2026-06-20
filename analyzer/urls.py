from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("analyze/", views.analyze, name="analyze"),
    path("analysis-status/<int:analysis_id>/", views.analysis_status, name="analysis_status"),
    path("results/<int:analysis_id>/", views.analysis_results, name="analysis_results"),
    path("history/", views.history, name="history"),
    path("history/delete/<int:analysis_id>/", views.delete_analysis, name="delete_analysis"),
    path("signup/", views.signup_view, name="signup"),
    path(
        "generate-cover-letter/<int:analysis_id>/",
        views.generate_cover_letter_api,
        name="generate_cover_letter",
    ),
    path(
        "export-cover-letter/<int:analysis_id>/",
        views.export_cover_letter_pdf,
        name="export_cover_letter_pdf",
    ),
    path(
        "export-report/<int:analysis_id>/",
        views.export_report_pdf,
        name="export_report_pdf",
    ),
    path("pricing/", views.pricing_view, name="pricing"),
    path("create-razorpay-order/", views.create_razorpay_order, name="create_razorpay_order"),
    path("webhook/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),
    path("api/analyze/", views.api_analyze, name="api_analyze"),
]
