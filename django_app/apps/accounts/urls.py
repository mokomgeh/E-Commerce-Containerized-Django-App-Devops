from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("addresses/", views.address_list, name="address_list"),
    path("addresses/new/", views.address_create, name="address_create"),
    path("addresses/<int:pk>/edit/", views.address_update, name="address_update"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
]
