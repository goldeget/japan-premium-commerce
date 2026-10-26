"""Pure route classification for PrestaShop's native search GET form."""

from urllib.parse import parse_qs, urlparse


def is_native_search_route(action_url: str, enabled_hidden_controllers: list[str]) -> bool:
    """Accept an explicit native controller, a unique hidden controller, or /search."""
    parsed = urlparse(action_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    action_controllers = query.get("controller", [])
    if action_controllers and action_controllers != ["search"]:
        return False
    if enabled_hidden_controllers and enabled_hidden_controllers != ["search"]:
        return False

    path_route = parsed.path.rstrip("/").endswith("/search")
    return bool(action_controllers == ["search"] or enabled_hidden_controllers == ["search"]
                or (path_route and not action_controllers))
