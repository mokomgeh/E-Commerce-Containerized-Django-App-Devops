"""
apps.accounts.tests
=====================
Covers the "one default address per type per user" invariant and basic
signup flow.
"""
from django.test import TestCase
from django.urls import reverse

from .models import Address, User


class AddressDefaultTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jane", password="testpass123", email="jane@example.com")

    def test_only_one_default_shipping_address_per_user(self):
        a1 = Address.objects.create(
            user=self.user, address_type=Address.AddressType.SHIPPING, full_name="Jane Doe",
            address_line_1="1 First St", city="Ottawa", state_province="ON", postal_code="K1A0B1",
            country="Canada", is_default=True,
        )
        a2 = Address.objects.create(
            user=self.user, address_type=Address.AddressType.SHIPPING, full_name="Jane Doe",
            address_line_1="2 Second St", city="Ottawa", state_province="ON", postal_code="K1A0B2",
            country="Canada", is_default=True,
        )
        a1.refresh_from_db()
        self.assertFalse(a1.is_default)
        self.assertTrue(a2.is_default)

    def test_guest_address_has_no_user(self):
        address = Address.objects.create(
            user=None, address_type=Address.AddressType.SHIPPING, full_name="Guest Buyer",
            address_line_1="3 Third St", city="Ottawa", state_province="ON", postal_code="K1A0B3",
            country="Canada",
        )
        self.assertIsNone(address.user)


class SignUpTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(reverse("accounts:signup"), {
            "username": "newuser", "email": "new@example.com", "phone_number": "",
            "password1": "SuperSecret123!", "password2": "SuperSecret123!",
        })
        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertEqual(response.status_code, 302)
