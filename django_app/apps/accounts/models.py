import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

class User(AbstractUser):
    """
    Custom user model.

    Adds an e-commerce-relevant profile surface (phone number, a public
    UUID that is safe to expose in URLs/receipts instead of the numeric PK,
    and marketing opt-in) on top of Django's built-in auth fields
    (username, email, password, is_active, date_joined, etc.).
    """    
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True) # UUID for security and against ID enumeration

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)

    accepts_marketing = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_default_address(self, address_type=None):
        """Return the user's default address, optionally filtered by type."""
        qs = self.addresses.filter(is_default=True)
        if address_type:
            qs = qs.filter(address_type=address_type)
        return qs.first()


class Address(models.Model):
    """
    A single billing or shipping address belonging to a user.

    A user can have many addresses (home, work, gift-recipient, etc.) but
    only one *default* address per type. We enforce that invariant in
    save() rather than at the DB layer because SQLite (used in dev) has
    limited support for partial unique constraints across Django versions;
    the application-level guarantee keeps the code portable across
    database backends.
    """

    class AddressType(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="addresses",
        null=True, blank=True,
        help_text="Blank for a one-off address captured during guest checkout.",
    )
    address_type = models.CharField(max_length=10, choices=AddressType.choices)

    full_name = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "addresses"
        ordering = ["-is_default", "-updated_at"]

    def __str__(self):
        return f"{self.full_name} - {self.address_line_1}, {self.city} ({self.get_address_type_display()})"

    def save(self, *args, **kwargs):
        # If this address is being marked default, unset any other default
        # address of the same type for the same user first. This keeps
        # "one default per type per user" true without a database constraint.
        # Guest checkout addresses have no user, so there's nothing to
        # de-duplicate against.
        if self.is_default and self.user_id is not None:
            Address.objects.filter(
                user=self.user, address_type=self.address_type, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("accounts:address_detail", kwargs={"pk": self.pk})
