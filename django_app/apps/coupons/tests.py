"""
apps.coupons.tests
====================
Coupon validation has several independent rules (active flag, date
window, usage cap, minimum purchase) -- each is tested in isolation so a
future regression pinpoints exactly which rule broke.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Coupon


def make_coupon(**overrides):
    defaults = dict(
        code="TEST10", discount_type=Coupon.DiscountType.PERCENTAGE, discount_value=Decimal("10.00"),
        valid_from=timezone.now() - timezone.timedelta(days=1),
        valid_to=timezone.now() + timezone.timedelta(days=1),
        is_active=True,
    )
    defaults.update(overrides)
    return Coupon.objects.create(**defaults)


class CouponValidationTests(TestCase):
    def test_valid_coupon_passes(self):
        coupon = make_coupon()
        valid, reason = coupon.is_valid(order_subtotal=Decimal("100.00"))
        self.assertTrue(valid)

    def test_inactive_coupon_fails(self):
        coupon = make_coupon(is_active=False)
        valid, reason = coupon.is_valid()
        self.assertFalse(valid)

    def test_expired_coupon_fails(self):
        coupon = make_coupon(valid_to=timezone.now() - timezone.timedelta(days=1))
        valid, reason = coupon.is_valid()
        self.assertFalse(valid)
        self.assertIn("expired", reason)

    def test_usage_limit_reached_fails(self):
        coupon = make_coupon(usage_limit=1, times_used=1)
        valid, reason = coupon.is_valid()
        self.assertFalse(valid)

    def test_minimum_purchase_not_met_fails(self):
        coupon = make_coupon(minimum_purchase_amount=Decimal("200.00"))
        valid, reason = coupon.is_valid(order_subtotal=Decimal("50.00"))
        self.assertFalse(valid)

    def test_percentage_discount_calculation(self):
        coupon = make_coupon(discount_type=Coupon.DiscountType.PERCENTAGE, discount_value=Decimal("20.00"))
        self.assertEqual(coupon.calculate_discount(Decimal("100.00")), Decimal("20.00"))

    def test_fixed_discount_never_exceeds_subtotal(self):
        coupon = make_coupon(discount_type=Coupon.DiscountType.FIXED, discount_value=Decimal("50.00"))
        self.assertEqual(coupon.calculate_discount(Decimal("30.00")), Decimal("30.00"))
