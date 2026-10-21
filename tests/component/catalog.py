"""Product fixtures shared by the offline product / options / workflow tests."""

from tests.component.fakeshop import Product

LAPTOP = Product("141-inch-laptop", 31, "14.1-inch Laptop", price="1590.00")
BYOC = Product(
    "build-your-own-computer",
    16,
    "Build your own computer",
    price="1200.00",
    attributes="attributes_byoc.html",
    required={"product_attribute_16_3_6": "Please select HDD"},
)
EDGE = Product(
    "engraved-ring",
    50,
    "Engraved ring",
    price="25.00",
    attributes="attributes_edge.html",
    required={
        "product_attribute_50_1_1": "Please select Size",
        "product_attribute_50_3_3": "Please select Gift wrap",
        "product_attribute_50_4_4": "Please select Color",
    },
)
NOT_SOLD = Product("used-camera", 60, "Used camera", purchase="none")  # like the live 'Used phone'
WISHLIST_ONLY = Product("fiction-ex", 64, "Fiction EX", purchase="wishlist")  # like the live 'Fiction EX'
RENAMED_BUTTON = Product("renamed-button-camera", 65, "Camera", purchase="renamed")
NO_PURCHASE_BLOCK = Product("no-block-camera", 66, "Camera", purchase="missing")
OUT_OF_STOCK = Product("sold-out-phone", 61, "Sold out phone", stock="Out of stock")
SOLD_OUT_ON_CLICK = Product("last-one-phone", 62, "Last one phone", forced_errors=["Out of stock"])
NEEDS_HIDDEN_OPTION = Product(
    "mystery-box", 63, "Mystery box", required={"product_attribute_63_1_1": "Please select Color"}
)
GIFT_CARD = Product("25-virtual-gift-card", 2, "$25 Virtual Gift Card", price="25.00", stock=None, giftcard="virtual")
GIFT_CARD_SENDER_FILLED = Product(
    "5-virtual-gift-card",
    3,
    "$5 Virtual Gift Card",
    price="5.00",
    stock=None,
    giftcard="virtual",
    sender=("Jane Customer", "jane@example.com"),
)
PHYSICAL_GIFT_CARD = Product(
    "100-physical-gift-card", 4, "$100 Physical Gift Card", price="100.00", stock=None, giftcard="physical"
)
CUSTOM_TSHIRT = Product(
    "custom-t-shirt",
    24,
    "Custom T-Shirt",
    price="15.00",
    attributes="attributes_text.html",
    required={"product_attribute_24_2_9": "Please enter Enter your text"},
)
UPLOAD_REQUIRED = Product("custom-poster", 70, "Custom poster", price="20.00", attributes="attributes_file.html")
UPLOAD_OPTIONAL = Product(
    "framed-print", 71, "Framed print", price="30.00", attributes="attributes_file.html", file_required=False
)
CHECKBOXES_REQUIRED = Product(
    "office-bundle",
    80,
    "Office bundle",
    price="40.00",
    attributes="attributes_checkboxes.html",
    required={
        "product_attribute_80_1_1": "Please select Software",
        "product_attribute_80_2_2": "Please select Accessories",
    },
)

BYOC_LABELS = {
    "Processor": {"2.2 GHz Intel Pentium Dual-Core E2200", "2.5 GHz Intel Pentium Dual-Core E2200 [+15.00]"},
    "RAM": {"2 GB", "4GB [+20.00]", "8GB [+60.00]"},
    "HDD": {"320 GB", "400 GB [+100.00]"},
    "OS": {"Ubuntu", "Windows 7 [+50.00]", "Windows 10 [+60.00]"},
}
