"""
Management command: seed_demo_data
====================================
Populates the database with a small but realistic demo catalog
(departments, categories, products, images-less placeholders,
specifications) plus a sample coupon, so a fresh clone of this repo is
immediately browsable without manually clicking through the admin.

Usage:
    python manage.py seed_demo_data
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.catalog.models import Category, Department, Product, ProductSpecification
# from apps.coupons.models import Coupon

CATALOG = {
    "Electronics": {
        "Laptops": [
            ("ProBook X15", "14-inch productivity laptop with all-day battery life.", 1299.00, 1099.00, {"RAM": "16GB", "Storage": "512GB SSD", "CPU": "8-core"}),
            ("UltraLight Air 13", "The thinnest laptop in our lineup, built for travel.", 999.00, None, {"RAM": "8GB", "Storage": "256GB SSD", "Weight": "1.1kg"}),
        ],
        "Headphones": [
            ("SilentWave ANC", "Active noise-cancelling over-ear headphones.", 249.00, 199.00, {"Battery": "30 hours", "Bluetooth": "5.3"}),
            ("SportBuds Pro", "Sweat-resistant true wireless earbuds.", 129.00, None, {"Battery": "8 hours", "Water Resistance": "IPX7"}),
        ],
    },
    "Fashion": {
        "Men's Shirts": [
            ("Classic Oxford Shirt", "100% cotton button-down, tailored fit.", 59.00, 45.00, {"Material": "100% Cotton", "Fit": "Tailored"}),
        ],
        "Women's Dresses": [
            ("Summer Wrap Dress", "Lightweight wrap dress, perfect for warm weather.", 79.00, None, {"Material": "Linen blend", "Length": "Midi"}),
        ],
    },
    "Home & Kitchen": {
        "Cookware": [
            ("NonStick Chef Pan 10\"", "Durable nonstick frying pan with ergonomic handle.", 39.00, 29.00, {"Material": "Aluminum", "Diameter": "10 inches"}),
        ],
    },
}


class Command(BaseCommand):
    help = "Seed the database with demo departments, categories, and products."

    def handle(self, *args, **options):
        created_products = 0
        for dept_name, categories in CATALOG.items():
            department, _ = Department.objects.get_or_create(name=dept_name)
            for cat_name, products in categories.items():
                category, _ = Category.objects.get_or_create(
                    name=cat_name, department=department, parent=None
                )
                for name, desc, price, discount, specs in products:
                    sku = f"{dept_name[:3].upper()}-{cat_name[:3].upper()}-{name[:3].upper()}".replace(" ", "")
                    product, created = Product.objects.get_or_create(
                        sku=sku,
                        defaults=dict(
                            department=department, category=category, name=name,
                            short_description=desc, description=desc,
                            price=Decimal(str(price)),
                            discount_price=Decimal(str(discount)) if discount else None,
                            stock_quantity=50, is_active=True, is_featured=True,
                        ),
                    )
                    if created:
                        created_products += 1
                        for i, (k, v) in enumerate(specs.items()):
                            ProductSpecification.objects.create(product=product, name=k, value=v, display_order=i)

        # coupon, coupon_created = Coupon.objects.get_or_create(
        #     code="WELCOME10",
        #     defaults=dict(
        #         description="10% off your first order",
        #         discount_type=Coupon.DiscountType.PERCENTAGE,
        #         discount_value=Decimal("10.00"),
        #         valid_from=timezone.now(),
        #         valid_to=timezone.now() + timedelta(days=365),
        #         is_active=True,
        #     ),
        # )

        # self.stdout.write(self.style.SUCCESS(
        #     f"Seeded {created_products} new products. Coupon WELCOME10 {'created' if coupon_created else 'already existed'}."
        # ))