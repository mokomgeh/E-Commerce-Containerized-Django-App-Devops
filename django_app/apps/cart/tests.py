"""
apps.cart.tests
=================
The cart is session-backed rather than DB-backed, so these tests exercise
it through Django's test client (which maintains a session/cookie jar
automatically) rather than instantiating Cart() directly against a bare
request object.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Department, Product


class CartTests(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Electronics")
        category = Category.objects.create(department=department, name="Phones")
        self.product = Product.objects.create(
            department=department, category=category, name="Smartphone",
            sku="PHN-001", price=Decimal("500.00"), stock_quantity=3,
        )

    def test_add_to_cart_increases_item_count(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 2})
        response = self.client.get(reverse("cart:cart_detail"))
        self.assertContains(response, "Smartphone")
        self.assertContains(response, "$1000.00" if False else "1000.00")  # subtotal 2 x 500

    def test_cart_cannot_exceed_stock(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 99})
        session = self.client.session
        self.assertEqual(session["cart"][str(self.product.id)]["quantity"], self.product.stock_quantity)

    def test_remove_from_cart(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 1})
        self.client.post(reverse("cart:cart_remove", args=[self.product.id]))
        session = self.client.session
        self.assertNotIn(str(self.product.id), session.get("cart", {}))

    def test_update_cart_quantity(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 1})
        self.client.post(reverse("cart:cart_update", args=[self.product.id]), {"quantity": 2})
        session = self.client.session
        self.assertEqual(session["cart"][str(self.product.id)]["quantity"], 2)

    def test_out_of_stock_product_cannot_be_added(self):
        self.product.stock_quantity = 0
        self.product.save()
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 1})
        session = self.client.session
        self.assertNotIn(str(self.product.id), session.get("cart", {}))
