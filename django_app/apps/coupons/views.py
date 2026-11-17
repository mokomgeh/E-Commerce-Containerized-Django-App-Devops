"""
apps.coupons.views
====================
Applying a coupon code happens inline on the checkout review page (see
apps.orders.views.checkout_review) since validation depends on the
current cart subtotal. This view only handles *removing* an already-
applied coupon from the session.
"""
from django.contrib import messages
from django.shortcuts import redirect


def remove_coupon(request):
    request.session.pop("coupon_id", None)
    messages.info(request, "Coupon removed.")
    return redirect("orders:checkout_review")
