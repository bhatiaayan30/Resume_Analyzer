import os
import razorpay
import traceback
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from dotenv import set_key

class Command(BaseCommand):
    help = "Setup Razorpay plans and save them to .env"

    def handle(self, *args, **options):
        key_id = getattr(settings, "RAZORPAY_KEY_ID", None)
        key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", None)

        if not key_id or "placeholder" in key_id or not key_secret or "placeholder" in key_secret:
            raise CommandError("Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env first.")

        client = razorpay.Client(auth=(key_id, key_secret))

        plans_to_create = [
            {
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": "Starter Plan",
                    "amount": 4900, # amount in paise
                    "currency": "INR",
                    "description": "Starter Tier for Resume Analyzer"
                }
            },
            {
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": "Pro Plan",
                    "amount": 14900, 
                    "currency": "INR",
                    "description": "Pro Tier for Resume Analyzer"
                }
            },
            {
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": "Elite Plan",
                    "amount": 29900, 
                    "currency": "INR",
                    "description": "Elite Tier for Resume Analyzer"
                }
            },
            {
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": "Unlimited Plan",
                    "amount": 99900, 
                    "currency": "INR",
                    "description": "Unlimited Tier for Resume Analyzer"
                }
            }
        ]

        env_file = ".env"

        try:
            self.stdout.write(self.style.SUCCESS("Creating Razorpay Plans..."))
            
            p1 = client.plan.create(plans_to_create[0])
            set_key(env_file, "RAZORPAY_PLAN_ID_49", p1['id'])
            self.stdout.write(f"Created Starter Plan: {p1['id']}")
            
            p2 = client.plan.create(plans_to_create[1])
            set_key(env_file, "RAZORPAY_PLAN_ID_149", p2['id'])
            self.stdout.write(f"Created Pro Plan: {p2['id']}")
            
            p3 = client.plan.create(plans_to_create[2])
            set_key(env_file, "RAZORPAY_PLAN_ID_299", p3['id'])
            self.stdout.write(f"Created Elite Plan: {p3['id']}")
            
            p4 = client.plan.create(plans_to_create[3])
            set_key(env_file, "RAZORPAY_PLAN_ID_999", p4['id'])
            self.stdout.write(f"Created Unlimited Plan: {p4['id']}")
            
            self.stdout.write(self.style.SUCCESS("\nSUCCESS! All plans created and added to .env."))
            self.stdout.write("Don't forget to also set your RAZORPAY_WEBHOOK_SECRET in .env before going live.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nError creating plans: {repr(e)}"))
            traceback.print_exc()
