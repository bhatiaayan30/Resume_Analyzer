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

<!-- TODO: Replace with actual screenshots or GIF once deployed -->
![Report Score Overview](/.github/assets/report_score.png)
![Skill Gap Analysis](/.github/assets/skill_gap.png)
## 🚀 Key Features

- **🎯 Instant Match Scoring:** Get a precise 0-100 score indicating how well your resume matches the job description.
- **🛡️ ATS Formatting Checks:** Detects tables, complex layouts, and invisible text that break standard corporate parsing systems.
- **✍️ Impact & Writing Critique:** Suggests high-impact rewrites for weak bullet points with detailed AI critiques.
- **📈 Upskilling Roadmap:** Identifies missing skills and generates an upskilling strategy with clickable resource links.
- **🎙️ Interview Prep:** Generates 10 to 15 highly tailored interview questions covering technical skills, behavioral situations, and gaps.
- **⚡ Async Processing:** Fast, non-blocking UI using `django-q` background workers to handle intensive AI tasks.
- **✉️ Magic Cover Letters:** Automatically generates a persuasive, tailored cover letter bridging your unique experience to the specific role using Groq's blazing-fast Llama-3 model.
- **🔒 Secure Authentication:** Built-in user accounts and history tracking powered by a Supabase PostgreSQL database.

## 🛠️ Tech Stack

- **Backend:** Django 5.1, Python 3.12
- **Database:** PostgreSQL (via Supabase Session Pooling)
- **Background Task Worker:** Django-Q
- **AI Engine:** Groq API (Llama-3-8b-8192 for near-instant inference)
- **Frontend:** HTML5, Tailwind CSS (via CDN), Vanilla JavaScript, React 18 (standalone)
- **Parsing:** `pdfplumber`, `python-docx`
- **Deployment:** Google Cloud Run (Containerized via Docker)

---

## 💻 Getting Started (Local Development)

### 1. Clone & Install
```bash
git clone https://github.com/bhatiaayan30/Resume_Analyzer.git
cd Resume_Analyzer
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory. You will need to configure various API keys for the full functionality:

1. **Django Settings**:
   - `SECRET_KEY`: A random secure string for Django.
   - `DEBUG`: Set to `True` for local development, `False` for production.
   - `ALLOWED_HOSTS`: Set to `localhost,127.0.0.1,*` for local testing.

2. **Database (Supabase PostgreSQL)**:
   - `DATABASE_URL`: Create a project on [Supabase](https://supabase.com/) and copy the connection string. (Note: You can comment this out to use local SQLite for basic testing).

3. **Groq AI (Llama 3)**:
   - `GROQ_API_KEY`: Get an API key from the [Groq Console](https://console.groq.com/).

4. **Google OAuth (Authentication)**:
   - `GOOGLE_CLIENT_ID` and `GOOGLE_SECRET`: Create credentials in the [Google Cloud Console](https://console.cloud.google.com/) under APIs & Services > Credentials.

5. **Razorpay (Payments)**:
   - `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`: Generate these from your [Razorpay Dashboard](https://dashboard.razorpay.com/) under Settings > API Keys.
   - `RAZORPAY_WEBHOOK_SECRET`: A secure string you define for your webhook endpoint.

Your `.env` file should look like this:
```env
DEBUG=True
SECRET_KEY=django-insecure-development-key-for-local-testing
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:password@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
GROQ_API_KEY=your_groq_api_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_SECRET=your_google_client_secret
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

### 3. Database & Run
```bash
python manage.py migrate
python manage.py runserver
```

**Note:** You must also start the background worker in a separate terminal:
```bash
python manage.py qcluster
```
*(Windows Users: If `qcluster` gets stuck looping after `Ctrl+C`, run the provided `kill_qcluster.bat` script to terminate it cleanly.)*

Visit `http://localhost:8000` to view the application.

---

## 🐳 Deployment (GitHub to Google Cloud Run)

This project is fully containerized and production-ready for Google Cloud Run, utilizing seamless GitHub integration.

### Procedure for GitHub to GCP Deployment:

1. **Prepare Google Cloud Platform (GCP)**:
   - Create a new project in the [Google Cloud Console](https://console.cloud.google.com/).
   - Enable the **Cloud Run API** and **Cloud Build API** for your project.
   - Set up billing for the project.

2. **Connect GitHub to Cloud Run**:
   - Navigate to **Cloud Run** in the GCP Console.
   - Click **Create Service**.
   - Select **Continuously deploy new revisions from a source repository**.
   - Click **Set up with Cloud Build**.
   - Select **GitHub** as the provider and authenticate.
   - Choose your repository (`Resume_Analyzer`) and the branch (e.g., `main`).

3. **Configure Build and Service Settings**:
   - Build Type: Choose **Dockerfile** or let Cloud Buildpacks automatically detect the environment.
   - Service Name: e.g., `resume-analyzer`.
   - Region: Choose a region close to your users.
   - Authentication: Select **Allow unauthenticated invocations** if this is a public web app.

4. **Environment Variables**:
   - Expand **Container, Connections, Security**.
   - Add all your production environment variables from your `.env` file (e.g., `SECRET_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `RAZORPAY_KEY_ID`, etc.).
   - Make sure `DEBUG` is set to `False` and `ALLOWED_HOSTS` includes your generated Cloud Run URL.

5. **Deploy**:
   - Click **Create**.
   - GCP will now automatically pull the code from GitHub, build the Docker container, and deploy it.
   - Any future pushes to the connected GitHub branch will automatically trigger a new build and deployment.

---

## 🏗️ Architecture Design

- **`analyzer/views.py`**: Logic-thin HTTP handlers. Handles routing, form validation, Magic Number binary file verification (spoofing protection), and rate limits.
- **`analyzer/utils.py`**: The core AI logic and text extraction engine. Highly decoupled so it can be unit-tested without spinning up a Django HTTP client.
- **`templates/analyzer/`**: Contains the glassmorphic, responsive Tailwind UI. The Cover Letter generator utilizes a standalone React component for seamless asynchronous rendering.

---

## 🚧 Known Limitations
- **File Support:** Currently only supports PDF and DOCX files. Google Docs or LinkedIn profile imports are not supported.
- **Language:** English-language resumes only.
- **Scope:** This is an analysis tool, not a job application tracker or resume builder.


---
<div align="center">
  <i>Built to get you hired.</i>
</div>
