"""Small, testable arithmetic for the isolated free-shipping checkout QA."""
from __future__ import annotations


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
