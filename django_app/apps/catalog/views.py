"""
apps.catalog.views
====================
Storefront browsing: department/category pages, product detail, and the
combined search + filter listing page. Every product-facing view also
feeds the analytics app (page views, search queries) so the
recommendation engine has real behavioral data to work with.
"""
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Department, Product, Category
from .filters import ProductFilter

def home(request):
    """Storefront homepage: featured products + trending rail."""
    context = {
        "departments": Department.objects.filter(is_active=True),
        "featured_products": Product.objects.active().filter(is_featured=True)[:8],
    }
    return render(request, "catalog/home.html", context)

def department_detail(request, slug):
    department = get_object_or_404(Department, slug=slug, is_active=True)
    products = Product.objects.active().filter(department=department)
    return _render_filtered_listing(request, products, {"department": department}, "catalog/department_detail.html")


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    # Include products from every descendant category too, so browsing a
    # parent category shows everything nested beneath it.
    descendant_ids = category.get_descendant_ids()
    products = Product.objects.active().filter(category_id__in=descendant_ids)
    return _render_filtered_listing(request, products, {"category": category}, "catalog/category_detail.html")


def product_search(request):
    """The main search + filter page, used for both free-text search and pure filter browsing."""
    products = Product.objects.active().select_related("department", "category")
    return _render_filtered_listing(request, products, {}, "catalog/product_search.html", track_query=True)


def _render_filtered_listing(request, base_queryset, extra_context, template, track_query=False):
    """
    Shared plumbing for every product-listing page: apply the
    ProductFilter (search text, price range, rating, stock, sort), then
    paginate. Centralizing this means product_search/department_detail/
    category_detail all behave identically instead of drifting apart.
    """
    product_filter = ProductFilter(request.GET, queryset=base_queryset)
    filtered_qs = product_filter.qs

    paginator = Paginator(filtered_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "filter": product_filter,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        **extra_context,
    }
    return render(request, template, context)

def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("department", "category").prefetch_related("images", "specifications"),
        slug=slug, is_active=True,
    )

    context = {
        "product": product,
    }
    return render(request, "catalog/product_detail.html", context)