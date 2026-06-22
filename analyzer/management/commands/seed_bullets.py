from django.core.management.base import BaseCommand
from analyzer.models import PreWrittenBullet

class Command(BaseCommand):
    help = "Seeds database with high-quality, metrics-driven pre-written bullet points."

    def handle(self, *args, **options):
        self.stdout.write("Seeding pre-written bullet points...")
        
        bullets_data = [
            # SOFTWARE ENGINEER
            {
                "job_role": "Software Engineer",
                "category": "Performance & Scalability",
                "bullets": [
                    "Optimized database queries and API response times, reducing latency by [metric]% and saving $[metric]/month in cloud infrastructure costs.",
                    "Architected a high-throughput microservices architecture handling [metric]+ concurrent requests using [tool].",
                    "Refactored legacy codebase using [tool], improving test coverage by [metric]% and reducing deployment times by [metric] minutes.",
                    "Implemented Redis caching layer, speeding up read-heavy data loads by [metric]% and decreasing DB load by [metric]%."
                ]
            },
            {
                "job_role": "Software Engineer",
                "category": "Technical Delivery & Engineering",
                "bullets": [
                    "Developed and launched [metric]+ full-stack product features using [tool], serving [metric]+ active monthly users.",
                    "Integrated payment processing systems using [tool], resolving checkout failures by [metric]% and increasing conversions by [metric]%.",
                    "Engineered real-time notification engine with [tool], delivering [metric]M+ alerts daily with sub-[metric]ms delivery latency.",
                    "Built reusable UI components with [tool], speeding up frontend development lifecycle times by [metric]%."
                ]
            },
            {
                "job_role": "Software Engineer",
                "category": "Leadership & Collaboration",
                "bullets": [
                    "Mentored [metric] junior engineers on software engineering best practices, accelerating onboarding time by [metric]%.",
                    "Led team of [metric] developers in implementing automated CI/CD pipelines, cutting production deployment errors by [metric]%.",
                    "Collaborated with product teams to design system specs, resulting in on-time delivery of [metric] core roadmap projects."
                ]
            },
            
            # PRODUCT MANAGER
            {
                "job_role": "Product Manager",
                "category": "Product Launch & Growth",
                "bullets": [
                    "Owned product strategy and roadmap for a [tool] dashboard, growing monthly active users (MAU) by [metric]% within [metric] months.",
                    "Led launch of a new mobile app feature, driving a [metric]% increase in customer engagement and generating $[metric]k in additional ARR.",
                    "Conducted [metric]+ user research sessions and A/B test experiments, optimizing conversion funnel efficiency by [metric]%."
                ]
            },
            {
                "job_role": "Product Manager",
                "category": "Execution & Leadership",
                "bullets": [
                    "Directed cross-functional agile team of [metric] engineers and designers to deliver [metric] high-impact features ahead of schedule.",
                    "Managed product backlog prioritization using [tool], increasing sprint velocity by [metric]% and reducing bug backlogs by [metric]%.",
                    "Defined product metrics and KPI monitoring systems, reducing customer churn rate by [metric]%."
                ]
            },
            
            # DATA ANALYST
            {
                "job_role": "Data Analyst",
                "category": "Analytics & Business Intelligence",
                "bullets": [
                    "Built interactive dashboard pipelines using [tool], saving business teams [metric] hours per week in manual spreadsheet reporting.",
                    "Analyzed customer behavior datasets of [metric]M+ rows, identifying churn risk patterns and saving $[metric]k in annual retention.",
                    "Presented cohort analysis to executives, leading to product tweaks that boosted customer lifetime value (LTV) by [metric]%."
                ]
            },
            {
                "job_role": "Data Analyst",
                "category": "Data Infrastructure & Modeling",
                "bullets": [
                    "Optimized SQL queries and ETL pipelines in [tool], speeding up data warehouse ingestion times by [metric]%.",
                    "Implemented data validation frameworks, reducing reporting inconsistencies and data quality issues by [metric]%.",
                    "Developed predictive model to forecast quarterly demand, achieving a [metric]% accuracy rate."
                ]
            },

            # SALES EXECUTIVE
            {
                "job_role": "Sales Executive",
                "category": "Revenue Generation",
                "bullets": [
                    "Closed $[metric]k+ in new sales pipeline revenue, exceeding quarterly quota targets by [metric]% for [metric] consecutive quarters.",
                    "Managed portfolio of [metric]+ enterprise client accounts, maintaining a customer retention rate of [metric]%.",
                    "Negotiated contract extensions with [metric] key accounts, increasing average contract value (ACV) by [metric]%."
                ]
            },
            {
                "job_role": "Sales Executive",
                "category": "Pipeline & Operations",
                "bullets": [
                    "Generated [metric]+ qualified business leads monthly through cold outbound campaigns and networking.",
                    "Refined sales demo templates, increasing product demo-to-close conversion rates by [metric]%.",
                    "Trained [metric] junior sales reps on CRM utilization, boosting team outbound efficiency by [metric]%."
                ]
            }
        ]

        count = 0
        for data in bullets_data:
            role = data["job_role"]
            category = data["category"]
            for text in data["bullets"]:
                # Avoid duplicates
                obj, created = PreWrittenBullet.objects.get_or_create(
                    job_role=role,
                    category=category,
                    bullet_text=text
                )
                if created:
                    count += 1
                    
        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {count} new pre-written bullet points!"))
