"""
apps.orders.tests
===================
Focuses on the two things an order system must never get wrong: totals
that are actually derived from line items (not trusted from elsewhere),
and coupon discounts applying correctly to those totals.
"""
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Category, Department, Product
from apps.coupons.models import Coupon
from django.utils import timezone

from .models import Order, OrderItem


class OrderTotalsTests(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Electronics")
        category = Category.objects.create(department=department, name="Cameras")
        self.product = Product.objects.create(
            department=department, category=category, name="Camera",
            sku="CAM-001", price=Decimal("200.00"), stock_quantity=10,
        )
        self.order = Order.objects.create(email="buyer@example.com")

    def test_recalculate_totals_from_line_items(self):
        OrderItem.objects.create(
            order=self.order, product=self.product, product_name=self.product.name,
            product_sku=self.product.sku, unit_price=Decimal("200.00"), quantity=3,
        )
        total = self.order.recalculate_totals()
        self.assertEqual(self.order.subtotal, Decimal("600.00"))
        self.assertEqual(total, Decimal("600.00"))

    def test_coupon_discount_applied_to_total(self):
        coupon = Coupon.objects.create(
            code="SAVE10", discount_type=Coupon.DiscountType.PERCENTAGE, discount_value=Decimal("10.00"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_to=timezone.now() + timezone.timedelta(days=1),
        )
        self.order.coupon = coupon
        self.order.save()
        OrderItem.objects.create(
            order=self.order, product=self.product, product_name=self.product.name,
            product_sku=self.product.sku, unit_price=Decimal("200.00"), quantity=1,
        )
        self.order.recalculate_totals()
        self.assertEqual(self.order.discount_amount, Decimal("20.00"))
        self.assertEqual(self.order.total, Decimal("180.00"))
