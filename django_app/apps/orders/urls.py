from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/address/", views.checkout_address, name="checkout_address"),
    path("checkout/review/", views.checkout_review, name="checkout_review"),
    path("history/", views.order_list, name="order_list"),
    path("<uuid:order_number>/", views.order_detail, name="order_detail"),
]
