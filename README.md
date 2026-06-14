<div align="center">
  <h1>✨ Resume Analyzer AI</h1>
  <p><strong>Beat the ATS. Land the Interview.</strong></p>
  <p>An intelligent, highly-tailored resume analysis tool powered by Llama-3, Django, and Supabase.</p>

  [![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](#)
  [![Django](https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white)](#)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?logo=postgresql&logoColor=white)](#)
  [![Groq](https://img.shields.io/badge/AI-Groq%20Llama--3-f55036?logo=meta&logoColor=white)](#)
  [![CI](https://github.com/bhatiaayan30/resume-analyzer-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/bhatiaayan30/resume-analyzer-ai/actions/workflows/ci.yml)
</div>

---

## ⚡ Overview

Resume Analyzer AI is an enterprise-grade web application designed to help job seekers bypass Applicant Tracking Systems (ATS) and optimize their applications. By uploading a resume (PDF/DOCX) and providing a target job description, the AI engine extracts text, maps skills, and instantly generates a comprehensive alignment report.

## 🚀 Key Features

- **🎯 Instant Match Scoring:** Get a precise 0-100 score indicating how well your resume matches the job description.
- **🛡️ ATS Formatting Checks:** Detects tables, complex layouts, and invisible text that break standard corporate parsing systems.
- **🔍 Skill Gap Analysis:** Identifies exactly which keywords you have matched, which ones you are missing, and suggests actionable upskilling roadmaps.
- **✍️ Magic Cover Letters:** Automatically generates a persuasive, tailored cover letter bridging your unique experience to the specific role using Groq's blazing-fast Llama-3 model.
- **🔒 Secure Authentication:** Built-in user accounts and history tracking powered by a Supabase PostgreSQL database.

## 🛠️ Tech Stack

- **Backend:** Django 5.1, Python 3.12
- **Database:** PostgreSQL (via Supabase Session Pooling)
- **AI Engine:** Groq API (Llama-3-8b-8192 for near-instant inference)
- **Frontend:** HTML5, Tailwind CSS (via CDN), Vanilla JavaScript, React 18 (standalone)
- **Parsing:** `pdfplumber`, `python-docx`
- **Deployment:** Google Cloud Run (Containerized via Docker)

---

## 💻 Getting Started (Local Development)

### 1. Clone & Install
```bash
git clone https://github.com/bhatiaayan30/resume-analyzer-ai.git
cd resume-analyzer-ai
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
SECRET_KEY=django-insecure-your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,*
GROQ_API_KEY=gsk_your_groq_api_key
DATABASE_URL=postgresql://user:password@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

### 3. Database & Run
```bash
python manage.py migrate
python manage.py runserver
```
Visit `http://localhost:8000` to view the application.

---

## 🐳 Deployment (Google Cloud Run)

This project is fully containerized and production-ready for Google Cloud Run.

1. Connect your GitHub repository to Google Cloud Console.
2. Navigate to **Cloud Run** → **Create Service**.
3. Select **Continuously deploy from a repository** and choose this repo.
4. Set the `GROQ_API_KEY`, `DATABASE_URL`, and `SECRET_KEY` in the Environment Variables section.
5. Deploy. Google Cloud Buildpacks will automatically detect the `Dockerfile`, install `gunicorn` + `whitenoise`, and serve your app globally.

---

## 🏗️ Architecture Design

- **`analyzer/views.py`**: Logic-thin HTTP handlers. Handles routing, form validation, Magic Number binary file verification (spoofing protection), and rate limits.
- **`analyzer/utils.py`**: The core AI logic and text extraction engine. Highly decoupled so it can be unit-tested without spinning up a Django HTTP client.
- **`templates/analyzer/`**: Contains the glassmorphic, responsive Tailwind UI. The Cover Letter generator utilizes a standalone React component for seamless asynchronous rendering.

---
<div align="center">
  <i>Built to get you hired.</i>
</div>
