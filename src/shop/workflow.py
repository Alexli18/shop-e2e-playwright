"""The shopping scenario: the four assignment functions built on the page objects."""

from decimal import Decimal
import logging
import random
import secrets
import uuid

import allure
from playwright.sync_api import Page

from shop.artifacts import RunArtifacts
from shop.base_workflow import BaseWorkflow
from shop.collector import ProductCollector
from shop.config import Credentials
from shop.models import AddedItem, AddStatus, CartSnapshot, RunResult, SearchOutcome, ShoppingCase, TextFieldData
from shop.pages import CartPage, LoginPage, ProductPage, RegisterPage, SearchPage

log = logging.getLogger(__name__)


def _test_address() -> str:
    return f"qa_{uuid.uuid4().hex[:8]}@example.com"


def new_account() -> Credentials:
    """Unique throw-away account for one run."""
    return Credentials(_test_address(), secrets.token_urlsafe(12))


class ShoppingWorkflow(BaseWorkflow):
    """Search -> add to cart -> budget check, on one browser page (the 'search tab')."""

    def __init__(
        self,
        page: Page,
        base_url: str,
        artifacts: RunArtifacts,
        credentials: Credentials | None = None,
        seed: int | None = None,
        max_quantity: int = 1,
    ) -> None:
        super().__init__(page, base_url, artifacts)
        self._credentials = credentials
        self._rng = random.Random(seed)
        # 1 (the assignment): one unit per item. > 1 (opt-in per case): a random quantity per item.
        self.max_quantity = max_quantity
        self._text_data = TextFieldData(name="QA Tester", email=_test_address())
        self.last_search = SearchOutcome([], [])

    def authenticate(self) -> str:
        """Log in with the given account, or register a new one and log in with it; return the email."""
        if self._credentials is not None:
            with allure.step(f"Log in as {self._credentials.email}"):
                LoginPage(self.page, self.base_url).open().log_in(self._credentials)
                CartPage(self.page, self.base_url).open().clear()  # existing accounts may keep old items
            self.artifacts.log("authenticated", mode="existing account", email=self._credentials.email)
            return self._credentials.email
        credentials = new_account()
        with allure.step(f"Register {credentials.email} and log in"):
            register = RegisterPage(self.page, self.base_url).open()
            register.register("QA", "Automation", credentials)  # registration logs the user in ...
            register.header.log_out()  # ... so log out and back in to prove the new credentials work
            LoginPage(self.page, self.base_url).open().log_in(credentials)
        self.artifacts.log("authenticated", mode="registered new user", email=credentials.email)
        return credentials.email

    def search_items_by_name_under_price(
        self, query: str, max_price: Decimal, limit: int = 5, in_descriptions: bool = False
    ) -> list[str]:
        """URLs of the first `limit` products priced <= max_price (an empty list is a valid result).

        Uses the page's price filter, re-checks every price, and follows the pager when page 1 is not enough.
        """
        max_price = Decimal(str(max_price))
        self.last_search = SearchOutcome([], [])
        if limit <= 0:
            return []
        with allure.step(f"Search '{query}' priced up to {max_price}, limit {limit}"):
            page = SearchPage(self.page, self.base_url).open().search(query, max_price, in_descriptions)
            self.last_search = ProductCollector(page.grid, page.pager).collect(max_price, limit)
            products = self.last_search.products
            self.artifacts.log(
                "search",
                query=query,
                max_price=max_price,
                limit=limit,
                in_descriptions=in_descriptions,
                pages=self.last_search.pages,
                found=products,
            )
            self._screenshot(f"search {query}")
        return [product.url for product in products]

    def add_items_to_cart(self, urls: list[str]) -> list[AddedItem]:
        """Open each product in its own tab, choose random options, add it, close the tab.

        Closing the tab returns to the search tab, which stays on the results page throughout.
        """
        items = []
        with allure.step(f"Add {len(urls)} item(s) to the cart"):
            for index, url in enumerate(urls, start=1):
                with allure.step(f"Item {index}: {url.removeprefix(self.base_url)}"):
                    items.append(self._add_in_new_tab(url))
        return items

    def _add_in_new_tab(self, url: str) -> AddedItem:
        tab = self.page.context.new_page()
        try:
            product = ProductPage(tab, self.base_url).open_url(url)
            item = self._add_one(product)
            shot = self._screenshot(f"{item.status} {item.title}", page=tab)
            counter = product.header.cart_quantity()
        except Exception as error:
            self._failure_screenshot(tab, url)  # while the tab is still open
            self.artifacts.log("add_to_cart_error", url=url, error=f"{type(error).__name__}: {error}")
            raise
        finally:
            tab.close()
            self.page.bring_to_front()
        self.artifacts.log("add_to_cart", item=item, cart_counter=counter, screenshot=shot.name)
        return item

    def _failure_screenshot(self, tab: Page, url: str) -> None:
        try:
            self._screenshot(f"failed {url.rsplit('/', 1)[-1]}", page=tab)
        except Exception:  # noqa: BLE001 - the original error matters more than a missing screenshot
            log.exception("Could not take the failure screenshot of %s", url)

    def _add_one(self, product: ProductPage) -> AddedItem:
        url, title, price = product.page.url, product.title(), product.price()
        if reason := product.unavailable_reason():
            return AddedItem(url, title, AddStatus.UNAVAILABLE, message=reason, page_price=price)
        if unsupported := product.options.unsupported_fields():
            message = f"Cannot fill {', '.join(unsupported)}"
            return AddedItem(url, title, AddStatus.UNSUPPORTED, message=message, page_price=price)
        options = {**product.options.choose_randomly(self._rng), **product.options.checked_extras()}
        text_fields = product.options.fill_text_fields(self._text_data)
        # One unit by default (the budget is per item); a random 1..max_quantity only when the case opts in.
        # The RNG is not used for quantities otherwise, so the default runs choose the same options as before.
        quantity = self._rng.randint(1, self.max_quantity) if self.max_quantity > 1 else 1
        if quantity > 1:
            product.set_quantity(quantity)
        log.info("%s: page price %s, options %s, quantity %s", title, price, options, quantity)
        notice = product.add_to_cart()
        if notice.success:
            status = AddStatus.ADDED
        elif "out of stock" in notice.text.lower():  # sold out between page load and click (shared demo data)
            status = AddStatus.UNAVAILABLE
        else:
            status = AddStatus.REJECTED
        return AddedItem(url, title, status, options, notice.text, text_fields, quantity, price)

    def assert_cart_total_not_exceeds(self, budget_per_item: Decimal, items_count: int) -> CartSnapshot:
        """Assert the cart Sub-Total (as shown, including option surcharges) <= budget_per_item * items_count."""
        budget = Decimal(str(budget_per_item))
        threshold = budget * items_count
        with allure.step(f"Cart Sub-Total must not exceed {budget} x {items_count} = {threshold}"):
            cart = CartPage(self.page, self.base_url).open().snapshot()
            self._screenshot("cart")
            self.artifacts.log("cart", entries=cart.entries, sub_total=cart.sub_total, threshold=threshold)
            if cart.sub_total > threshold:
                raise AssertionError(f"Cart Sub-Total {cart.sub_total} exceeds {budget} x {items_count} = {threshold}")
        return cart

    def run(self, case: ShoppingCase) -> RunResult:
        self._rng.seed(case.seed)
        self.max_quantity = case.max_quantity
        self.artifacts.log(
            "case",
            name=case.name,
            query=case.query,
            max_price=case.max_price,
            limit=case.limit,
            seed=case.seed,
            in_descriptions=case.search_in_descriptions,
            max_quantity=case.max_quantity,
        )
        self.authenticate()
        urls = self.search_items_by_name_under_price(
            case.query, case.max_price, case.limit, case.search_in_descriptions
        )
        items = self.add_items_to_cart(urls)
        # As in the assignment's example the threshold counts every found URL (len(urls) when quantities are 1):
        # items that could not be added count as one unit, so they make the check looser, never stricter.
        # With random quantities the budget is per unit, so an added item counts its quantity.
        units = sum(item.quantity if item.status is AddStatus.ADDED else 1 for item in items)
        cart = self.assert_cart_total_not_exceeds(case.max_price, units)
        return RunResult(urls, items, cart, self.last_search)
