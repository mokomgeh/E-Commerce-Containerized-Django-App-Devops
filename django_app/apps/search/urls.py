from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("suggest/", views.search_suggestions, name="suggestions"),
]
