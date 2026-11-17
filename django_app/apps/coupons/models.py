"""
apps.coupons.models
=====================
Discount coupon codes with flexible rules: percentage or fixed-amount
off, date validity window, minimum purchase threshold, and an optional
total-usage cap.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage off"
        FIXED = "fixed", "Fixed amount off"

    code = models.CharField(max_length=40, unique=True, help_text="Case-insensitive; stored uppercase.")
    description = models.CharField(max_length=255, blank=True)

    discount_type = models.CharField(max_length=10, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Percentage (e.g. 15 = 15%) or currency amount, depending on discount_type.",
    )

    minimum_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()

    usage_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Leave blank for unlimited total uses."
    )
    times_used = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    def is_valid(self, order_subtotal: Decimal = None) -> tuple[bool, str]:
        """
        Validate this coupon against all its business rules. Returns a
        (is_valid, reason) tuple so callers (views, forms) can show the
        customer a specific, helpful error message rather than a generic
        "invalid coupon".
        """
        now = timezone.now()
        if not self.is_active:
            return False, "This coupon is no longer active."
        if now < self.valid_from:
            return False, "This coupon is not yet valid."
        if now > self.valid_to:
            return False, "This coupon has expired."
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False, "This coupon has reached its usage limit."
        if order_subtotal is not None and order_subtotal < self.minimum_purchase_amount:
            return False, f"A minimum purchase of {self.minimum_purchase_amount} is required for this coupon."
        return True, ""

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """Compute the discount amount for a given order subtotal, never exceeding the subtotal itself."""
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = subtotal * (self.discount_value / Decimal("100"))
        else:
            discount = self.discount_value
        return min(discount, subtotal).quantize(Decimal("0.01"))
