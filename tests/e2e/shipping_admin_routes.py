"""Dependency-free matching for PrestaShop native shipping admin links."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse


_MODERN_ADMIN_ROUTES = {
    "AdminCarriers": "/improve/shipping/carriers",
    "AdminShipping": "/improve/shipping/preferences",
}
_KOREAN_ADMIN_LANGUAGES = {"ko", "ko-kr"}


def matches_admin_controller_url(href: str, controller: str, admin_path: str) -> bool:
    """Match a native controller's legacy URL or PrestaShop 9.2 Symfony route."""
    parsed = urlparse(href)
    admin_prefix = admin_path.rstrip("/")
    if not admin_prefix or not parsed.path.startswith(admin_prefix + "/"):
        return False

    query = parse_qs(parsed.query, keep_blank_values=True)
    if query.get("controller") == [controller]:
        return True

    route_suffix = _MODERN_ADMIN_ROUTES.get(controller)
    if route_suffix is None:
        return False

    relative_path = parsed.path[len(admin_prefix) :].rstrip("/")
    if relative_path.startswith("/index.php/"):
        relative_path = relative_path[len("/index.php") :]
    return relative_path == route_suffix


def carrier_action_url(carriers_list_url: str, action: str, carrier_id: int | None = None) -> str:
    """Build a carrier form URL while retaining the token from PrestaShop's admin link."""
    if action not in {"create", "edit"}:
        raise ValueError("carrier action must be create or edit")
    if action == "edit" and (carrier_id is None or carrier_id < 1):
        raise ValueError("editing a carrier requires a positive carrier ID")

    parsed = urlparse(carriers_list_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    relative_path = parsed.path.rstrip("/")
    modern_route = "/improve/shipping/carriers"
    if relative_path.endswith(modern_route):
        suffix = "/create" if action == "create" else f"/{carrier_id}/edit"
        return urlunparse(parsed._replace(path=relative_path + suffix))

    if dict(query).get("controller") != "AdminCarriers":
        raise ValueError("carrier list URL is not an authenticated AdminCarriers route")

    action_parameters = {"addcarrier", "id_carrier", "updatecarrier"}
    query = [(key, value) for key, value in query if key not in action_parameters]
    if action == "create":
        query.append(("addcarrier", "1"))
    else:
        query.extend((("id_carrier", str(carrier_id)), ("updatecarrier", "1")))
    return urlunparse(parsed._replace(query=urlencode(query)))


def carrier_id_from_edit_url(href: str, admin_path: str) -> int | None:
    """Read the carrier ID from modern Symfony edit paths or the legacy admin route."""
    parsed = urlparse(href)
    admin_prefix = admin_path.rstrip("/")
    if not admin_prefix or not parsed.path.startswith(admin_prefix + "/"):
        return None

    relative_path = parsed.path[len(admin_prefix) :].rstrip("/")
    if relative_path.startswith("/index.php/"):
        relative_path = relative_path[len("/index.php") :]
    match = re.fullmatch(r"/improve/shipping/carriers/([0-9]+)/edit", relative_path)
    if match is not None:
        carrier_id = int(match.group(1))
        return carrier_id if carrier_id > 0 else None

    query = parse_qs(parsed.query, keep_blank_values=True)
    if query.get("controller") != ["AdminCarriers"] or query.get("updatecarrier") != ["1"]:
        return None
    carrier_ids = query.get("id_carrier", [])
    if len(carrier_ids) != 1 or re.fullmatch(r"[0-9]+", carrier_ids[0]) is None:
        return None
    carrier_id = int(carrier_ids[0])
    return carrier_id if carrier_id > 0 else None


def is_korean_admin_language(language: str) -> bool:
    """Accept Korean document language tags used by the PrestaShop Back Office."""
    return language.strip().casefold() in _KOREAN_ADMIN_LANGUAGES
