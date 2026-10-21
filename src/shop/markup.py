"""Class names of the shop's markup that several page objects and components rely on.
One place to update when the theme changes; locators used by a single component stay in that component."""

# header
HEADER_LINKS = "header-links"
ACCOUNT_LINK = "account"
CART_COUNTER = "cart-qty"
# listings (search results, categories)
SEARCH_RESULTS = "search-results"
RESULT_MESSAGES = ("result", "warning")  # 'No products were found...' / 'Search term minimum length is 3...'
PRODUCT_ITEM = "product-item"
PRODUCT_TITLE = "product-title"
ACTUAL_PRICE = "actual-price"
CURRENT_PAGE = "current-page"
# cart
CART_ROW = "cart-item-row"
CART_PRODUCT_NAME = "product-name"
CART_QUANTITY = "qty-input"
CART_UNIT_PRICE = "product-unit-price"
CART_LINE_TOTAL = "product-subtotal"
CART_TOTALS = "cart-total"
