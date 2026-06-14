# Resume Analyzer — Django + Python + OpenAI

A web app where users upload a resume (PDF/DOCX) and paste a job description.
The backend extracts the text, calls the OpenAI API, and returns a structured
analysis: match score, matched skills, missing skills, experience gaps, and
actionable improvement suggestions.

---

## Quick start

```bash
# 1. Bootstrap the Django project (creates manage.py + resume_analyzer/ package)
django-admin startproject resume_analyzer
cd resume_analyzer

# 2. Create the app
python manage.py startapp analyzer

# 3. Copy the files from this scaffold into place:
#    analyzer/views.py       → analyzer/views.py
#    analyzer/utils.py       → analyzer/utils.py
#    analyzer/urls.py        → analyzer/urls.py
#    analyzer/models.py      → analyzer/models.py
#    analyzer/apps.py        → analyzer/apps.py
#    resume_analyzer/urls.py → resume_analyzer/urls.py
#    (replace the generated settings.py with the one from this scaffold)
#    templates/              → templates/

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY and a generated SECRET_KEY

# 6. Set up the database
python manage.py migrate

# 7. Run
python manage.py runserver
# Open http://localhost:8000
```

---

## File map

```
resume_analyzer/
├── requirements.txt
├── .env.example               ← copy to .env and fill in
├── resume_analyzer/
│   ├── settings.py            ← reads from .env via decouple
│   └── urls.py                ← project-level routing
└── analyzer/
    ├── views.py               ★ validates input, calls utils, renders response
    ├── utils.py               ★ text extraction + AI analysis (testable without HTTP)
    ├── urls.py                ← app-level routing
    ├── models.py              ← ResumeAnalysis model (Step 5 — history feature)
    └── templates/analyzer/
        ├── base.html          ← shared layout, header, CSS reset
        ├── index.html         ← upload form
        └── results.html       ← match score, skills, suggestions
```

---

## Build steps (from the roadmap widget)

| Step | What | Key files |
|------|------|-----------|
| 1 ✅ | Project setup + upload form | `index.html`, `views.py` (index) |
| 2 ✅ | Text extraction backend | `utils.py` → `extract_text()` |
| 3 ✅ | AI analysis function | `utils.py` → `analyze_with_ai()` |
| 4 ✅ | Results page | `results.html`, `views.py` (analyze) |
| 5    | Polish + deploy | `models.py`, rate limiting, streaming, Docker |

---

## Step 5 — things to add next

**History (Resume model)**
Uncomment the save call in `views.py` once you've run:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Rate limiting** — add `django-ratelimit` to the analyze view:
```python
from ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def analyze(request):
    ...
```

**Streaming** — ask the AI assistant:
*"Add streaming support to analyze_with_ai using stream=True and Server-Sent Events
so the analysis appears progressively instead of after a long wait."*

**Deploy to Heroku**
```bash
echo "web: gunicorn resume_analyzer.wsgi" > Procfile
heroku create
heroku config:set OPENAI_API_KEY=sk-... SECRET_KEY=... DEBUG=False
git push heroku main
```

---

## Interview talking points

**Draw the request lifecycle on a whiteboard:**
```
Browser → POST /analyze/ → urls.py → views.analyze()
  → extract_text()      (utils.py, pdfplumber / python-docx)
  → analyze_with_ai()   (utils.py, OpenAI API)
  → render results.html
```

**Why utils.py instead of everything in views.py?**
Because `extract_text()` and `analyze_with_ai()` can be unit-tested without
spinning up a Django test client — just call them directly with a file object
and a string.

**What if the PDF is scanned (image-only)?**
`pdfplumber` returns empty strings for image-only pages.
`extract_text()` checks for this and raises a `ValueError`, which the view
catches and returns as a 422 response with a human-readable error message.

**How do you ensure the AI returns valid JSON?**
The system prompt gives it an explicit schema and says "no preamble, no markdown
fences". `temperature=0.1` keeps output deterministic. The view wraps
`json.loads()` in a try/except so a malformed response returns a 503 rather than
a 500.
