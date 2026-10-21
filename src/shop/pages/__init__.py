"""Page objects of the Demo Web Shop."""

from shop.pages.base import BasePage, ListingPage
from shop.pages.cart import CartPage
from shop.pages.category import CategoryPage
from shop.pages.login import LoginPage
from shop.pages.product import ProductPage
from shop.pages.register import RegisterPage
from shop.pages.search import SearchPage

__all__ = [
    "BasePage",
    "CartPage",
    "CategoryPage",
    "ListingPage",
    "LoginPage",
    "ProductPage",
    "RegisterPage",
    "SearchPage",
]
