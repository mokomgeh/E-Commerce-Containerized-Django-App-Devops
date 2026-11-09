"""
apps.catalog.views
====================
Storefront browsing: department/category pages, product detail, and the
combined search + filter listing page. Every product-facing view also
feeds the analytics app (page views, search queries) so the
recommendation engine has real behavioral data to work with.
"""
from django.shortcuts import get_object_or_404, render

from .models import Department, Product


def home(request):
    """Storefront homepage: featured products + trending rail."""
    context = {
        "departments": Department.objects.filter(is_active=True),
        "featured_products": Product.objects.active().filter(is_featured=True)[:8],
    }
    return render(request, "catalog/home.html", context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("department", "category").prefetch_related("images", "specifications", "reviews"),
        slug=slug, is_active=True,
    )

    context = {
        "product": product,
    }
    return render(request, "catalog/product_detail.html", context)