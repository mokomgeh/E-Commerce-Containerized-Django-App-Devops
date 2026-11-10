"""
Injects the active department list into every template's context, so the
navbar (included on every page) can render top-level navigation links
without every single view needing to fetch and pass departments manually.
Cheap: a handful of rows, and Department is rarely written to, so this
query is effectively free relative to page render cost.
"""
from .models import Department


def departments_nav(request):
    return {"departments_nav": Department.objects.filter(is_active=True)}
