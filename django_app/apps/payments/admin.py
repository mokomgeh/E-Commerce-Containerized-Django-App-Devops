from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "transaction_id", "amount", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("transaction_id", "order__order_number")
    readonly_fields = ("raw_response",)
