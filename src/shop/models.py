"""Plain data objects and the data-driven shopping cases."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
from pathlib import Path


@dataclass(frozen=True)
class ProductSummary:
    title: str
    url: str
    price: Decimal


@dataclass(frozen=True)
class TextFieldData:
    """Generated values for free-text fields (never real personal data)."""

    name: str
    email: str
    text: str = "QA automation test"


@dataclass(frozen=True)
class CartEntry:
    title: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    attributes: dict[str, str] = field(default_factory=dict)  # the chosen options the cart lists under the name


@dataclass(frozen=True)
class CartSnapshot:
    entries: list[CartEntry]
    sub_total: Decimal

    @property
    def quantity(self) -> int:
        return sum(entry.quantity for entry in self.entries)


class AddStatus(StrEnum):
    ADDED = "added"
    UNAVAILABLE = "unavailable"  # out of stock, not sold online, or wishlist only (the shop's own signs)
    UNSUPPORTED = "unsupported"  # the form has a required control that cannot be filled (e.g. file upload)
    REJECTED = "rejected"  # the shop answered with an error notification


@dataclass(frozen=True)
class AddedItem:
    url: str
    title: str
    status: AddStatus
    options: dict[str, str] = field(default_factory=dict)
    message: str = ""
    text_fields: dict[str, str] = field(default_factory=dict)  # generated values typed into text inputs
    quantity: int = 1  # units put in the cart (1 unless the case sets max_quantity)
    page_price: Decimal | None = None  # the price shown on the product page, before option surcharges


@dataclass(frozen=True)
class SearchOutcome:
    """What the search collected and which result pages it read (1-based, in visit order)."""

    products: list[ProductSummary]
    pages: list[int]


@dataclass(frozen=True)
class RunResult:
    urls: list[str]
    items: list[AddedItem]
    cart: CartSnapshot
    search: SearchOutcome = field(default_factory=lambda: SearchOutcome([], []))

    def with_status(self, status: AddStatus) -> list[AddedItem]:
        return [item for item in self.items if item.status is status]


@dataclass(frozen=True)
class ShoppingCase:
    """One data-driven scenario; the fields after `seed` are optional expectations and search options."""

    name: str
    query: str
    max_price: Decimal
    limit: int
    seed: int
    search_in_descriptions: bool = False
    expect_empty: bool = False  # the search must find nothing
    min_results: int = 0  # the search must find at least this many products
    min_search_pages: int = 1  # the search must read at least this many result pages
    smoke: bool = False  # also part of the fast `smoke` suite
    max_quantity: int = 1  # > 1: a random quantity 1..max_quantity per item (seeded); the budget counts units

    def __post_init__(self) -> None:
        for name in ("name", "query"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"Invalid shopping case: {name} must be a string")
        if not self.name.strip() or not self.query.strip():
            raise ValueError("Case name and query must not be empty")
        if not self.max_price.is_finite() or self.max_price < 0:
            raise ValueError("max_price must be a finite non-negative amount")
        for name in ("limit", "seed", "min_results", "min_search_pages", "max_quantity"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if self.limit < 0 or self.min_results < 0 or self.min_search_pages < 1:
            raise ValueError("limit and min_results must be >= 0, min_search_pages >= 1")
        if self.max_quantity < 1:
            raise ValueError("max_quantity must be >= 1")
        for name in ("search_in_descriptions", "expect_empty", "smoke"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be true or false")
        if self.expect_empty and (self.min_results or self.min_search_pages > 1):
            raise ValueError("expect_empty contradicts min_results / min_search_pages")
        if self.min_results > self.limit:
            raise ValueError("min_results cannot exceed limit")
        if self.limit == 0 and (self.min_search_pages > 1 or self.expect_empty):
            # limit 0 never searches, so these expectations could never be verified
            raise ValueError("limit 0 does not search: min_search_pages / expect_empty cannot be checked")


_REQUIRED = ("name", "query", "max_price", "limit", "seed")
_OPTIONAL = ("search_in_descriptions", "expect_empty", "min_results", "min_search_pages", "smoke", "max_quantity")


def _case(row: object) -> ShoppingCase:
    if not isinstance(row, dict):
        raise ValueError(f"Invalid shopping case: expected a JSON object, got {type(row).__name__}")
    if unknown := set(row) - set(_REQUIRED) - set(_OPTIONAL):
        raise ValueError(f"Invalid shopping case: unknown key(s) {sorted(unknown)}")
    label = f"Invalid shopping case {row.get('name')!r}"
    try:
        price = row["max_price"]
        if isinstance(price, bool) or not isinstance(price, (str, int, float)):
            raise ValueError(f"{label}: max_price must be a number or a string, got {price!r}")
        try:
            amount = Decimal(str(price).strip())
        except InvalidOperation:
            raise ValueError(f"{label}: max_price {price!r} is not a number") from None
        values = {key: row[key] for key in _REQUIRED} | {key: row[key] for key in _OPTIONAL if key in row}
        return ShoppingCase(**{**values, "max_price": amount})
    except KeyError as error:
        raise ValueError(f"{label}: missing key {error}") from None


def load_cases(path: Path) -> list[ShoppingCase]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Shopping cases must be a non-empty JSON array")
    cases = [_case(row) for row in rows]
    if len({case.name for case in cases}) != len(cases):
        raise ValueError("Shopping case names must be unique")
    return cases
