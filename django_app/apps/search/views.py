"""
apps.search.views
===================
Lightweight JSON search-suggestions endpoint used by the navbar search
box for live autocomplete (separate from the full search+filter page in
apps.catalog, which handles the actual results page). Kept as its own
small app/endpoint because "autocomplete-as-you-type" has different
performance requirements (fast, few fields, no pagination) than a full
listing query.
"""
from django.http import JsonResponse

from apps.catalog.models import Product


def search_suggestions(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    products = (
        Product.objects.active()
        .filter(name__icontains=query)
        .select_related("category")[:8]
    )
    results = [
        {
            "name": p.name,
            "url": p.get_absolute_url(),
            "price": str(p.current_price),
            "category": p.category.name,
            "image": p.get_primary_image().image.url if p.get_primary_image() else "",
        }
        for p in products
    ]
    return JsonResponse({"results": results})
