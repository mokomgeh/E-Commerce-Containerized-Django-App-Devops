"""
apps.catalog.filters
======================
django-filter FilterSet powering the product search/listing page:
price range, department, category, minimum rating, in-stock-only, and
free-text search across name/description -- plus a `sort` field for
ordering. Kept as a FilterSet (rather than hand-rolled query building in
the view) so the same filter definitions can back both the HTML search
page and, later, a DRF API endpoint with zero duplication.
"""
import django_filters
from django.db.models import Q

from .models import Category, Department, Product


class ProductFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_search", label="Search")
    department = django_filters.ModelChoiceFilter(queryset=Department.objects.filter(is_active=True))
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_rating = django_filters.NumberFilter(field_name="average_rating", lookup_expr="gte")
    in_stock_only = django_filters.BooleanFilter(method="filter_in_stock", label="In stock only")
    on_sale_only = django_filters.BooleanFilter(method="filter_on_sale", label="On sale only")

    sort = django_filters.ChoiceFilter(
        method="filter_sort",
        label="Sort by",
        choices=[
            ("-created_at", "Newest"),
            ("price", "Price: Low to High"),
            ("-price", "Price: High to Low"),
            ("-average_rating", "Highest Rated"),
            ("-review_count", "Most Reviewed"),
        ],
    )

    class Meta:
        model = Product
        fields = ["department", "category", "min_price", "max_price", "min_rating"]

    def filter_search(self, queryset, name, value):
        # Search across name, short/long description, and SKU. Using Q
        # objects rather than a full-text-search backend keeps this
        # portable to SQLite for local dev; swap in Postgres's
        # SearchVector for production-scale relevance ranking.
        return queryset.filter(
            Q(name__icontains=value)
            | Q(short_description__icontains=value)
            | Q(description__icontains=value)
            | Q(sku__icontains=value)
        )

    def filter_in_stock(self, queryset, name, value):
        return queryset.filter(stock_quantity__gt=0) if value else queryset

    def filter_on_sale(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(discount_price__isnull=False, discount_price__gt=0)

    def filter_sort(self, queryset, name, value):
        return queryset.order_by(value)

    def filter_category(self, queryset, name, value):
        # Not directly used (ModelChoiceFilter handles equality by
        # default) but documented here: view-level code expands the
        # chosen category to include descendants via
        # Category.get_descendant_ids() *before* this filterset runs,
        # so "Electronics" also returns "Gaming Laptops" products.
        return queryset
