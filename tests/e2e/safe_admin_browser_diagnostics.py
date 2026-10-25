from __future__ import annotations

import re
from urllib.parse import urlsplit


SAFE_ADMIN_ROUTE_SEGMENTS = frozenset(
    {
        "admin-kuranea", "index.php", "login", "logout", "sell", "dashboard",
        "security", "compromised",
        "customer-service", "merchandise-return", "merchandise-returns",
        "orders", "order", "returns", "return", "customers", "customer",
        "catalog", "products", "product", "categories", "category",
        "view", "edit", "add", "new", "create", "settings", "configuration",
        "shipping", "stock", "monitoring", "modules", "employees", "addresses",
        "address", "payment", "design", "international", "marketing", "home",
    }
)


def safe_admin_pathname(candidate_url: str, admin_root: str) -> str:
    try:
        candidate = urlsplit(candidate_url)
        expected = urlsplit(admin_root)
        candidate_port = candidate.port or (443 if candidate.scheme == "https" else 80)
        expected_port = expected.port or (443 if expected.scheme == "https" else 80)
    except ValueError:
        return "unknown"

    if (
        candidate.scheme != expected.scheme
        or (candidate.hostname or "").lower() != (expected.hostname or "").lower()
        or candidate_port != expected_port
        or candidate.username is not None
        or candidate.password is not None
    ):
        return "outside_admin"

    raw_path = candidate.path or "/"
    if not raw_path.startswith("/"):
        return "unknown"
    admin_prefix = expected.path.rstrip("/")
    if raw_path != admin_prefix and not raw_path.startswith(admin_prefix + "/"):
        return "same_origin_non_admin"

    safe_segments: list[str] = []
    for segment in raw_path.split("/"):
        if not segment:
            safe_segments.append("")
        elif segment in SAFE_ADMIN_ROUTE_SEGMENTS:
            safe_segments.append(segment)
        elif re.fullmatch(r"[0-9]+", segment):
            safe_segments.append("<id>")
        else:
            safe_segments.append("<redacted>")
    safe_path = "/".join(safe_segments)
    if len(safe_path) > 240:
        return safe_path[:220].rstrip("/") + "/<truncated>"
    return safe_path


def safe_document_response_status(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unknown"
    try:
        status = int(value)
    except (OverflowError, ValueError):
        return "unknown"
    if status != value or not 100 <= status <= 599:
        return "unknown"
    return str(status)
