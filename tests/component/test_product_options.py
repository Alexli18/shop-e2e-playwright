"""ProductOptions.choose_randomly against the live BYOC attribute markup and nopCommerce edge cases."""

import random

from playwright.sync_api import Page
import pytest

from tests.component.catalog import BYOC, BYOC_LABELS, EDGE, LAPTOP
from tests.component.fakeshop import FakeShop
from shop.pages import ProductPage

pytestmark = pytest.mark.component


def choose(page: Page, url: str, seed: int) -> dict[str, str]:
    product = ProductPage(page, "unused").open_url(url)
    return product.options.choose_randomly(random.Random(seed))


def checked_label(page: Page, group: str) -> list[str]:
    return page.locator(f"input[type='radio'][name='{group}']:checked").evaluate_all(
        "radios => radios.map(r => document.querySelector(`label[for='${r.id}']`).textContent.trim()"
        ".replace(/\\s+/g, ' '))"
    )


def selected_text(page: Page, select_id: str) -> str:
    return page.locator(f"#{select_id}").evaluate(
        "s => s.options[s.selectedIndex].textContent.trim().replace(/\\s+/g, ' ')"
    )


def test_one_value_per_select_and_radio_group_with_labels(page: Page, shop: FakeShop) -> None:
    chosen = choose(page, shop.product(BYOC), seed=17)

    assert set(chosen) == set(BYOC_LABELS)  # captions without the '*' marker; checkboxes not touched
    for caption, label in chosen.items():
        assert label in BYOC_LABELS[caption]
    # The returned labels are what the page now shows as selected.
    assert selected_text(page, "product_attribute_16_5_4") == chosen["Processor"]
    assert selected_text(page, "product_attribute_16_6_5") == chosen["RAM"]
    assert checked_label(page, "product_attribute_16_3_6") == [chosen["HDD"]]
    assert checked_label(page, "product_attribute_16_4_7") == [chosen["OS"]]
    assert page.locator("#product_attribute_16_8_8_22").is_checked()  # pre-checked checkbox left alone


def test_ticked_checkboxes_are_reported_with_their_surcharge(page: Page, shop: FakeShop) -> None:
    product = ProductPage(page, "unused").open_url(shop.product(BYOC))
    assert product.options.checked_extras() == {"Software": "Microsoft Office [+50.00]"}
    assert ProductPage(page, "unused").open_url(shop.product(LAPTOP)).options.checked_extras() == {}


def test_same_seed_gives_same_choice(page: Page, shop: FakeShop) -> None:
    url = shop.product(BYOC)
    assert choose(page, url, seed=42) == choose(page, url, seed=42)


def test_different_seeds_explore_different_variants(page: Page, shop: FakeShop) -> None:
    url = shop.product(BYOC)
    outcomes = {tuple(sorted(choose(page, url, seed).items())) for seed in range(8)}
    assert len(outcomes) >= 3


@pytest.mark.parametrize("seed", range(6))
def test_placeholders_and_disabled_values_are_never_chosen(page: Page, shop: FakeShop, seed: int) -> None:
    chosen = choose(page, shop.product(EDGE), seed)

    assert chosen["Size"] == "M"  # not '--- Please select ---', not 'Choose one', not the disabled 'XS'
    assert "Engraving font" not in chosen  # only a placeholder: nothing to choose, skipped
    assert chosen["Gift wrap"] == "Plain paper"  # the disabled radio is never picked
    assert chosen["Color"] in {"Red", "Blue"}  # colour squares: label text is empty, swatch title is used
    assert page.locator("input[name='product_attribute_50_4_4']:checked").count() == 1


def test_options_chosen_are_posted_and_accepted(page: Page, shop: FakeShop) -> None:
    product = ProductPage(page, "unused").open_url(shop.product(EDGE))
    product.options.choose_randomly(random.Random(3))
    notice = product.add_to_cart()
    assert notice.success, notice.text
    _slug, form = shop.added[-1]
    assert form["product_attribute_50_1_1"] == ["102"]
    assert form["product_attribute_50_3_3"] == ["32"]


def test_product_without_attributes_returns_empty(page: Page, shop: FakeShop) -> None:
    assert choose(page, shop.product(LAPTOP), seed=1) == {}
