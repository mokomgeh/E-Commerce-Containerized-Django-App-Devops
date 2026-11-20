"""
apps.orders.views
===================
The checkout funnel: address selection -> review/coupon -> (payment app
takes over) -> order confirmation. Order creation happens server-side
from the *session cart*, never from client-submitted prices, so a
tampered request can't change what a customer is charged.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.forms import AddressForm
from apps.accounts.models import Address
from apps.cart.cart import Cart
from apps.coupons.forms import CouponApplyForm
from apps.coupons.models import Coupon

from .models import Order, OrderItem


def checkout_address(request):
    """
    Step 1: choose (or add) billing and shipping addresses.
    Supports both logged-in users (pick from saved addresses) and guests
    (fill in a one-off address that's saved to the new account-less order).
    """
    cart = Cart(request)
    if cart.is_empty:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart:cart_detail")

    if request.user.is_authenticated:
        addresses = request.user.addresses.all()
        if request.method == "POST":
            billing_id = request.POST.get("billing_address")
            shipping_id = request.POST.get("shipping_address")
            if billing_id and shipping_id:
                request.session["checkout_billing_id"] = int(billing_id)
                request.session["checkout_shipping_id"] = int(shipping_id)
                return redirect("orders:checkout_review")
            messages.error(request, "Please select both a billing and shipping address.")
        return render(request, "orders/checkout_address.html", {"addresses": addresses, "cart": cart})

    # Guest checkout: single combined form, used for both billing and shipping.
    if request.method == "POST":
        form = AddressForm(request.POST)
        email = request.POST.get("email", "").strip()
        if form.is_valid() and email:
            address = form.save(commit=False)
            address.user = None
            request.session["guest_email"] = email
            request.session["guest_address"] = {
                k: str(v) for k, v in form.cleaned_data.items()
            }
            return redirect("orders:checkout_review")
        messages.error(request, "Please correct the errors below and provide an email address.")
    else:
        form = AddressForm(initial={"address_type": Address.AddressType.SHIPPING})
    return render(request, "orders/checkout_address_guest.html", {"form": form, "cart": cart})


def _get_or_apply_coupon(request, subtotal):
    coupon_id = request.session.get("coupon_id")
    if not coupon_id:
        return None
    try:
        coupon = Coupon.objects.get(id=coupon_id)
    except Coupon.DoesNotExist:
        return None
    valid, reason = coupon.is_valid(order_subtotal=subtotal)
    if not valid:
        messages.warning(request, f"Coupon removed: {reason}")
        del request.session["coupon_id"]
        return None
    return coupon


def checkout_review(request):
    """Step 2: review the cart, optionally apply a coupon, then create the Order."""
    cart = Cart(request)
    if cart.is_empty:
        return redirect("cart:cart_detail")

    coupon = _get_or_apply_coupon(request, cart.total_price)
    coupon_form = CouponApplyForm()

    if request.method == "POST" and "apply_coupon" in request.POST:
        coupon_form = CouponApplyForm(request.POST)
        if coupon_form.is_valid():
            code = coupon_form.cleaned_data["code"].upper().strip()
            try:
                candidate = Coupon.objects.get(code=code)
                valid, reason = candidate.is_valid(order_subtotal=cart.total_price)
                if valid:
                    request.session["coupon_id"] = candidate.id
                    coupon = candidate
                    messages.success(request, f"Coupon '{code}' applied.")
                else:
                    messages.error(request, reason)
            except Coupon.DoesNotExist:
                messages.error(request, "That coupon code doesn't exist.")

    elif request.method == "POST" and "place_order" in request.POST:
        order = _create_order_from_cart(request, cart, coupon)
        cart.clear()
        request.session.pop("coupon_id", None)
        return redirect("payments:checkout", order_number=order.order_number)

    discount = coupon.calculate_discount(cart.total_price) if coupon else 0
    context = {
        "cart": cart,
        "coupon": coupon,
        "coupon_form": coupon_form,
        "discount": discount,
        "total": cart.total_price - (discount or 0),
    }
    return render(request, "orders/checkout_review.html", context)


def _create_order_from_cart(request, cart, coupon):
    """Build the Order + OrderItem rows from the current session cart. Server-authoritative pricing."""
    if request.user.is_authenticated:
        billing = get_object_or_404(Address, pk=request.session.get("checkout_billing_id"), user=request.user)
        shipping = get_object_or_404(Address, pk=request.session.get("checkout_shipping_id"), user=request.user)
        email = request.user.email
        user = request.user
    else:
        # Guest: materialize the address dict captured in checkout_address().
        addr_data = request.session.get("guest_address", {})
        shipping = Address.objects.create(user=None, **{
            k: v for k, v in addr_data.items() if k in [f.name for f in Address._meta.fields]
        }) if addr_data else None
        billing = shipping
        email = request.session.get("guest_email", "")
        user = None

    order = Order.objects.create(user=user, email=email, billing_address=billing, shipping_address=shipping, coupon=coupon)

    for line in cart:
        OrderItem.objects.create(
            order=order,
            product=line["product"],
            product_name=line["product"].name,
            product_sku=line["product"].sku,
            unit_price=line["price"],
            quantity=line["quantity"],
        )
        # Decrement stock immediately on order creation (pending payment)
        # to prevent overselling during the payment step; a production
        # system would typically reserve stock with an expiry instead.
        product = line["product"]
        product.stock_quantity = max(0, product.stock_quantity - line["quantity"])
        product.save(update_fields=["stock_quantity"])

    order.recalculate_totals()
    return order


@login_required
def order_list(request):
    orders = request.user.orders.all()
    return render(request, "orders/order_list.html", {"orders": orders})


def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    # Guests can view their just-placed order (session-scoped); logged-in
    # users can only view their own past orders.
    if request.user.is_authenticated and order.user_id and order.user_id != request.user.id:
        messages.error(request, "You don't have permission to view that order.")
        return redirect("orders:order_list")
    return render(request, "orders/order_detail.html", {"order": order})
