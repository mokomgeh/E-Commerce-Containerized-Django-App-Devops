"""
Makes `cart` available in every template (e.g. for the header's cart
icon/item-count badge) without every view having to pass it explicitly.
Registered in config/settings.py TEMPLATES['OPTIONS']['context_processors'].
"""
from .cart import Cart


def cart(request):
    return {"cart": Cart(request)}