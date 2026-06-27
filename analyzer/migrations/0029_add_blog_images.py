from django.db import migrations

def add_cover_images(apps, schema_editor):
    BlogPost = apps.get_model('analyzer', 'BlogPost')
    
    images = {
        "algorithmic-screen-semantic-vs-keyword-stuffing": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=800&q=80",
        "why-pdf-parsing-fails-multi-column-resumes": "https://images.unsplash.com/photo-1586281380349-632531db7ed4?auto=format&fit=crop&w=800&q=80",
        "fighting-ai-fatigue-detecting-generative-resumes": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=800&q=80",
        "beyond-static-resumes-interactive-web-portfolios": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80",
        "feedback-loop-generative-mock-interviews": "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=800&q=80",
        "real-time-optimization-chrome-extension": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=800&q=80",
        "recruiters-perspective-resume-filtering-session": "https://images.unsplash.com/photo-1565688534245-05d6b5be184a?auto=format&fit=crop&w=800&q=80",
        "quantifying-soft-skills-resume": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=800&q=80",
        "cover-letters-recruiter-relevance-and-tailoring": "https://images.unsplash.com/photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=800&q=80",
        "restructuring-resume-for-career-transition": "https://images.unsplash.com/photo-1473186578172-c141e6798c11?auto=format&fit=crop&w=800&q=80"
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
