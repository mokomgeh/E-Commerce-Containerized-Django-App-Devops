"""
apps.cart.cart
================
A real, functional session-backed shopping cart.

Why session-based instead of a DB model? A cart needs to work for
anonymous visitors *before* they create an account -- forcing login just
to add an item to a cart is a well-known conversion killer. Django's
session framework already gives us a signed, server-side (or
cache-backed) per-visitor store, so we use it directly: the cart's
contents are a small dict stored under request.session['cart'], keyed by
product id, e.g. {"42": {"quantity": 2, "price": "19.99"}}.

Because sessions persist across requests via a cookie, this cart survives
page loads, browser tabs, and (with SESSION_ENGINE pointed at the DB or
cache, as configured in settings) even server restarts -- it is not lost
on refresh, which is the #1 complaint about naive "cart in a global
variable" implementations.
"""
from decimal import Decimal

from django.conf import settings

from apps.catalog.models import Product

CART_SESSION_KEY = "cart"


class Cart:
    """
    A thin wrapper around request.session that provides list/add/update/
    remove/clear operations and computed totals. Instantiate once per
    request: `cart = Cart(request)`.
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if cart is None:
            cart = self.session[CART_SESSION_KEY] = {}
        self.cart = cart

    def add(self, product: Product, quantity: int = 1, override_quantity: bool = False):
        """Add a product to the cart, or update its quantity if already present."""
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                "quantity": 0,
                # Snapshot the price at add-time. This is intentional: if
                # the store changes a price after a customer adds an item,
                # their cart honors the price they saw (a common e-commerce
                # UX expectation), until they explicitly re-add/refresh it.
                "price": str(product.current_price),
            }
        if override_quantity:
            self.cart[product_id]["quantity"] = quantity
        else:
            self.cart[product_id]["quantity"] += quantity

        # Never let a cart line exceed available stock.
        self.cart[product_id]["quantity"] = max(0, min(self.cart[product_id]["quantity"], product.stock_quantity))
        if self.cart[product_id]["quantity"] == 0:
            del self.cart[product_id]
        self.save()

    def remove(self, product: Product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self):
        # Flag the session as modified so Django knows to persist the
        # (mutated-in-place) dict back to the session store.
        self.session.modified = True

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self.save()

    def __iter__(self):
        """
        Yield each cart line enriched with the live Product object and
        computed subtotal, so templates can render everything without
        extra queries per line.
        """
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids).select_related("category", "department")
        products_map = {str(p.id): p for p in products}

        for product_id, item in self.cart.items():
            product = products_map.get(product_id)
            if product is None:
                continue  # product was deleted since being added to cart
            price = Decimal(item["price"])
            quantity = item["quantity"]
            yield {
                "product": product,
                "price": price,
                "quantity": quantity,
                "subtotal": price * quantity,
            }

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    @property
    def total_price(self) -> Decimal:
        return sum((Decimal(item["price"]) * item["quantity"] for item in self.cart.values()), Decimal("0.00"))

    @property
    def is_empty(self) -> bool:
        return len(self.cart) == 0
