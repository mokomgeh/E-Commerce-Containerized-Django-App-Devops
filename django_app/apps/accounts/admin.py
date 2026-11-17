from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Address, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Reuses Django's polished UserAdmin (password change widgets, groups,
    permissions UI) and just adds our extra fields to the display/fieldsets.
    """
    list_display = ("username", "email", "phone_number", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email", "phone_number")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Store profile", {"fields": ("phone_number", "accepts_marketing")}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "address_type", "full_name", "city", "country", "is_default")
    list_filter = ("address_type", "is_default", "country")
    search_fields = ("user__username", "full_name", "city", "postal_code")
