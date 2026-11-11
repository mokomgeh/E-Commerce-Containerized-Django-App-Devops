"""
apps.cart.views
=================
Add/update/remove/view endpoints for the session cart. All mutating
endpoints require POST (never GET) to avoid accidental cart changes from
link prefetching, crawlers, or CSRF -- Django's CSRF middleware protects
the POST forms automatically.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .cart import Cart


def cart_detail(request):
    cart = Cart(request)
    return render(request, "cart/cart_detail.html", {"cart": cart})


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    quantity = int(request.POST.get("quantity", 1))

    if not product.in_stock:
        messages.error(request, f"{product.name} is currently out of stock.")
        return redirect(product.get_absolute_url())

    cart.add(product=product, quantity=quantity)
    messages.success(request, f"Added {product.name} to your cart.")

    next_url = request.POST.get("next") or "cart:cart_detail"
    return redirect(next_url)


@require_POST
def cart_update(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get("quantity", 1))
    cart.add(product=product, quantity=quantity, override_quantity=True)
    return redirect("cart:cart_detail")


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    messages.info(request, f"Removed {product.name} from your cart.")
    return redirect("cart:cart_detail")
