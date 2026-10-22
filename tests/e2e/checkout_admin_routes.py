"""Small, dependency-free URL checks for Back Office order links."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


_DETAIL_ACTIONS = {"detail", "details", "view", "vieworder"}


def is_modern_admin_order_detail_url(href: str, expected_order_id: int | str) -> bool:
    """Accept only the matching PrestaShop Symfony order detail route."""
    path_segments = [segment for segment in urlparse(href).path.rstrip("/").split("/") if segment]
    return len(path_segments) >= 4 and path_segments[-4:] == [
        "sell",
        "orders",
        str(expected_order_id),
        "view",
    ]


def is_legacy_admin_order_detail_url(href: str, expected_order_id: int | str) -> bool:
    """Accept only the matching legacy AdminOrders detail action URL."""
    parsed = urlparse(href)
    query = {
        key.casefold(): values
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
    }
    order_id = str(expected_order_id)
    if (
        query.get("controller") != ["AdminOrders"]
        or query.get("id_order") != [order_id]
        or "submitaction" in query
    ):
        return False

    action_values = [value.casefold() for value in query.get("action", [])]
    if any(action not in _DETAIL_ACTIONS for action in action_values):
        return False
    return "vieworder" in query or any(action in _DETAIL_ACTIONS for action in action_values)
