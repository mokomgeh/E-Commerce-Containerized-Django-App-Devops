"""
apps.orders.models
====================
Order and OrderItem: the transactional record of what a customer bought.

Important design choice: OrderItem snapshots the product's name, SKU, and
price at time of purchase (rather than only FK'ing to Product and reading
its *current* price). Product prices/names change over time; an order
must always reflect what the customer actually agreed to pay, even if the
product is later repriced, renamed, or deleted.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Payment"
        PAID = "paid", "Paid"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    # Public-facing order number, safe to show/email to customers instead
    # of the internal auto-increment id.
    order_number = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    # Guest checkout support: if there's no user, we still need contact info.
    email = models.EmailField()

    billing_address = models.ForeignKey(
        "accounts.Address", on_delete=models.PROTECT, related_name="billing_orders", null=True, blank=True
    )
    shipping_address = models.ForeignKey(
        "accounts.Address", on_delete=models.PROTECT, related_name="shipping_orders", null=True, blank=True
    )

    coupon = models.ForeignKey(
        "coupons.Coupon", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    tracking_number = models.CharField(max_length=100, blank=True)
    customer_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["order_number"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Order {str(self.order_number)[:8]} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("orders:order_detail", kwargs={"order_number": self.order_number})

    def recalculate_totals(self, save=True):
        """
        Recompute subtotal/discount/total from line items. Called after
        items are added/changed and again right before payment, so the
        charged amount is always derived from server-side data -- never
        trusted from the client.
        """
        self.subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))

        if self.coupon:
            valid, _ = self.coupon.is_valid(order_subtotal=self.subtotal)
            self.discount_amount = self.coupon.calculate_discount(self.subtotal) if valid else Decimal("0.00")
        else:
            self.discount_amount = Decimal("0.00")

        self.total = max(
            Decimal("0.00"),
            self.subtotal - self.discount_amount + self.shipping_cost + self.tax_amount,
        )
        if save:
            self.save(update_fields=["subtotal", "discount_amount", "total"])
        return self.total

    def mark_as_paid(self):
        from django.utils import timezone
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, related_name="order_items"
    )

    # Snapshots -- see module docstring for why these are duplicated
    # instead of always reading from `product`.
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
