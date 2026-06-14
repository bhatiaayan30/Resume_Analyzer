"""
models.py — database models for the analyzer app.

ResumeAnalysis is a Step 5 addition (history feature).
The core app (Steps 1-4) works without it — add the migration
once the basic flow is working.
"""
from django.db import models


from django.contrib.auth.models import User

class ResumeAnalysis(models.Model):
    """
    Stores the result of each AI analysis so users can
    browse their history without re-uploading.
    """
    user              = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    filename          = models.CharField(max_length=255)
    
    # Raw text used for generating cover letters later
    resume_text       = models.TextField(blank=True)
    job_desc_full     = models.TextField(blank=True)
    cover_letter      = models.TextField(blank=True)
    job_desc_snippet  = models.CharField(max_length=200, blank=True)

    # AI results — stored as JSON arrays
    match_score       = models.IntegerField(default=0)
    matched_skills    = models.JSONField(default=list)
    missing_skills    = models.JSONField(default=list)
    experience_gaps   = models.JSONField(default=list)
    suggestions       = models.JSONField(default=list)
    upskill_paths     = models.JSONField(default=list)
    ats_format_issues = models.JSONField(default=list)
    impact_critiques  = models.JSONField(default=list)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.filename} — {self.match_score}% match "
            f"({self.created_at:%Y-%m-%d %H:%M})"
        )
