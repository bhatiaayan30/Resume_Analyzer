from django.db import migrations

def add_cover_images(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    
    # Updated to cohesive, dark, neon purple/pink abstract aesthetic to match the site's theme
    images = {
        "algorithmic-screen-semantic-vs-keyword-stuffing": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=800&q=80",
        "why-pdf-parsing-fails-multi-column-resumes": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=800&q=80",
        "fighting-ai-fatigue-detecting-generative-resumes": "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?auto=format&fit=crop&w=800&q=80",
        "beyond-static-resumes-interactive-web-portfolios": "https://images.unsplash.com/photo-1557682250-33bd709cbe85?auto=format&fit=crop&w=800&q=80",
        "feedback-loop-generative-mock-interviews": "https://images.unsplash.com/photo-1614729939124-032f0b56c9ce?auto=format&fit=crop&w=800&q=80",
        "real-time-optimization-chrome-extension": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=800&q=80",
        "recruiters-perspective-resume-filtering-session": "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?auto=format&fit=crop&w=800&q=80",
        "quantifying-soft-skills-resume": "https://images.unsplash.com/photo-1604871000636-074fa5117945?auto=format&fit=crop&w=800&q=80",
        "cover-letters-recruiter-relevance-and-tailoring": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
        "restructuring-resume-for-career-transition": "https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?auto=format&fit=crop&w=800&q=80"
    }

    for slug, url in images.items():
        BlogPost.objects.filter(slug=slug).update(cover_image=url)

def remove_cover_images(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    BlogPost.objects.all().update(cover_image='')

class Migration(migrations.Migration):

    dependencies = [
        ('analyzer', '0028_secondaryemail'),
    ]

    operations = [
        migrations.RunPython(add_cover_images, remove_cover_images),
    ]
