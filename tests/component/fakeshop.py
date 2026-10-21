"""An in-browser fake of demowebshop.tricentis.com for the offline suite.

Every request of the browser context is intercepted with `context.route`: requests to the shop's
base URL are answered from the HTML fixtures in tests/fixtures (modeled on the live markup), and
any other host is aborted, so the suite never touches the network.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
import json
import zlib
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlsplit

from playwright.sync_api import BrowserContext, Request, Route

BASE = "https://demowebshop.tricentis.com"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

SUCCESS_MESSAGE = 'The product has been added to your <a href="/cart">shopping cart</a>'


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def render(template: str, **values: object) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


# ---------------------------------------------------------------- listings ---------------------------


@dataclass(frozen=True)
class Card:
    """One product tile; `price` and `old_price` are shown exactly as given (e.g. '1,200.00')."""

    title: str
    price: str | None
    old_price: str | None = None
    product_id: int = 0

    @property
    def slug(self) -> str:
        return "-".join(self.title.lower().split())

    @property
    def url(self) -> str:
        return f"{BASE}/{self.slug}"

    def html(self) -> str:
        prices = ""
        if self.old_price is not None:
            prices += f'<span class="price old-price">{self.old_price}</span>\n'
        if self.price is not None:
            prices += f'<span class="price actual-price">{self.price}</span>'
        product_id = self.product_id or (zlib.crc32(self.slug.encode()) % 10_000 + 1)
        return render(
            fixture("product_card.html"), id=product_id, href=f"/{self.slug}", title=self.title, prices=prices
        )


def pager_html(current: int, total: int, href: Callable[[int], str]) -> str:
    """Pager exactly like the live one: '<div class="pager"></div>' when there is a single page."""
    if total <= 1:
        return '<div class="pager">\n</div>'
    items = []
    if current > 1:
        items.append(f'<li class="previous-page"><a href="{href(current - 1)}">Previous</a></li>')
    for number in range(1, total + 1):
        if number == current:
            items.append(f'<li class="current-page"><span>{number}</span></li>')
        else:
            items.append(f'<li class="individual-page"><a href="{href(number)}">{number}</a></li>')
    if current < total:
        items.append(f'<li class="next-page"><a href="{href(current + 1)}">Next</a></li>')
    return f'<div class="pager">\n<ul>{"".join(items)}</ul>\n</div>'


def grid_html(cards: list[Card]) -> str:
    return '<div class="product-grid">\n' + "\n".join(card.html() for card in cards) + "\n</div>"


def purchase_html(product: Product) -> str:
    """The product page's .add-to-cart block for `product.purchase` (see Product)."""
    if product.purchase == "missing":
        return ""
    if product.purchase == "none":
        return '<div class="add-to-cart">\n</div>'
    panel = render(fixture("add_to_cart_panel.html"), id=product.product_id)
    if product.purchase == "renamed":
        return panel.replace('value="Add to cart"', 'value="Add to basket"')
    if product.purchase == "wishlist":
        start = panel.index('<input type="button" id="add-to-cart-button')
        end = panel.index(">", start) + 1
        wishlist = (
            f'<input type="button" id="add-to-wishlist-button-{product.product_id}" '
            f'class="button-2 add-to-wishlist-button" value="Add to wishlist">'
        )
        return panel[:start] + wishlist + panel[end:]
    return panel


def no_results_html() -> str:
    return (
        '<div class="search-results">\n<strong class="result">\n'
        "No products were found that matched your criteria.\n</strong>\n"
        '<div class="pager">\n</div>\n</div>'
    )


# ------------------------------------------------------------------ server -----------------------------


@dataclass
class Product:
    slug: str
    product_id: int
    title: str
    price: str = "100.00"
    stock: str | None = "In stock"
    attributes: str = ""  # fixture file name, or ''
    giftcard: str | None = None  # 'virtual' (names + e-mails) or 'physical' (names only)
    sender: tuple[str, str] = ("", "")  # pre-filled sender name / e-mail (logged-in customer)
    # The purchase block, as the live shop renders it: 'cart' (Qty + Add to cart), 'none' (an empty block: the
    # product is not sold online), 'wishlist' (Qty + Add to wishlist only), 'renamed' (the button says "Add to
    # basket": a changed theme), 'missing' (no block at all: a changed theme).
    purchase: str = "cart"
    # attribute field name -> error shown when the form posts no value for it
    required: dict[str, str] = field(default_factory=dict)
    # forced answer of the add-to-cart endpoint, e.g. ["Out of stock"] (sold out after page load)
    forced_errors: list[str] | None = None
    file_required: bool = True  # attributes_file.html only: the upload is mandatory


GIFT_CARD_FIELDS = {  # posted field suffix -> refusal message, as the live shop words it
    "virtual": {
        "RecipientName": "Enter valid recipient name",
        "RecipientEmail": "Enter valid recipient email",
        "SenderName": "Enter valid sender name",
        "SenderEmail": "Enter valid sender email",
    },
    "physical": {"RecipientName": "Enter valid recipient name", "SenderName": "Enter valid sender name"},
}


@dataclass
class Response:
    body: str
    status: int = 200
    content_type: str = "text/html; charset=utf-8"


Handler = Callable[[Request, dict[str, list[str]]], Response]


class FakeShop:
    def __init__(self, context: BrowserContext) -> None:
        self.requests: list[str] = []  # every shop URL requested (method + path?query)
        self.blocked: list[str] = []  # foreign URLs the browser tried to load
        self.cart_count = 0
        self.added: list[tuple[str, dict[str, list[str]]]] = []  # (slug, posted form) of accepted adds
        self.accounts: dict[str, str] = {}  # registered e-mail -> password
        self.logged_in: str | None = None
        self._handlers: dict[str, Handler] = {}
        self._products_by_id: dict[int, Product] = {}
        self._products_by_slug: dict[str, Product] = {}
        context.route("**/*", self._handle)

    # --------------------------------------------------------- page builders

    def page_html(self, body: str) -> str:
        if self.logged_in:
            links = (
                f'<li><a href="/customer/info" class="account">{self.logged_in}</a></li>'
                '<li><a href="/logout" class="ico-logout">Log out</a></li>'
            )
        else:
            links = (
                '<li><a href="/register" class="ico-register">Register</a></li>'
                '<li><a href="/login" class="ico-login">Log in</a></li>'
            )
        return render(
            fixture("layout.html"), body=body, cart_qty=self.cart_count, script=fixture("shop.js"), account_links=links
        )

    def status(self, path: str, status: int, body: str = "error") -> None:
        """Answer `path` with a plain-text body and the given HTTP status (e.g. 500)."""
        self._handlers[path] = lambda _request, _query: Response(body, status=status, content_type="text/plain")

    def html(self, path: str, body: str | Callable[[dict[str, list[str]]], str]) -> None:
        """Serve the page body (or a function of the query string) inside the shop layout at `path`."""

        def handler(_request: Request, query: dict[str, list[str]]) -> Response:
            return Response(self.page_html(body(query) if callable(body) else body))

        self._handlers[path] = handler

    def category(self, slug: str, pages: list[list[Card]]) -> str:
        """A category listing with one page per entry of `pages`; returns its URL."""
        return self._listing(slug, lambda number: pages[number - 1] if pages else [], lambda _number: len(pages))

    def endless_category(self, slug: str, price: str) -> str:
        """A listing whose pager never ends: page n shows one card 'Item n' and always a Next link."""
        return self._listing(slug, lambda number: [Card(f"Item {number}", price)], lambda number: number + 1)

    def _listing(self, slug: str, cards_on: Callable[[int], list[Card]], total_on: Callable[[int], int]) -> str:
        path = f"/{slug}"

        def body(query: dict[str, list[str]]) -> str:
            number = int(query.get("pagenumber", ["1"])[0])
            return (
                f'<div class="page category-page"><div class="page-title"><h1>{slug}</h1></div>'
                f'<div class="page-body">{grid_html(cards_on(number))}'
                f"{pager_html(number, total_on(number), lambda n: f'{path}?pagenumber={n}')}</div></div>"
            )

        self.html(path, body)
        return BASE + path

    def search(self, pages: list[list[Card]], price_filter: bool = True, descriptions_option: bool = True) -> None:
        """/search: the live form; with `Q` in the query, result page `pagenumber` of `pages`."""
        advanced = fixture("search_advanced.html")
        toggle, block = advanced.split("<!--block-->")
        toggle = toggle.split("<!--toggle-->")[1]
        if not descriptions_option:
            before, rest = block.split("<!--sid-->")
            block = before + rest.split("<!--/sid-->")[1]

        def body(query: dict[str, list[str]]) -> str:
            results = ""
            if "Q" in query or "q" in query:
                text = (query.get("Q") or query.get("q"))[0]
                number = int(query.get("pagenumber", ["1"])[0])
                if not pages:
                    results = no_results_html()
                else:
                    href = lambda n: f"/search?q={quote_plus(text)}&amp;pagenumber={n}"  # noqa: E731
                    results = (
                        f'<div class="search-results">{grid_html(pages[number - 1])}'
                        f"{pager_html(number, len(pages), href)}</div>"
                    )
            else:
                text = ""
            return render(
                fixture("search_form.html"),
                query=text,
                results=results,
                advanced_toggle=toggle if price_filter else "",
                advanced_block=block if price_filter else "",
            )

        self.html("/search", body)

    def product(self, product: Product) -> str:
        """Serve a product page and its add-to-cart endpoint; returns the product URL."""
        known = self._products_by_id.get(product.product_id)
        assert known is None or known.slug == product.slug, f"product id {product.product_id} used twice"
        self._products_by_id[product.product_id] = product
        self._products_by_slug[product.slug] = product

        def body(_query: dict[str, list[str]]) -> str:
            stock = ""
            if product.stock is not None:
                stock = (
                    '<div class="stock"><span class="label">Availability: </span>'
                    f'<span class="value">{product.stock}</span></div>'
                )
            panel = purchase_html(product)
            attributes = ""
            if product.attributes:
                attributes = render(
                    fixture(product.attributes),
                    id=product.product_id,
                    required='<span class="required">*</span>' if product.file_required else "",
                )
            giftcard = ""
            if product.giftcard:
                giftcard = render(
                    fixture(f"giftcard_{product.giftcard}.html"),
                    id=product.product_id,
                    sender_name=product.sender[0],
                    sender_email=product.sender[1],
                )
            return render(
                fixture("product.html"),
                slug=product.slug,
                id=product.product_id,
                title=product.title,
                price=product.price,
                stock=stock,
                add_to_cart=panel,
                attributes=attributes,
                giftcard=giftcard,
            )

        self.html(f"/{product.slug}", body)
        self._handlers[f"/addproducttocart/details/{product.product_id}/1"] = self._add_to_cart
        return f"{BASE}/{product.slug}"

    def cart(self, rows: list[dict[str, object]], sub_total: str, total: str | None = None) -> None:
        if not rows:
            self.html("/cart", fixture("cart_empty.html"))
            return
        self.html("/cart", self._cart_html(rows, sub_total, total or sub_total))

    def live_cart(self) -> None:
        """/cart shows what was accepted by the add-to-cart endpoint (one row per add, quantity 1)."""

        def body(_query: dict[str, list[str]]) -> str:
            if not self.added:
                return fixture("cart_empty.html")
            products = [self._products_by_slug[slug] for slug, _form in self.added]
            rows = [
                {"slug": item.slug, "title": item.title, "unit_price": item.price, "line_total": item.price}
                for item in products
            ]
            total = f"{sum(Decimal(item.price) for item in products):,.2f}"
            return self._cart_html(rows, total, total)

        self.html("/cart", body)

    @staticmethod
    def _cart_html(rows: list[dict[str, object]], sub_total: str, total: str) -> str:
        defaults = {"attributes": "", "quantity": 1}
        html_rows = "\n".join(
            render(fixture("cart_row.html"), row_id=7000 + index, **{**defaults, **row})
            for index, row in enumerate(rows)
        )
        return render(fixture("cart.html"), rows=html_rows, sub_total=sub_total, total=total)

    def accounts_pages(self) -> None:
        """/register, /login and /logout with a single session (the shop's auth cookie)."""
        parts = fixture("auth.html")
        register = parts.split("<!--register-->")[1].split("<!--result-->")[0]
        result = parts.split("<!--result-->")[1].split("<!--login-->")[0]
        login = parts.split("<!--login-->")[1]
        home = '<div class="page home-page"><div class="page-body">Welcome to our store</div></div>'

        def register_handler(request: Request, _query: dict[str, list[str]]) -> Response:
            if request.method != "POST":
                return Response(self.page_html(register))
            form = parse_qs(request.post_data or "")
            email, password = form["Email"][0], form["Password"][0]
            assert form["ConfirmPassword"][0] == password and form["Gender"] == ["M"], form
            self.accounts[email] = password
            self.logged_in = email
            return Response(self.page_html(result))

        def login_handler(request: Request, _query: dict[str, list[str]]) -> Response:
            if request.method != "POST":
                return Response(self.page_html(login))
            form = parse_qs(request.post_data or "")
            email, password = form["Email"][0], form["Password"][0]
            if self.accounts.get(email) != password:
                return Response(
                    self.page_html('<div class="validation-summary-errors">Login was unsuccessful.</div>' + login)
                )
            self.logged_in = email
            return Response(self.page_html(home))

        def logout_handler(_request: Request, _query: dict[str, list[str]]) -> Response:
            self.logged_in = None
            return Response(self.page_html(home))

        self._handlers["/register"] = register_handler
        self._handlers["/login"] = login_handler
        self._handlers["/logout"] = logout_handler
        self.html("/", home)

    # --------------------------------------------------------- routing

    def _add_to_cart(self, request: Request, _query: dict[str, list[str]]) -> Response:
        product_id = int(urlsplit(request.url).path.split("/")[-2])
        product = self._products_by_id[product_id]
        form = parse_qs(request.post_data or "", keep_blank_values=True)
        errors = list(product.forced_errors or [])
        errors += [
            message
            for name, message in product.required.items()
            if not any(value not in ("", "0") for value in form.get(name, []))
        ]
        upload = form.get(f"product_attribute_{product_id}_1_1", [])
        if product.attributes == "attributes_file.html" and product.file_required and not any(upload):
            errors.append("Please upload Upload your design")
        if product.giftcard:
            for suffix, message in GIFT_CARD_FIELDS[product.giftcard].items():
                value = form.get(f"giftcard_{product_id}.{suffix}", [""])[0].strip()
                if not value or (suffix.endswith("Email") and "@" not in value):
                    errors.append(message)
        if errors:
            answer = {"success": False, "message": errors[0] if len(errors) == 1 else errors}
        else:
            self.cart_count += 1
            self.added.append((product.slug, form))
            answer = {"success": True, "message": SUCCESS_MESSAGE, "updatetopcartsectionhtml": f"({self.cart_count})"}
        return Response(json.dumps(answer), content_type="application/json")

    def _handle(self, route: Route, request: Request) -> None:
        url = urlsplit(request.url)
        if f"{url.scheme}://{url.netloc}" != BASE:
            self.blocked.append(request.url)
            route.abort()
            return
        self.requests.append(f"{request.method} {url.path}{'?' + url.query if url.query else ''}")
        handler = self._handlers.get(url.path)
        if handler is None:
            route.fulfill(status=404, content_type="text/plain", body="not found")
            return
        response = handler(request, parse_qs(url.query, keep_blank_values=True))
        route.fulfill(status=response.status, content_type=response.content_type, body=response.body)

    def page_requests(self, path: str) -> list[str]:
        """GET requests for `path` (any query), in order."""
        return [entry for entry in self.requests if entry.startswith(f"GET {path}?") or entry == f"GET {path}"]

    def posts(self, path_prefix: str) -> list[str]:
        return [entry for entry in self.requests if entry.startswith(f"POST {path_prefix}")]
