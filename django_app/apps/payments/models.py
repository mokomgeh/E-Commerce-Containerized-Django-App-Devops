"""
apps.payments.models
======================
Records the outcome of every payment attempt against an Order. We store
Stripe's transaction id and raw status rather than trusting client-side
"payment succeeded" signals -- the source of truth is always the
gateway's server-to-server response (see services.py).
"""
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="payments")

    provider = models.CharField(max_length=30, default="stripe")
    transaction_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text="Stripe PaymentIntent id (e.g. 'pi_...').",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # Full gateway response, useful for support/debugging without a second API call.
    raw_response = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.transaction_id or self.pk} for Order {self.order.order_number} ({self.status})"
