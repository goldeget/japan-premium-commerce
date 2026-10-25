"""Pure evidence checks for the isolated storefront product browser QA."""

from __future__ import annotations


def product_page_failure_reason(
    *,
    response_status: int | None,
    body_id: str,
    not_found_visible: bool,
    product_container_count: int,
    product_heading_count: int,
    product_heading_visible: bool,
    product_heading_text: str,
    product_form_count: int,
    product_id_value: str | None,
    expected_product_id: int,
    add_to_cart_visible: bool,
    add_to_cart_enabled: bool,
) -> str | None:
    """Return a bounded reason when the loaded document is not this product.

    The page title is deliberately not an input: CI run identifiers are used in
    synthetic product names and can contain any digit sequence, including 404.
    """
    if type(response_status) is int and not 200 <= response_status < 300:
        return "document_response_not_successful"
    if not_found_visible:
        return "not_found_page"
    if body_id != "product":
        return "not_product_document"
    if product_container_count != 1:
        return "product_container_invalid"
    if (
        product_heading_count != 1
        or not product_heading_visible
        or "[CI ONLY]" not in product_heading_text
    ):
        return "product_heading_invalid"
    if product_form_count != 1:
        return "product_form_invalid"
    if product_id_value != str(expected_product_id):
        return "product_identity_mismatch"
    if not add_to_cart_visible or not add_to_cart_enabled:
        return "add_to_cart_unavailable"
    return None


def mobile_product_breadcrumb_failure_reason(
    *,
    title_matches_heading: bool,
    title_length: int,
    breadcrumb_client_width: int,
    breadcrumb_scroll_width: int,
    current_item_client_width: int,
    current_item_scroll_width: int,
    within_breadcrumb_bounds: bool,
) -> str | None:
    """Classify a long synthetic product breadcrumb that is clipped on mobile."""
    if not title_matches_heading:
        return "breadcrumb_title_mismatch"
    if title_length < 40:
        return "synthetic_title_too_short"
    if (
        breadcrumb_scroll_width > breadcrumb_client_width + 1
        or current_item_scroll_width > current_item_client_width + 1
    ):
        return "breadcrumb_text_overflow"
    if not within_breadcrumb_bounds:
        return "breadcrumb_outside_bounds"
    return None
