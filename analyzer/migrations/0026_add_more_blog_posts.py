from django.db import migrations
from django.utils import timezone
from datetime import datetime

def update_and_add_posts(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    
    # Helper to create timezone-aware datetime
    def make_dt(year, month, day):
        dt = datetime(year, month, day, 10, 0, 0)
        return timezone.make_aware(dt)

    # Update existing posts dates to space them out
    dates_map = {
        "algorithmic-screen-semantic-vs-keyword-stuffing": make_dt(2026, 4, 12),
        "why-pdf-parsing-fails-multi-column-resumes": make_dt(2026, 4, 25),
        "fighting-ai-fatigue-detecting-generative-resumes": make_dt(2026, 5, 2),
        "beyond-static-resumes-interactive-web-portfolios": make_dt(2026, 5, 19),
        "feedback-loop-generative-mock-interviews": make_dt(2026, 6, 5),
        "real-time-optimization-chrome-extension": make_dt(2026, 6, 26),
    }

    for slug, pub_date in dates_map.items():
        BlogPost.objects.filter(slug=slug).update(published_at=pub_date)

    # Add 4 new posts
    # Post 7 (May 10)
    BlogPost.objects.get_or_create(
        slug="recruiters-perspective-resume-filtering-session",
        defaults={
            "title": "The Recruiter's Perspective: Inside a High-Volume Resume Filtering Session",
            "summary": "Step into the shoes of a corporate recruiter. Learn how hiring managers spend their initial 6-second scan window and what variables cause them to click 'Save' or 'Reject'.",
            "category": "Recruiting Insights",
            "read_time": 6,
            "published_at": make_dt(2026, 5, 10),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    To optimize your resume effectively, you must first understand the operational reality of the person reviewing it. In a typical corporate recruitment funnel, a single job posting can attract between 200 and 1,000 applications. 
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    Recruiters do not read resumes word-for-word during the initial screening. Instead, they perform a rapid, coordinate-based scan that lasts between 6 and 8 seconds per resume.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">The 6-Second Scan Pattern</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    Eye-tracking studies reveal that recruiters scan resumes in an 'F-shape' pattern, focusing heavily on specific data anchors. Their eyes immediately look for:
</p>
<ul class="list-disc pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li><strong>Your Name & Contact Info:</strong> Quick validation of identity and location.</li>
    <li><strong>Current Job Title & Company:</strong> Verifying if your current level aligns with the target role.</li>
    <li><strong>Start and End Dates:</strong> Checking for clear career progression and tenure consistency.</li>
    <li><strong>Previous Experience:</strong> Scanning past titles and scope of responsibilities.</li>
    <li><strong>Education & Core Skills:</strong> Looking for required degrees or certifications.</li>
</ul>
<p class="text-gray-300 mb-6 leading-relaxed">
    If these anchors are hidden within dense paragraphs or unusual visual layouts, the recruiter's eye misses them, resulting in a fast rejection. Formatting for readability is just as critical as keyword matching.
</p>
            """
        }
    )

    # Post 8 (May 28)
    BlogPost.objects.get_or_create(
        slug="quantifying-soft-skills-resume",
        defaults={
            "title": "Quantifying the Intangible: How to Metricize Leadership and Soft Skills",
            "summary": "Vague phrases like 'strong communicator' or 'natural leader' fail to persuade. Explore technical formatting strategies to prove soft skills using concrete outcomes.",
            "category": "Resume Strategy",
            "read_time": 5,
            "published_at": make_dt(2026, 5, 28),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    Almost every resume contains claims like "self-motivated," "detail-oriented," or "proven leader." To a recruiter or an ATS, these generic descriptions are empty buzzwords. Anyone can type them, which means they hold zero credibility.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    Instead of listing soft skills, you must <strong>show</strong> them by quantifying their impact. By connecting behavior to a business outcome, you make your soft skills verifiable and persuasive.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">The Formula for Quantifying Soft Skills</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    Use the Action-Context-Result framework to rewrite your experience statements:
</p>
<ul class="list-disc pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li><strong>Instead of:</strong> "Excellent communication and collaboration skills."</li>
    <li><strong>Write:</strong> "Coordinated cross-functional alignment between 4 engineering squads and product design, accelerating release cycle velocity by 18%."</li>
    <li class="mt-4"><strong>Instead of:</strong> "Strong mentoring and leadership abilities."</li>
    <li><strong>Write:</strong> "Mentored 3 junior software engineers, guiding them through promotions and reducing team onboarding cycle time by 25%."</li>
</ul>
<p class="text-gray-300 mb-6 leading-relaxed">
    By anchoring your leadership, communication, and adaptability to measurable outputs, you prove your claims and satisfy both automated parsers and hiring managers.
</p>
            """
        }
    )

    # Post 9 (June 15)
    BlogPost.objects.get_or_create(
        slug="cover-letters-recruiter-relevance-and-tailoring",
        defaults={
            "title": "Cover Letters in 2026: Do Recruiters Read Them, and How Do You Tailor Them Instantly?",
            "summary": "The debate is over—recruiters scan cover letters when they are highly relevant and target the hiring manager's exact concerns. Learn how to generate tailored hooks without wasting hours.",
            "category": "Job Search Strategy",
            "read_time": 5,
            "published_at": make_dt(2026, 6, 15),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    One of the most debated topics in career counseling is whether cover letters are still relevant. Many applicants feel writing them is a waste of time, assuming they are immediately discarded.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    The truth is nuanced: while recruiters rarely read generic cover letters, a **tailored, problem-solving cover letter** can be the deciding factor when comparing two candidates with similar experience levels.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">Anatomy of a High-Converting Cover Letter</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    To write a cover letter that gets read, keep it brief (under 300 words) and structure it around the company's pain points:
</p>
<ul class="list-disc pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li><strong>The Hook:</strong> Open with a specific achievement or connection to the company's current goals rather than a generic introduction.</li>
    <li><strong>The Alignment:</strong> Detail 2-3 specific instances from your past experience that match the core skills requested in the job description.</li>
    <li><strong>The Value Add:</strong> Explain how your unique skills can solve one of their current challenges (e.g. scaling their infrastructure or expanding to new markets).</li>
</ul>
<p class="text-gray-300 mb-6 leading-relaxed">
    Using automated tailoring tools allows you to analyze job descriptions and generate customized hooks instantly, eliminating the friction of writing from scratch.
</p>
            """
        }
    )

    # Post 10 (June 22)
    BlogPost.objects.get_or_create(
        slug="restructuring-resume-for-career-transition",
        defaults={
            "title": "Navigating Career Transitions: Restructuring Experience for a Brand New Domain",
            "summary": "Transitioning roles is challenging when your experience reads like a different industry. Learn how to map transferable skills and rewrite experience bullets for your new domain.",
            "category": "Career Transition",
            "read_time": 7,
            "published_at": make_dt(2026, 6, 22),
            "content": """
<p class="text-gray-300 mb-6 text-lg leading-relaxed">
    Pivoting into a new industry or role is one of the most challenging career moves you can make. The biggest hurdle? Your resume reads like your *past* domain, making it difficult for recruiters in your *target* domain to see your potential.
</p>
<p class="text-gray-300 mb-6 leading-relaxed">
    To pivot successfully, you must translate your past experience into the language of your future role. This is called **transferable skills mapping**.
</p>
<h3 class="text-2xl font-bold text-white mt-8 mb-4">How to Re-frame Domain Experience</h3>
<p class="text-gray-300 mb-6 leading-relaxed">
    Follow these steps to structure your resume for a new domain:
</p>
<ul class="list-disc pl-6 space-y-3 text-gray-300 mb-6 leading-relaxed">
    <li><strong>De-jargonize:</strong> Remove terms specific only to your previous industry. Replace them with standard business terminology. (e.g. replace "managed clinic operations" with "led project operations").</li>
    <li><strong>Focus on Methodologies:</strong> Highlight operational frameworks (Agile, Scrum, Lean, data-driven decisions) that are universally valued across industries.</li>
    <li><strong>Re-order Skill Clusters:</strong> Put skills relevant to the new domain in your skills summary block, placing them first.</li>
</ul>
<p class="text-gray-300 mb-6 leading-relaxed">
    Using semantic matching tools helps you identify which of your existing capabilities align closest with target roles, highlighting the exact skills you need to emphasize.
</p>
            """
        }
    )

def remove_more_blog_posts(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    # Delete only the 4 newly added posts
    slugs_to_delete = [
        "recruiters-perspective-resume-filtering-session",
        "quantifying-soft-skills-resume",
        "cover-letters-recruiter-relevance-and-tailoring",
        "restructuring-resume-for-career-transition"
    ]
    BlogPost.objects.filter(slug__in=slugs_to_delete).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('analyzer', '0025_populate_blog_posts'),
    ]

    operations = [
        migrations.RunPython(update_and_add_posts, remove_more_blog_posts),
    ]
