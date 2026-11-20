from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("<uuid:order_number>/", views.checkout, name="checkout"),
    path("<uuid:order_number>/return/", views.payment_return, name="payment_return"),
    # Server-to-server webhook -- not order-scoped, since Stripe posts
    # every event to one fixed endpoint URL configured in its dashboard.
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
]
