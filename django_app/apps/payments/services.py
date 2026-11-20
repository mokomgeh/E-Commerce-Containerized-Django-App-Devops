"""
apps.payments.services
========================
Stripe integration (Test mode by default -- flip to a live secret key in
your deployment env vars once you're ready to take real payments).

Uses the modern **PaymentIntent + Payment Element** pattern:

  1. The server creates (or reuses) a PaymentIntent for the order's total
     and returns its `client_secret` to the browser.
  2. Stripe.js renders the Payment Element -- a hosted, PCI-compliant
     card form -- using that client_secret.
  3. On submit, Stripe.js confirms the payment client-side and redirects
     the browser to our `return_url` with the PaymentIntent id attached.
  4. Our `payment_return` view re-verifies that PaymentIntent's status
     server-to-server via the Stripe API before ever marking an order as
     paid.

Card numbers never touch our server -- only the PaymentIntent id/secret
does -- which is the PCI-compliance benefit of using a hosted gateway
instead of rolling your own card processing. A Stripe webhook
(`apps/payments/views.stripe_webhook`) provides a second, more durable
confirmation path in case the browser never makes it back to step 4
(closed tab, network drop, etc.) -- see that view's docstring.
"""
import stripe
from django.conf import settings


def _configure():
    """
    Point the Stripe SDK at our secret key, failing loudly and helpfully
    if it isn't set yet (the common state for a fresh clone of this repo)
    instead of letting a low-level Stripe auth error bubble up.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError(
            "Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY "
            "in your .env file. Get free test-mode keys at https://dashboard.stripe.com/test/apikeys."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


def get_or_create_payment_intent(order):
    """
    Reuse a still-pending PaymentIntent for this order if one exists
    (e.g. the customer refreshed the payment page), otherwise create a
    fresh one. Returns (stripe_payment_intent, Payment).

    Reusing rather than always creating avoids leaving a trail of
    abandoned PaymentIntents in the Stripe dashboard every time someone
    reloads the checkout page, and keeps the amount in sync if the order
    total changed (e.g. a coupon was applied) since the intent was made.
    """
    from .models import Payment  # local import avoids a circular import at module load time

    _configure()
    amount_cents = int((order.total * 100).to_integral_value())

    existing = (
        order.payments.filter(provider="stripe", status=Payment.Status.PENDING)
        .exclude(transaction_id="")
        .order_by("-created_at")
        .first()
    )
    if existing:
        try:
            intent = stripe.PaymentIntent.retrieve(existing.transaction_id)
            if intent.status in ("requires_payment_method", "requires_confirmation", "requires_action"):
                if intent.amount != amount_cents:
                    intent = stripe.PaymentIntent.modify(intent.id, amount=amount_cents)
                return intent, existing
        except stripe.error.InvalidRequestError:
            pass  # the stored intent id is stale/invalid -- fall through and create a new one

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=order.currency if hasattr(order, "currency") else "usd",
        automatic_payment_methods={"enabled": True},
        metadata={"order_number": str(order.order_number)},
    )
    payment = Payment.objects.create(
        order=order, provider="stripe", transaction_id=intent.id,
        amount=order.total, status=Payment.Status.PENDING,
    )
    return intent, payment


def retrieve_payment_intent(payment_intent_id):
    """Fetch the current, authoritative status of a PaymentIntent from Stripe."""
    _configure()
    return stripe.PaymentIntent.retrieve(payment_intent_id)


def construct_webhook_event(payload, sig_header):
    """
    Verify and parse an incoming Stripe webhook payload using our webhook
    signing secret. Raises stripe.error.SignatureVerificationError (or
    ValueError for a malformed payload) if the request didn't actually
    come from Stripe -- callers must treat that as a rejected request,
    never process the payload.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError(
            "STRIPE_WEBHOOK_SECRET is not configured. Set it in your .env file using the "
            "signing secret shown when you add a webhook endpoint in the Stripe dashboard "
            "(or from `stripe listen` when testing locally)."
        )
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
