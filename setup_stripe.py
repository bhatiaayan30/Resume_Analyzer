import os
import sys
import django
import stripe
from pathlib import Path

# Add the project directory to the sys.path
sys.path.append(str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_analyzer.settings')

django.setup()

from django.conf import settings

def setup_stripe_product():
    if not settings.STRIPE_SECRET_KEY:
        print("Error: STRIPE_SECRET_KEY is not set in your .env file.")
        return

    stripe.api_key = settings.STRIPE_SECRET_KEY

    print("Creating Stripe Product...")
    try:
        product = stripe.Product.create(
            name="Resume Analyzer Plans",
            description="Tiered subscription plans for Resume Analyzer.",
        )
        print(f"✅ Product created: {product.id}")

        prices = [
            (4900, "STRIPE_PRICE_ID_49"),
            (14900, "STRIPE_PRICE_ID_149"),
            (29900, "STRIPE_PRICE_ID_299"),
            (99900, "STRIPE_PRICE_ID_999"),
        ]

        created_prices = []
        for amount, env_name in prices:
            print(f"Creating Stripe Price (₹{amount//100}/month)...")
            price = stripe.Price.create(
                unit_amount=amount,
                currency="inr",
                recurring={"interval": "month"},
                product=product.id,
            )
            created_prices.append((env_name, price.id))
            print(f"✅ Price created: {price.id}")

        print("\n🎉 Stripe Setup Complete!")
        print("Add the following lines to your .env file:")
        for env_name, price_id in created_prices:
            print(f"{env_name}={price_id}")

    except Exception as e:
        print(f"❌ Error creating Stripe product: {e}")

if __name__ == "__main__":
    setup_stripe_product()
