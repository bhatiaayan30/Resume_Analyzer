import os
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resume_analyzer.settings")
app = get_wsgi_application()

try:
    call_command('migrate', interactive=False)
except Exception as e:
    print(f"Migration failed during Vercel startup: {e}")
