from django.db import migrations
from django.utils import timezone

def populate_blog_posts(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    
    # Article 1
    BlogPost.objects.get_or_create(
        slug="algorithmic-screen-semantic-vs-keyword-stuffing",
        defaults={
            "title": "The Algorithmic Screen: Semantic Concept Matching vs. Keyword Stuffing in Modern ATS",
            "summary": "Why copying and pasting white-text keywords is a relic of the past. Explore how modern screening engines use vector embeddings to read and score candidate profiles.",
            "category": "ATS Insights",
            "read_time": 6,
            "published_at": timezone.now(),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    For years, job seekers have tried to 'beat' Applicant Tracking Systems (ATS) using basic tricks. The most common? Copying and pasting the entire job description into the footer of a resume, resizing it to 1pt, and coloring it white so it remains invisible to human eyes but readable to machines. 
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    In 2026, this tactic is not only useless, but it can also get your application blacklisted. Modern screening systems like Workday, Greenhouse, and Taleo no longer rely on simplistic keyword count matching. Instead, they use advanced semantic search and large language models (LLMs) to read resumes the way a human recruiter would.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">What is Semantic Matching?</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    Unlike simple keyword check programs, semantic models convert sentences into mathematical coordinates called vector embeddings. These coordinates represent the <em>meaning</em> of the text. For example, if a job description asks for experience in "managing distributed ledgers" and your resume mentions "implementing blockchain solutions," a semantic matcher immediately knows these two concepts are closely related. You receive matching credit even though the exact word was not present.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    Conversely, if you stuff keywords like "Python, Python, Python" in a random list, the system flags it as highly disjointed and marks the resume as low-quality because it lacks structural coherence.
</p>
<div class="glass-panel p-6 rounded-2xl border border-white/5 my-8">
    <h4 class="font-bold text-white mb-2">Key Takeaway</h4>
    <p class="text-gray-400 text-sm">
        Focus on matching the <strong>context and structure</strong> of your experience to the job requirements. Use action verbs and describe how you applied the skills rather than listing them in isolation.
    </p>
</div>
            """
        }
    )

    # Article 2
    BlogPost.objects.get_or_create(
        slug="why-pdf-parsing-fails-multi-column-resumes",
        defaults={
            "title": "Why PDF Parsing Fails: The Technical Breakdown of Multi-Column Resumes",
            "summary": "Understanding coordinate-based text extraction. Learn why beautiful Canva templates with parallel columns get scrambled into unreadable jargon by parsing algorithms.",
            "category": "Formatting Guide",
            "read_time": 5,
            "published_at": timezone.now(),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    You spent hours designing a gorgeous, two-column resume on Canva, choosing the perfect accent colors and layout. But when you upload it to a company's job portal, the parsed output looks like an unreadable mess, with your contact info, jobs, and hobbies mixed together.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    This happens because of the technical limitations of PDF parsers. When an ATS extracts text from a PDF, it parses the document's character coordinates. Standard PDF libraries extract text from top-to-bottom and left-to-right, completely scrambling two-column layouts.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">How a Parser Reads Columns</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    Instead of seeing two distinct columns side-by-side, the parser reads coordinate lines horizontally across the entire page. For example:
</p>
<pre class="bg-black/30 p-4 rounded-xl border border-white/5 text-xs text-brand font-mono mb-6 leading-relaxed">
Line 1: [Contact Info]           [Professional Summary]
Parsed: "Contact Info Professional Summary"

Line 2: [Email Address]         [Experienced Software Engineer]
Parsed: "Email Address Experienced Software Engineer"
</pre>
<p class="text-gray-300 mb-6 leading-relaxed">
    As a result, your sentences get broken in half and joined with unrelated phrases from the opposite column. The ATS's entity parser fails to recognize your experience, skills, and education, leading to an immediate automatic rejection.
</p>
<div class="glass-panel p-6 rounded-2xl border border-white/5 my-8">
    <h4 class="font-bold text-white mb-2">Rule of Thumb</h4>
    <p class="text-gray-400 text-sm">
        Always stick to a clean, single-column resume format when applying online. Save the creative, multi-column designs for direct networking or emailing to human recruiters.
    </p>
</div>
            """
        }
    )

    # Article 3
    BlogPost.objects.get_or_create(
        slug="fighting-ai-fatigue-detecting-generative-resumes",
        defaults={
            "title": "Fighting AI Fatigue: How Recruiters Detect Generative Profiles and Timeline Inconsistencies",
            "summary": "Recruiters are rejecting applications at record rates due to templated LLM language. Learn how to write metric-driven statements that pass verification checks.",
            "category": "Authenticity & AI",
            "read_time": 7,
            "published_at": timezone.now(),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    With the rise of generic chat assistants, recruiters are experiencing extreme "AI fatigue." They are receiving thousands of resumes that look identical, using the same overused words ("spearheaded", "leveraged", "streamlined") and lacking any unique voice.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    To protect their pipelines, recruitment teams are deploying detection tools and timeline checks. If your resume reads like a copy-pasted prompt response, it's likely to be filtered out.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">Key Markers of a Generative Resume</h3>
<ul class="list-disc pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li><strong>Clichés & Buzzwords:</strong> Constant repetition of words like "fostered," "synergy," and "game-changing."</li>
    <li><strong>Vague Metrics:</strong> Statements like "Improved efficiency by 30%" without explaining the baseline, the scale, or the actual work done.</li>
    <li><strong>Chronological Gaps & Overlaps:</strong> Generative models often generate arbitrary dates or overlook timeline conflicts (e.g., claiming to work full-time at two non-remote companies simultaneously).</li>
</ul>
<p class="text-gray-300 mb-6 leading-relaxed">
    To stand out, you must audit your resume for timeline accuracy and back up every metric with a technical explanation of how you achieved it.
</p>
            """
        }
    )

    # Article 4
    BlogPost.objects.get_or_create(
        slug="beyond-static-resumes-interactive-web-portfolios",
        defaults={
            "title": "Beyond Static Resumes: The SEO and Accessibility Benefits of an Interactive Web Portfolio",
            "summary": "Why flat files are limiting your discoverability. See how converting your application into an accessible, crawlable online showcase gets you noticed by hiring managers.",
            "category": "Portfolio Strategy",
            "read_time": 5,
            "published_at": timezone.now(),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    A standard PDF resume is a static snapshot of your career. While necessary for application portals, it doesn't represent who you are dynamically, and it does not help you get discovered organically.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    An interactive web portfolio changes this dynamic. By putting your achievements online, you gain several advantages:
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">Why Web Portfolios Win</h3>
<ul class="list-disc pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li><strong>SEO Discoverability:</strong> A web portfolio can be indexed by search engines. When recruiters look up your name or specific project keywords, they find your portfolio first.</li>
    <li><strong>Interactive Elements:</strong> Unlike a flat PDF, a website lets you embed live links to GitHub repositories, Figma prototypes, interactive charts, and video demonstrations.</li>
    <li><strong>Mobile Accessibility:</strong> Many recruiters check resumes on the go. While reading a PDF on a phone is a pinch-to-zoom nightmare, a responsive website renders perfectly on any viewport.</li>
</ul>
            """
        }
    )

    # Article 5
    BlogPost.objects.get_or_create(
        slug="feedback-loop-generative-mock-interviews",
        defaults={
            "title": "The Feedback Loop: Leveraging Generative Mock Interviews to Pass the HR Screening Call",
            "summary": "Passing the resume screen is only half the battle. Discover how practicing with real-time mock interviews helps you refine behavioral answers under pressure.",
            "category": "Interview Prep",
            "read_time": 6,
            "published_at": timezone.now(),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    You passed the ATS screening and scheduled an HR interview. But are you actually prepared to speak, or are you just reading over notes?
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    Passive preparation (reading interview guides) is not enough. Under pressure, we often stumble or lose the core focus of our answers. The only way to improve is through active practice.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">The STAR Method in Action</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    When answering behavioral questions (e.g., "Tell me about a time you resolved a technical conflict"), always structure your response using the STAR method:
</p>
<ul class="list-disc pl-6 space-y-2 text-gray-300 mb-6 leading-relaxed">
    <li><strong>Situation:</strong> Give context about the challenge.</li>
    <li><strong>Task:</strong> Describe your specific responsibility.</li>
    <li><strong>Action:</strong> Explain exactly what you did to address it.</li>
    <li><strong>Result:</strong> State the concrete, quantifiable outcome.</li>
</ul>
<p class="text-gray-300 mb-6 leading-relaxed">
    Generative mock interview tools help you practice this flow by asking follow-up questions tailored directly to your resume, forcing you to think on your feet.
</p>
            """
        }
    )

    # Article 6
    BlogPost.objects.get_or_create(
        slug="real-time-optimization-chrome-extension",
        defaults={
            "title": "Real-Time Optimization: Embedding ATS Checks Directly into Your Job Search Workflow",
            "summary": "Maximize your daily output. A step-by-step tutorial on using our Chrome extension to analyze job descriptions and check resume alignment directly on LinkedIn.",
            "category": "Product Guide",
            "read_time": 4,
            "published_at": timezone.now(),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    Applying for jobs can feel like a numbers game, but quality is what actually lands interviews. Still, spending 30 minutes optimizing your resume for every single job application is unsustainable.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    To solve this, you need to embed optimization directly into your browsing flow.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">Streamlining Your Scan Workflow</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    Instead of copy-pasting text back and forth between different windows:
</p>
<ol class="list-decimal pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li>Install the Chrome extension to connect your account.</li>
    <li>Navigate to any role on LinkedIn, Indeed, or Greenhouse.</li>
    <li>Click the extension icon to immediately pull the job description, scan it against your uploaded resume, and display a match score directly on your sidebar.</li>
</ol>
<p class="text-gray-300 mb-6 leading-relaxed">
    This real-time feedback allows you to instantly decide whether a role is worth applying to, or what minor adjustments are needed to pass the screen.
</p>
            """
        }
    )

def remove_blog_posts(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    BlogPost.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('analyzer', '0024_blogpost'),
    ]

    operations = [
        migrations.RunPython(populate_blog_posts, remove_blog_posts),
    ]
