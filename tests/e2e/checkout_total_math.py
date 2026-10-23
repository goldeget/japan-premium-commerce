"""Small, testable arithmetic for the isolated free-shipping checkout QA."""
from __future__ import annotations

import math


def _label_has_any(label: str, markers: tuple[str, ...]) -> bool:
    normalized = " ".join(label.casefold().split())
    return any(marker in normalized for marker in markers)


def is_tax_inclusive_total_label(label: str) -> bool:
    return _label_has_any(label, ("tax incl", "tax included", "税込", "세금 포함", "含税", "含稅"))


def is_tax_exclusive_total_label(label: str) -> bool:
    return _label_has_any(
        label,
        (
            "tax excl",
            "tax excluded",
            "excluding tax",
            "税抜",
            "税別",
            "세금 제외",
            "세금 별도",
            "不含税",
            "不含稅",
        ),
    )


def labeled_tax_total_amounts(total_rows: list[tuple[str, int]]) -> dict[str, int | None]:
    """Read uniquely labeled gross/net totals without relying on row order."""
    inclusive_rows = [amount for label, amount in total_rows if is_tax_inclusive_total_label(label)]
    exclusive_rows = [amount for label, amount in total_rows if is_tax_exclusive_total_label(label)]
    if len(inclusive_rows) > 1 or len(exclusive_rows) > 1:
        raise AssertionError("checkout displayed duplicate labeled tax-inclusive or tax-exclusive totals")
    return {
        "total_tax_incl": inclusive_rows[0] if inclusive_rows else None,
        "total_tax_excl": exclusive_rows[0] if exclusive_rows else None,
    }


def reconcile_order_confirmation_total_rows(
    *,
    total_rows: list[tuple[str, int]],
    tax_amounts: list[int],
    allow_unassigned_tax_rule: bool = False,
    explicit_zero_rate_tax_rules_group_id: int | None = None,
) -> dict[str, int | None | bool | str]:
    """Read the final order amount and tax evidence from confirmation labels."""
    if not total_rows:
        raise AssertionError("order confirmation did not display a recognizable final total")
    labeled = labeled_tax_total_amounts(total_rows)
    total_incl = labeled["total_tax_incl"]
    total_excl = labeled["total_tax_excl"]

    if explicit_zero_rate_tax_rules_group_id is not None:
        if explicit_zero_rate_tax_rules_group_id < 1:
            raise AssertionError("an explicit zero-rate fixture must retain its positive tax-rule group ID")
        if any(amount != 0 for amount in tax_amounts):
            raise AssertionError("the explicitly configured zero-rate fixture displayed positive tax")
        if total_incl is not None and total_excl is not None and total_incl != total_excl:
            raise AssertionError("the explicit zero-rate fixture has different gross and net confirmation totals")
        if total_incl is None:
            total_incl = total_rows[-1][1]
        if total_excl is None:
            total_excl = total_incl
        tax = 0
        display_mode = "explicit_zero_rate_rule"
    elif allow_unassigned_tax_rule:
        if any(amount != 0 for amount in tax_amounts):
            raise AssertionError("confirmation displayed tax despite the fixture having no assigned tax rule")
        if total_incl is not None and total_excl is not None and total_incl != total_excl:
            raise AssertionError("confirmation gross/net totals conflict with the unassigned-tax fixture")
        if total_incl is None:
            total_incl = total_rows[-1][1]
        tax = None
        display_mode = "no_assigned_tax_rule"
    elif tax_amounts:
        tax = sum(tax_amounts)
        if total_incl is None:
            total_incl = total_rows[-1][1]
        if total_excl is not None and total_incl - total_excl != tax:
            raise AssertionError("order confirmation gross/net totals disagree with its displayed tax rows")
        if total_excl is None:
            total_excl = total_incl - tax
        display_mode = "detailed_breakdown"
    elif total_incl is not None and total_excl is not None:
        tax = total_incl - total_excl
        if tax <= 0:
            raise AssertionError("order confirmation gross/net totals must establish positive tax")
        display_mode = "tax_inclusive_and_exclusive_totals"
    elif total_incl is not None:
        tax = None
        display_mode = "inclusive_total_only"
    else:
        raise AssertionError(
            "order confirmation omitted both a tax amount and an explicit tax-inclusive total"
        )

    return {
        "tax": tax,
        "tax_breakdown_displayed": bool(tax_amounts),
        "tax_display_mode": display_mode,
        "total_tax_incl": total_incl,
        "total_tax_excl": total_excl,
    }


def reconcile_explicit_zero_rate_checkout(
    *,
    products_tax_incl: int,
    shipping_tax_incl: int,
    discounts_tax_incl: int,
    total_tax_incl: int,
    explicit_tax_rules_group_id: int,
    resolved_tax_rate_percent: float,
    tax_amounts: list[int],
    total_tax_excl: int | None = None,
) -> dict[str, int | None | bool | str]:
    """Reconcile a test-only explicit zero-rate rule without confusing it with unknown tax."""
    if explicit_tax_rules_group_id < 1:
        raise AssertionError("an explicit zero-rate fixture requires a positive tax-rule group ID")
    if not math.isfinite(resolved_tax_rate_percent) or abs(resolved_tax_rate_percent) > 0.000001:
        raise AssertionError("the explicit exemption fixture must resolve to its configured zero tax rate")
    if any(amount != 0 for amount in tax_amounts):
        raise AssertionError("the explicit zero-rate fixture displayed positive tax")
    amounts = (products_tax_incl, shipping_tax_incl, discounts_tax_incl, total_tax_incl)
    if any(amount < 0 for amount in amounts):
        raise AssertionError("checkout totals cannot contain negative amounts")
    if shipping_tax_incl != 0:
        raise AssertionError("the supported Japan carrier must keep shipping at ¥0")
    if total_tax_incl != products_tax_incl + shipping_tax_incl - discounts_tax_incl:
        raise AssertionError("checkout total has an unexplained amount (possible platform fee)")
    if total_tax_excl is not None and total_tax_excl != total_tax_incl:
        raise AssertionError("explicit zero-rate gross and net checkout totals must match")

    return {
        "products_tax_incl": products_tax_incl,
        "products_tax_excl": products_tax_incl,
        "shipping_tax_incl": shipping_tax_incl,
        "shipping_tax_excl": 0,
        "discounts_tax_incl": discounts_tax_incl,
        "discounts_tax_excl": discounts_tax_incl,
        "tax": 0,
        "total_tax_incl": total_tax_incl,
        "total_tax_excl": total_tax_incl,
        "tax_breakdown_displayed": bool(tax_amounts),
        "tax_display_mode": "explicit_zero_rate_rule",
        "tax_rules_group_id": explicit_tax_rules_group_id,
    }


def reconcile_cart_totals(
    *,
    products_tax_incl: int,
    shipping_tax_incl: int,
    discounts_tax_incl: int,
    tax: int,
    total_tax_incl: int,
    total_tax_excl: int,
    pre_discount_tax: int,
) -> dict[str, int]:
    """Derive net product and discount amounts from observed cart totals.

    The caller supplies the tax observed before applying a cart rule. This
    keeps the product subtotal's original tax separate from the post-discount
    tax displayed in the current cart.
    """
    amounts = (
        products_tax_incl,
        shipping_tax_incl,
        discounts_tax_incl,
        tax,
        total_tax_incl,
        total_tax_excl,
        pre_discount_tax,
    )
    if any(amount < 0 for amount in amounts):
        raise AssertionError("checkout totals cannot contain negative amounts")
    if shipping_tax_incl != 0:
        raise AssertionError("the supported Japan carrier must keep shipping at ¥0")
    if total_tax_incl - total_tax_excl != tax:
        raise AssertionError("checkout tax does not reconcile to the tax-inclusive total")
    if total_tax_incl != products_tax_incl + shipping_tax_incl - discounts_tax_incl:
        raise AssertionError("checkout total has an unexplained amount (possible platform fee)")

    products_tax_excl = products_tax_incl - pre_discount_tax
    discounts_tax_excl = products_tax_excl - total_tax_excl
    if products_tax_excl < 0 or discounts_tax_excl < 0:
        raise AssertionError("tax-exclusive product or discount total is inconsistent")

    return {
        "products_tax_incl": products_tax_incl,
        "products_tax_excl": products_tax_excl,
        "shipping_tax_incl": shipping_tax_incl,
        "shipping_tax_excl": 0,
        "discounts_tax_incl": discounts_tax_incl,
        "discounts_tax_excl": discounts_tax_excl,
        "tax": tax,
        "total_tax_incl": total_tax_incl,
        "total_tax_excl": total_tax_excl,
    }


def reconcile_tax_included_display(
    *,
    products_tax_incl: int,
    shipping_tax_incl: int,
    discounts_tax_incl: int,
    total_tax_incl: int,
    total_label: str,
) -> dict[str, int | None | bool | str]:
    """Validate the customer-visible price when PrestaShop shows no tax row.

    An inclusive final total proves the customer's payable amount, but it does
    not expose a tax decomposition. Keep those amounts unknown here; the
    isolated native saved-order check verifies the configured tax rule and
    actual tax rows separately.
    """
    amounts = (
        products_tax_incl,
        shipping_tax_incl,
        discounts_tax_incl,
        total_tax_incl,
    )
    if any(amount < 0 for amount in amounts):
        raise AssertionError("checkout totals cannot contain negative amounts")
    if shipping_tax_incl != 0:
        raise AssertionError("the supported Japan carrier must keep shipping at ¥0")

    label = " ".join(total_label.casefold().split())
    inclusive_markers = (
        "tax incl",
        "tax included",
        "税込",
        "세금 포함",
        "含税",
        "含稅",
    )
    if not any(marker in label for marker in inclusive_markers):
        raise AssertionError(
            "a taxable checkout without a tax breakdown must label its final total as tax-inclusive"
        )
    if total_tax_incl != products_tax_incl + shipping_tax_incl - discounts_tax_incl:
        raise AssertionError("checkout total has an unexplained amount (possible platform fee)")

    return {
        "products_tax_incl": products_tax_incl,
        "products_tax_excl": None,
        "shipping_tax_incl": shipping_tax_incl,
        "shipping_tax_excl": None,
        "discounts_tax_incl": discounts_tax_incl,
        "discounts_tax_excl": None,
        "tax": None,
        "total_tax_incl": total_tax_incl,
        "total_tax_excl": None,
        "tax_breakdown_displayed": False,
        "tax_display_mode": "inclusive_total_only",
    }


def reconcile_no_assigned_tax_rule_display(
    *,
    products_tax_incl: int,
    shipping_tax_incl: int,
    discounts_tax_incl: int,
    total_tax_incl: int,
    tax_breakdown_displayed: bool = False,
) -> dict[str, int | None | bool | str]:
    """Reconcile an unclassified fixture without claiming a legal zero tax."""
    amounts = (products_tax_incl, shipping_tax_incl, discounts_tax_incl, total_tax_incl)
    if any(amount < 0 for amount in amounts):
        raise AssertionError("checkout totals cannot contain negative amounts")
    if shipping_tax_incl != 0:
        raise AssertionError("the supported Japan carrier must keep shipping at ¥0")
    if total_tax_incl != products_tax_incl + shipping_tax_incl - discounts_tax_incl:
        raise AssertionError("checkout total has an unexplained amount (possible platform fee)")

    return {
        "products_tax_incl": products_tax_incl,
        "products_tax_excl": None,
        "shipping_tax_incl": shipping_tax_incl,
        "shipping_tax_excl": None,
        "discounts_tax_incl": discounts_tax_incl,
        "discounts_tax_excl": None,
        "tax": None,
        "total_tax_incl": total_tax_incl,
        "total_tax_excl": None,
        "tax_breakdown_displayed": tax_breakdown_displayed,
        "tax_display_mode": "no_assigned_tax_rule",
    }


def reconcile_inclusive_and_exclusive_totals(
    *,
    products_tax_incl: int,
    shipping_tax_incl: int,
    discounts_tax_incl: int,
    total_tax_incl: int,
    total_tax_excl: int,
    pre_discount_tax: int,
) -> dict[str, int | None | bool | str]:
    """Reconcile labeled gross/net totals when no separate tax row is shown.

    The gross/net difference is an observed tax amount. Mark the tax row as
    undisplayed so artifacts preserve how that value was established.
    """
    tax = total_tax_incl - total_tax_excl
    if tax <= 0:
        raise AssertionError("separate taxable totals must establish a positive tax amount")
    totals = reconcile_cart_totals(
        products_tax_incl=products_tax_incl,
        shipping_tax_incl=shipping_tax_incl,
        discounts_tax_incl=discounts_tax_incl,
        tax=tax,
        total_tax_incl=total_tax_incl,
        total_tax_excl=total_tax_excl,
        pre_discount_tax=pre_discount_tax,
    )
    totals["tax_breakdown_displayed"] = False
    totals["tax_display_mode"] = "tax_inclusive_and_exclusive_totals"
    return totals
