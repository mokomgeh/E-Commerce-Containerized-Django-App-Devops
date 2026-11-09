from django.contrib import admin

from .models import (Category, Department, Product, ProductImage,
                      ProductSpecification)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "display_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "parent", "is_active", "display_order")
    list_filter = ("department", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "sku", "department", "category", "price", "discount_price",
        "stock_quantity", "is_active", "is_featured", "average_rating",
    )
    list_filter = ("department", "category", "is_active", "is_featured")
    search_fields = ("name", "sku", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductSpecificationInline]
    fieldsets = (
        (None, {"fields": ("department", "category", "name", "slug", "sku")}),
        ("Descriptions", {"fields": ("short_description", "description")}),
        ("Pricing & stock", {"fields": ("price", "discount_price", "stock_quantity", "weight_kg")}),
        ("Visibility", {"fields": ("is_active", "is_featured")}),
    )
