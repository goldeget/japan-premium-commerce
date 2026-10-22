"""Dependency-free matching for PrestaShop native shipping admin links."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


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


def is_korean_admin_language(language: str) -> bool:
    """Accept Korean document language tags used by the PrestaShop Back Office."""
    return language.strip().casefold() in _KOREAN_ADMIN_LANGUAGES
