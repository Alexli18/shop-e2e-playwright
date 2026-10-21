"""Product attributes: reproducible random choice in selects and radio groups, generated text for
required text inputs (custom text, gift card recipient / sender), detection of unsupported controls."""

from dataclasses import dataclass
import random

from playwright.sync_api import Locator, expect

from shop.models import TextFieldData


@dataclass(frozen=True)
class _Choice:
    """One selectable value: a select option (value) or a radio button (id), with the label it shows."""

    key: str
    label: str
    group: str = ""  # radio group name


def _text(locator: Locator) -> str:
    return " ".join((locator.text_content() or "").split())


class ProductOptions:
    # The attribute caption is the <dt> right before the <dd> holding the control.
    _CAPTION = "xpath=ancestor::dd[1]/preceding-sibling::dt[1]"

    # Controls the chooser cannot fill with generated data.
    _UNSUPPORTED = "input[type='file']"
    # A required attribute has <span class="required">*</span> in its caption.
    _REQUIRED_CAPTION = "xpath=ancestor::dd[1]/preceding-sibling::dt[1][.//span[contains(@class, 'required')]]"

    def __init__(self, scope: Locator) -> None:
        self._scope = scope
        self._root = scope.locator(".attributes")
        # Attribute text boxes / text areas, and the gift card's required inputs (its message is optional).
        self._text_fields = scope.locator(
            ".attributes input[type='text'], .attributes textarea, .giftcard input[type='text']"
        )

    def choose_randomly(self, rng: random.Random) -> dict[str, str]:
        """Pick a random available value in every select and radio group; return {attribute: label}."""
        chosen: dict[str, str] = {}
        for select in self._selects():
            options = self._options(select)
            if options:
                option = rng.choice(options)
                select.select_option(value=option.key)
                expect(select).to_have_value(option.key)
                chosen[self._caption(select)] = option.label
        for group in self._radio_groups():
            radio = rng.choice(group)
            control = self._root.locator(f"[id='{radio.key}']")
            self._root.locator(f"label[for='{radio.key}']").click()
            expect(control).to_be_checked()
            chosen[self._caption(control)] = radio.label
        return chosen

    def checked_extras(self) -> dict[str, str]:
        """Checkboxes that are ticked (they keep the shop's defaults): {attribute: 'label, label'}.

        They are not chosen randomly, but their surcharges are in the cart, so the run log records them."""
        extras: dict[str, list[str]] = {}
        for box in self._root.locator("input[type='checkbox']:checked").all():
            label = self._root.locator(f"label[for='{box.get_attribute('id')}']")
            extras.setdefault(self._caption(box), []).append(_text(label) if label.count() else "")
        return {caption: ", ".join(labels) for caption, labels in extras.items()}

    def fill_text_fields(self, data: TextFieldData) -> dict[str, str]:
        """Fill every empty text field: e-mail fields get `data.email`, name fields `data.name`, others `data.text`."""
        filled: dict[str, str] = {}
        for control in self._text_fields.all():
            if not control.is_editable() or control.input_value():
                continue  # disabled, read-only, or already filled (e.g. the gift card sender of a customer)
            label = self._scope.locator(f"label[for='{control.get_attribute('id')}']")
            caption = (_text(label) if label.count() else "").rstrip(":") or self._caption(control)
            lowered = caption.lower()
            value = data.email if "email" in lowered else data.name if "name" in lowered else data.text
            control.fill(value)
            filled[caption] = value
        return filled

    def unsupported_fields(self) -> list[str]:
        """Captions of REQUIRED controls that cannot be filled automatically (e.g. a mandatory file upload).

        Optional ones are left empty and do not block adding the product."""
        controls = self._root.locator(self._UNSUPPORTED)
        required = [
            controls.nth(index)
            for index in range(controls.count())
            if controls.nth(index).locator(self._REQUIRED_CAPTION).count()
        ]
        return [self._caption(control) for control in required]

    def _selects(self) -> list[Locator]:
        selects = self._root.locator("select")
        return [selects.nth(index) for index in range(selects.count())]

    @staticmethod
    def _options(select: Locator) -> list[_Choice]:
        """Enabled options with a real value: placeholders ('--- Please select ---', value '' or '0') are skipped."""
        choices = []
        for option in select.locator("option:not([disabled])").all():
            value = option.get_attribute("value") or ""
            if value not in ("", "0"):
                choices.append(_Choice(value, _text(option)))
        return choices

    def _radio_groups(self) -> list[list[_Choice]]:
        """Enabled radios by group. The label is its text; a colour swatch has none, so its title is used."""
        groups: dict[str, list[_Choice]] = {}
        for radio in self._root.locator("input[type='radio']:not([disabled])").all():
            radio_id = radio.get_attribute("id") or ""
            label = self._root.locator(f"label[for='{radio_id}']")
            swatch = label.locator("[title]")
            text = (_text(label) if label.count() else "") or (
                swatch.first.get_attribute("title") or "" if swatch.count() else ""
            )
            name = radio.get_attribute("name") or ""
            groups.setdefault(name, []).append(_Choice(radio_id, text or radio.get_attribute("value") or "", name))
        return list(groups.values())

    def _caption(self, control: Locator) -> str:
        return control.locator(self._CAPTION).inner_text().replace("*", "").strip().rstrip(":").strip()
