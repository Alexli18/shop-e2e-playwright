"""Shopping cart rows: product, unit price, quantity, line total."""

from playwright.sync_api import Locator, Page

from shop import markup
from shop.models import CartEntry
from shop.prices import parse_price


class CartTable:
    def __init__(self, page: Page) -> None:
        self._rows = page.locator(f"table.cart tr.{markup.CART_ROW}")

    def count(self) -> int:
        return self._rows.count()

    def entries(self) -> list[CartEntry]:
        return [self._entry(self._rows.nth(index)) for index in range(self.count())]

    def remove_checkboxes(self) -> Locator:
        return self._rows.get_by_role("checkbox")

    @staticmethod
    def _entry(row: Locator) -> CartEntry:
        return CartEntry(
            title=row.locator(f"td.product a.{markup.CART_PRODUCT_NAME}").inner_text().strip(),
            quantity=int(row.locator(f"td.qty input.{markup.CART_QUANTITY}").input_value()),
            unit_price=parse_price(row.locator(f"td.unit-price .{markup.CART_UNIT_PRICE}").inner_text()),
            line_total=parse_price(row.locator(f"td.subtotal .{markup.CART_LINE_TOTAL}").inner_text()),
            attributes=CartTable._attributes(row),
        )

    @staticmethod
    def _attributes(row: Locator) -> dict[str, str]:
        """The 'Caption: label' lines under the product name ('RAM: 8GB [+60.00]'). A caption listed several times
        (several ticked checkboxes) is joined with ', ', as ProductOptions.checked_extras reports it."""
        block = row.locator("td.product .attributes")
        lines: dict[str, list[str]] = {}
        for line in (block.inner_text() if block.count() else "").splitlines():
            caption, separator, label = line.partition(":")
            if separator:
                lines.setdefault(caption.strip(), []).append(" ".join(label.split()))
        return {caption: ", ".join(labels) for caption, labels in lines.items()}
