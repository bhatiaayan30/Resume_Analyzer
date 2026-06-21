from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("analyze/", views.analyze, name="analyze"),
    path("analysis-status/<uuid:analysis_id>/", views.analysis_status, name="analysis_status"),
    path("results/<uuid:analysis_id>/", views.analysis_results, name="analysis_results"),
    path("history/", views.history, name="history"),
    path("history/delete/<uuid:analysis_id>/", views.delete_analysis, name="delete_analysis"),
    path("settings/", views.settings_view, name="settings"),
    path("signup/", views.signup_view, name="signup"),
    path(
        "generate-cover-letter/<uuid:analysis_id>/",
        views.generate_cover_letter_api,
        name="generate_cover_letter",
    ),
    path(
        "export-cover-letter/<uuid:analysis_id>/",
        views.export_cover_letter_pdf,
        name="export_cover_letter_pdf",
    ),
    path(
        "export-report/<uuid:analysis_id>/",
        views.export_report_pdf,
        name="export_report_pdf",
    ),
    path("pricing/", views.pricing_view, name="pricing"),
    path("create-razorpay-order/", views.create_razorpay_order, name="create_razorpay_order"),
    path("api/verify-coupon/", views.verify_coupon, name="verify_coupon"),
    path("webhook/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),
    path("api/analyze/", views.api_analyze, name="api_analyze"),
    path("insights/", views.market_insights, name="market_insights"),
    path("api/request-otp/", views.request_otp, name="request_otp"),
    path("api/verify-otp/", views.verify_otp, name="verify_otp"),
]
