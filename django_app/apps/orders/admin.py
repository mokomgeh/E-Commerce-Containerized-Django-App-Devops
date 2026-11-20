from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "product_sku", "unit_price", "quantity", "line_total")

    def line_total(self, obj):
        return obj.line_total


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "email", "status", "total", "created_at", "paid_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "email", "user__username")
    readonly_fields = ("order_number", "subtotal", "discount_amount", "total", "created_at", "updated_at")
    inlines = [OrderItemInline]
