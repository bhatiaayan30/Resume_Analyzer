import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_analyzer.settings')
django.setup()
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm

# Cleanup any existing test user
User.objects.filter(username='testuser').delete()
# Create test user
User.objects.create_user('testuser', 'test@example.com', 'password123')

form = PasswordResetForm({'email': 'test@example.com'})
print('valid' if form.is_valid() else 'invalid')
if form.is_valid():
    form.save(
        request=None,
        use_https=False,
        from_email=None,
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
    )
