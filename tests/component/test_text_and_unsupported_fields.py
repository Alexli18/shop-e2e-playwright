"""ProductOptions.fill_text_fields / unsupported_fields and how the workflow uses them (gift cards,
custom text attributes, file uploads)."""

from playwright.sync_api import Page
import pytest

from tests.component.catalog import (
    CUSTOM_TSHIRT,
    GIFT_CARD,
    GIFT_CARD_SENDER_FILLED,
    LAPTOP,
    PHYSICAL_GIFT_CARD,
    UPLOAD_OPTIONAL,
    UPLOAD_REQUIRED,
)
from tests.component.fakeshop import BASE, Card, FakeShop
from shop.artifacts import RunArtifacts
from shop.models import AddStatus, TextFieldData
from shop.pages import ProductPage
from shop.workflow import ShoppingWorkflow

pytestmark = pytest.mark.component

DATA = TextFieldData(name="QA Tester", email="qa_fixed@example.com")


def open_product(page: Page, url: str) -> ProductPage:
    return ProductPage(page, BASE).open_url(url)


def value(page: Page, element_id: str) -> str:
    return page.locator(f"[id='{element_id}']").input_value()


def add_items(page: Page, shop: FakeShop, artifacts: RunArtifacts, *products) -> list:
    shop.search([[Card("Anything", "1.00")]])
    page.goto(f"{BASE}/search?q=anything")
    return ShoppingWorkflow(page, BASE, artifacts, seed=3).add_items_to_cart([shop.product(p) for p in products])


# ------------------------------------------------------------- fill_text_fields


def test_virtual_gift_card_fields_get_names_and_emails(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(GIFT_CARD))

    filled = product.options.fill_text_fields(DATA)

    assert filled == {
        "Recipient's Name": "QA Tester",
        "Recipient's Email": "qa_fixed@example.com",
        "Your Name": "QA Tester",
        "Your Email": "qa_fixed@example.com",
    }
    assert value(page, "giftcard_2_RecipientName") == "QA Tester"
    assert value(page, "giftcard_2_SenderEmail") == "qa_fixed@example.com"
    assert value(page, "giftcard_2_Message") == ""  # the optional message stays empty
    assert product.add_to_cart().success


def test_prefilled_sender_fields_are_left_alone(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(GIFT_CARD_SENDER_FILLED))

    filled = product.options.fill_text_fields(DATA)

    assert filled == {"Recipient's Name": "QA Tester", "Recipient's Email": "qa_fixed@example.com"}
    assert value(page, "giftcard_3_SenderName") == "Jane Customer"
    assert value(page, "giftcard_3_SenderEmail") == "jane@example.com"
    assert product.add_to_cart().success
    _slug, form = shop.added[-1]
    assert form["giftcard_3.SenderName"] == ["Jane Customer"]


def test_physical_gift_card_has_names_only(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(PHYSICAL_GIFT_CARD))
    assert product.options.fill_text_fields(DATA) == {"Recipient's Name": "QA Tester", "Your Name": "QA Tester"}
    assert product.add_to_cart().success


def test_custom_text_attributes_get_the_default_text(page: Page, shop: FakeShop) -> None:
    product = open_product(page, shop.product(CUSTOM_TSHIRT))

    filled = product.options.fill_text_fields(DATA)

    # Caption from the <dt> (no label[for]); the textarea too; filled / disabled / read-only boxes untouched.
    assert filled == {"Enter your text": "QA automation test", "Gift message": "QA automation test"}
    assert value(page, "product_attribute_24_2_9") == "QA automation test"
    assert value(page, "product_attribute_24_4_11") == "ABC"
    assert value(page, "product_attribute_24_5_12") == ""
    assert value(page, "product_attribute_24_6_13") == ""
    assert product.add_to_cart().success


def test_product_without_text_fields(page: Page, shop: FakeShop) -> None:
    assert open_product(page, shop.product(LAPTOP)).options.fill_text_fields(DATA) == {}


def test_unfilled_gift_card_is_refused_with_one_message_per_field(page: Page, shop: FakeShop) -> None:
    notice = open_product(page, shop.product(GIFT_CARD)).add_to_cart()
    assert notice.success is False
    assert notice.text == (
        "Enter valid recipient name Enter valid recipient email Enter valid sender name Enter valid sender email"
    )


# ------------------------------------------------------------- workflow: text fields


def test_workflow_adds_gift_cards_and_logs_text_fields(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    items = add_items(page, shop, artifacts, GIFT_CARD, GIFT_CARD_SENDER_FILLED, CUSTOM_TSHIRT)

    assert [item.status for item in items] == [AddStatus.ADDED] * 3, [item.message for item in items]
    gift = items[0].text_fields
    assert set(gift) == {"Recipient's Name", "Recipient's Email", "Your Name", "Your Email"}
    assert gift["Recipient's Name"] == gift["Your Name"] == "QA Tester"
    email = gift["Recipient's Email"]
    assert email == gift["Your Email"] and email.startswith("qa_") and email.endswith("@example.com")
    assert set(items[1].text_fields) == {"Recipient's Name", "Recipient's Email"}
    assert items[2].text_fields["Enter your text"] == "QA automation test"
    logged = [event["item"] for event in artifacts.events if event["event"] == "add_to_cart"]
    assert [item.text_fields for item in logged] == [item.text_fields for item in items]
    assert shop.cart_count == 3


def test_generated_email_is_unique_per_workflow(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    first = add_items(page, shop, artifacts, GIFT_CARD)[0].text_fields["Your Email"]
    second = add_items(page, shop, artifacts, GIFT_CARD)[0].text_fields["Your Email"]
    assert first != second


# ------------------------------------------------------------- unsupported controls


def test_file_upload_is_unsupported_and_not_clicked(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    items = add_items(page, shop, artifacts, UPLOAD_REQUIRED, LAPTOP)

    assert [item.status for item in items] == [AddStatus.UNSUPPORTED, AddStatus.ADDED]
    assert items[0].message == "Cannot fill Upload your design"
    assert items[0].options == {} and items[0].text_fields == {}
    assert shop.posts("/addproducttocart/details/70/") == []  # Add to cart was never clicked
    logged = [event for event in artifacts.events if event["event"] == "add_to_cart"]
    assert logged[0]["item"].status is AddStatus.UNSUPPORTED
    assert logged[0]["screenshot"].endswith(".png")


def test_unsupported_fields_lists_upload_captions(page: Page, shop: FakeShop) -> None:
    assert open_product(page, shop.product(UPLOAD_REQUIRED)).options.unsupported_fields() == ["Upload your design"]
    assert open_product(page, shop.product(LAPTOP)).options.unsupported_fields() == []


def test_optional_file_upload_does_not_block_adding(page: Page, shop: FakeShop, artifacts: RunArtifacts) -> None:
    items = add_items(page, shop, artifacts, UPLOAD_OPTIONAL)
    assert items[0].status is AddStatus.ADDED, items[0].message
