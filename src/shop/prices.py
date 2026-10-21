"""Parsing of prices as displayed by the shop."""

from decimal import Decimal
import re

_AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
# Right after an amount: more digits or a separator + digit ('1.234,56', '12,5', '1,2345.00'), or a
# space-grouped thousand ('1 234,56').
_OTHER_FORMAT = re.compile(r"[.,]?\d| \d{3}(?![\d.])")


def parse_price(text: str) -> Decimal:
    """Return the first amount in the text, e.g. 'Sub-Total: 1,215.00' -> Decimal('1215.00').

    Only the shop's US format (',' for thousands, '.' for decimals) is read; other formats raise ValueError
    rather than give a silently wrong amount."""
    normalized = " ".join(text.split())
    match = _AMOUNT.search(normalized)
    if match is None:
        raise ValueError(f"No price found in {text!r}")
    if _OTHER_FORMAT.match(normalized, match.end()):
        raise ValueError(f"Unsupported price format in {text!r} (expected e.g. 1,234.56)")
    return Decimal(match.group().replace(",", ""))
