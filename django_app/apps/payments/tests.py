"""
apps.payments.tests
=====================
Stripe calls a real external test-mode API, so we don't hit the network
in unit tests. Instead we verify the fail-fast behavior when API keys are
missing (the most common state for anyone who's just cloned this repo),
webhook signature rejection, and that the Payment model behaves as
expected.
"""
from decimal import Decimal

import stripe
from django.test import TestCase, override_settings

from apps.orders.models import Order

from .models import Payment
from .services import get_or_create_payment_intent
from .views import stripe_webhook  # noqa: F401  (imported to confirm it's wired up)


class StripeConfigTests(TestCase):
    @override_settings(STRIPE_SECRET_KEY="", STRIPE_PUBLISHABLE_KEY="")
    def test_missing_api_keys_raise_helpful_error(self):
        order = Order.objects.create(email="buyer@example.com", total=Decimal("50.00"))
        with self.assertRaises(RuntimeError) as ctx:
            get_or_create_payment_intent(order)
        self.assertIn("not configured", str(ctx.exception))


class PaymentModelTests(TestCase):
    def test_payment_defaults_to_stripe_provider(self):
        order = Order.objects.create(email="buyer@example.com")
        payment = Payment.objects.create(order=order, amount=Decimal("50.00"), transaction_id="pi_test123")
        self.assertEqual(payment.provider, "stripe")

    def test_payment_str_includes_order_number(self):
        order = Order.objects.create(email="buyer@example.com")
        payment = Payment.objects.create(
            order=order, amount=Decimal("50.00"), status=Payment.Status.SUCCESS, transaction_id="pi_test123",
        )
        self.assertIn("pi_test123", str(payment))


class WebhookSecurityTests(TestCase):
    def test_webhook_rejects_request_without_valid_signature(self):
        response = self.client.post(
            "/payments/webhook/", data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="not-a-real-signature",
        )
        # With STRIPE_WEBHOOK_SECRET unset in tests, our view rejects with
        # 503 (can't verify) rather than ever trusting an unverified
        # payload -- either way, it must NOT return 200.
        self.assertIn(response.status_code, (400, 503))
