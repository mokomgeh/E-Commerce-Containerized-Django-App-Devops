"""
apps.accounts.forms
=====================
Registration, login-adjacent, and address forms.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Address, User


class SignUpForm(UserCreationForm):
    """Extends Django's built-in UserCreationForm with our extra fields."""
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "phone_number", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class AddressForm(forms.ModelForm):
    """Create/update form for a billing or shipping address."""

    class Meta:
        model = Address
        fields = [
            "address_type", "full_name", "company", "address_line_1",
            "address_line_2", "city", "state_province", "postal_code",
            "country", "phone_number", "is_default",
        ]
        widgets = {
            "address_type": forms.Select(attrs={"class": "form-select"}),
        }
