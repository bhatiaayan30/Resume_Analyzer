"""
models.py — database models for the analyzer app.

ResumeAnalysis is a Step 5 addition (history feature).
The core app (Steps 1-4) works without it — add the migration
once the basic flow is working.
"""

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from .fields import EncryptedTextField

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_premium = models.BooleanField(default=False)
    subscription_tier = models.IntegerField(default=0) # 0=Free, 1=Tier1, 2=Tier2, 3=Tier3, 4=Tier4
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    razorpay_customer_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    has_used_free_trial = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    profile.save()



class Persona(models.Model):
    """Different target roles for a user (e.g., Backend, Frontend)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class JobDescription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    full_text = EncryptedTextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ResumeVersion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    persona = models.ForeignKey(Persona, on_delete=models.SET_NULL, null=True, blank=True)
    filename = models.CharField(max_length=255)
    # Encrypted plain text extracted from the resume
    encrypted_text = EncryptedTextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ResumeAnalysis(models.Model):
    """
    Stores the result of each AI analysis so users can
    browse their history without re-uploading.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    filename = models.CharField(max_length=255)
    
    # Async processing status
    status = models.CharField(max_length=20, default='pending') # pending, processing, completed, error

    # Raw text used for generating cover letters later - Now Encrypted
    resume_text = EncryptedTextField(blank=True)
    job_desc_full = EncryptedTextField(blank=True)
    cover_letter = EncryptedTextField(blank=True)
    job_desc_snippet = models.CharField(max_length=200, blank=True)

    # Links to expanded schema
    resume_version = models.ForeignKey(ResumeVersion, on_delete=models.SET_NULL, null=True, blank=True)
    job_description = models.ForeignKey(JobDescription, on_delete=models.SET_NULL, null=True, blank=True)

    # AI results — stored as JSON arrays
    match_score = models.IntegerField(default=0)
    matched_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    experience_gaps = models.JSONField(default=list)
    suggestions = models.JSONField(default=list)
    upskill_paths = models.JSONField(default=list)
    ats_format_issues = models.JSONField(default=list)
    searchability_checks = models.JSONField(default=list)
    impact_critiques = models.JSONField(default=list)
    interview_questions = models.JSONField(default=list, blank=True)
    
    # Token Tracking
    prompt_tokens = models.IntegerField(default=0, blank=True, null=True)
    completion_tokens = models.IntegerField(default=0, blank=True, null=True)
    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} — {self.match_score}% match ({self.created_at:%Y-%m-%d %H:%M})"


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.IntegerField(help_text="Discount percentage (0-100)")
    max_uses = models.IntegerField(default=100, help_text="Maximum number of times this coupon can be used")
    uses = models.IntegerField(default=0, help_text="Number of times this coupon has been used")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return self.is_active and self.uses < self.max_uses

    def __str__(self):
        return f"{self.code} - {self.discount_percent}%"
