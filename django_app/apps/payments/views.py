"""
apps.payments.views
=====================
Renders the Stripe Payment Element and confirms payments through two
independent, idempotent paths:

  * `payment_return` -- the customer's browser lands here after Stripe.js
    confirms the payment client-side. Good for immediate UX (redirect
    straight to the order confirmation page).
  * `stripe_webhook` -- Stripe calls this server-to-server whenever a
    PaymentIntent's status changes. This is the *durable* source of
    truth: it still fires even if the customer's browser never makes it
    back (closed tab, dropped connection, etc.), which is exactly the
    gap a redirect-only integration leaves open.

Both paths funnel through the same `_finalize_successful_payment()`
helper, guarded so that finalizing an already-paid order is a safe no-op
-- whichever path arrives first "wins" and the other becomes a no-op.
"""
import json

import stripe
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# from apps.analytics.models import PurchaseEvent
from apps.orders.models import Order

from .models import Payment
from .services import (construct_webhook_event, get_or_create_payment_intent,
                        retrieve_payment_intent)


def checkout(request, order_number):
    """GET: create/reuse a PaymentIntent and render the Stripe Payment Element."""
    order = get_object_or_404(Order, order_number=order_number, status=Order.Status.PENDING)
    # Always re-derive the total from line items right before charging --
    # never trust a stale value from earlier in the checkout flow.
    order.recalculate_totals()

    try:
        intent, payment = get_or_create_payment_intent(order)
        client_secret, error = intent.client_secret, None
    except RuntimeError as exc:
        client_secret, error = None, str(exc)

    return_url = request.build_absolute_uri(reverse("payments:payment_return", args=[order.order_number]))
    return render(request, "payments/checkout.html", {
        "order": order,
        "client_secret": client_secret,
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "return_url": return_url,
        "config_error": error,
    })


def payment_return(request, order_number):
    """
    GET: the customer's browser lands here after Stripe.js redirects
    following `stripe.confirmPayment()`. Stripe appends `payment_intent`
    and `redirect_status` query params -- we don't trust those blindly,
    we re-fetch the PaymentIntent from Stripe's API to get its actual,
    server-verified status before doing anything.
    """
    order = get_object_or_404(Order, order_number=order_number)
    intent_id = request.GET.get("payment_intent")

    if not intent_id:
        messages.error(request, "We couldn't confirm your payment. Please try again.")
        return redirect("payments:checkout", order_number=order.order_number)

    intent = retrieve_payment_intent(intent_id)
    payment = get_object_or_404(Payment, transaction_id=intent_id, order=order)

    if intent.status == "succeeded":
        _finalize_successful_payment(payment, intent)
        messages.success(request, "Payment successful! Thank you for your order.")
        return redirect("orders:order_detail", order_number=order.order_number)

    # Not yet succeeded (e.g. still requires_action, or failed outright).
    payment.status = Payment.Status.FAILED
    payment.raw_response = {"status": intent.status}
    payment.save(update_fields=["status", "raw_response", "updated_at"])
    messages.error(request, f"Payment was not completed (status: {intent.status}). Please try again.")
    return redirect("payments:checkout", order_number=order.order_number)


def _finalize_successful_payment(payment, intent):
    """
    Mark a payment (and its order) as paid, exactly once. Called from
    both `payment_return` and `stripe_webhook`, so it's written to be
    safely re-entrant: if the order is already paid, this is a no-op.
    """
    order = payment.order
    if order.status == Order.Status.PAID:
        return  # already finalized by the other confirmation path

    with transaction.atomic():
        payment.status = Payment.Status.SUCCESS
        payment.raw_response = {"status": intent.status, "id": intent.id}
        payment.save(update_fields=["status", "raw_response", "updated_at"])

        order.mark_as_paid()

        if order.coupon_id:
            order.coupon.times_used += 1
            order.coupon.save(update_fields=["times_used"])

        # # Fan out one analytics PurchaseEvent per order line so the
        # # recommendation engine's "frequently bought together" and any
        # # purchase-based dashboards have granular data.
        # for item in order.items.all():
        #     if item.product_id:
        #         PurchaseEvent.objects.create(
        #             product=item.product, order=order,
        #             user=order.user, quantity=item.quantity, unit_price=item.unit_price,
        #         )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Stripe calls this endpoint server-to-server on payment events --
    configure it in the Stripe dashboard (or via `stripe listen --forward-to
    localhost:8000/payments/webhook/` for local testing) pointed at this
    URL. This is the *durable* confirmation path: unlike `payment_return`,
    it doesn't depend on the customer's browser successfully redirecting
    back, so it catches cases like a closed tab or a network drop right
    after a successful charge.

    Every request's signature is verified against STRIPE_WEBHOOK_SECRET
    before we trust anything in the payload -- this is what stops anyone
    else from POSTing a fake "payment succeeded" event at us.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponseBadRequest("Invalid signature")
    except RuntimeError:
        # Webhook secret not configured -- can't safely verify, so reject
        # rather than silently trusting an unverified payload.
        return HttpResponse(status=503)

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        try:
            payment = Payment.objects.select_related("order").get(transaction_id=intent["id"])
        except Payment.DoesNotExist:
            return HttpResponse(status=200)  # nothing we know about; acknowledge and ignore
        _finalize_successful_payment(payment, intent)

    elif event["type"] == "payment_intent.payment_failed":
        intent = event["data"]["object"]
        Payment.objects.filter(transaction_id=intent["id"]).update(
            status=Payment.Status.FAILED, raw_response={"status": intent.get("status")}
        )

    return HttpResponse(status=200)
