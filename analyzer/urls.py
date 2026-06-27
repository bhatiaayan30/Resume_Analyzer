from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("analyze/", views.analyze, name="analyze"),
    path("analysis-status/<uuid:analysis_id>/", views.analysis_status, name="analysis_status"),
    path("results/<uuid:analysis_id>/", views.analysis_results, name="analysis_results"),
    path("history/", views.history, name="history"),
    path("history/compare/", views.compare_versions_view, name="compare_versions"),
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
    path("payment-failed/", views.payment_failed, name="payment_failed"),
    path("contact/", views.contact_view, name="contact"),
    
    # Secondary Email management paths
    path("api/secondary-email/add/", views.add_secondary_email, name="add_secondary_email"),
    path("api/secondary-email/delete/", views.delete_secondary_email, name="delete_secondary_email"),
    path("api/secondary-email/make-primary/", views.make_secondary_email_primary, name="make_secondary_email_primary"),
    path("api/secondary-email/request-otp/", views.request_secondary_otp, name="request_secondary_otp"),
    path("api/secondary-email/verify-otp/", views.verify_secondary_otp, name="verify_secondary_otp"),
    
    # New Premium Features
    path("interview/start/<uuid:analysis_id>/", views.start_interview_api, name="start_interview_api"),
    path("interview/send/<int:session_id>/", views.send_interview_message_api, name="send_interview_message_api"),
    path("bullet-rewrite/<uuid:analysis_id>/", views.suggest_bullet_rewrite_api, name="suggest_bullet_rewrite_api"),
    path("recalculate-score/<uuid:analysis_id>/", views.recalculate_score_api, name="recalculate_score_api"),
    path("export-resume/<uuid:analysis_id>/", views.export_resume_pdf, name="export_resume_pdf"),
    path("portfolio/<uuid:analysis_id>/", views.portfolio_view, name="portfolio_view"),
    path("portfolio/export/<uuid:analysis_id>/", views.export_portfolio_html, name="export_portfolio_html"),
    path("api/localize/<uuid:analysis_id>/", views.localize_resume_api, name="localize_resume_api"),
    
    # Resume Builder Wizard
    path("builder/", views.resume_builder_view, name="resume_builder"),
    path("api/builder/parse-upload/", views.parse_resume_for_builder_api, name="parse_resume_for_builder_api"),
    path("api/builder/save/", views.save_builder_resume_api, name="save_builder_resume_api"),
    path("api/builder/suggest-summary/", views.suggest_summary_api, name="suggest_summary_api"),
    path("api/builder/suggest-bullets/", views.suggest_bullets_api, name="suggest_bullets_api"),
    
    # Vet and Hire Inspired Premium Features
    path("features/authenticity-audit/", views.authenticity_audit_view, name="authenticity_audit"),
    path("features/screening-room/", views.screening_room_view, name="screening_room"),
    path("features/auto-vet/", views.auto_vet_view, name="auto_vet"),
    path("features/skills-gap/", views.skills_gap_view, name="skills_gap"),
    path("features/chrome-extension/", views.chrome_extension_view, name="chrome_extension"),
    
    # Blog Section
    path("blog/", views.blog_index, name="blog_index"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    path("why-us/", views.why_us_view, name="why_us"),
]


