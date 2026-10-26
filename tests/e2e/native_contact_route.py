"""Safe, run-local native contact route fixture reader."""

import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


LOCALES = ("ja", "en", "ko")


def safe_contact_rewrite_segment(value: object) -> str | None:
    """Normalize one safe localized route segment, rejecting encoded separators."""
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    segment = value
    for _ in range(5):
        if (
            segment in {".", ".."}
            or any(char in segment for char in "/\\?#&=;")
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in segment)
        ):
            return None
        try:
            decoded = unquote(segment, errors="strict")
        except UnicodeDecodeError:
            return None
        if decoded == segment:
            return None if "%" in segment else segment
        segment = decoded
    return None


def contact_route_mismatch(
    candidate_url: str,
    shop_url: str,
    *,
    locale: str | None = None,
    localized_rewrite: str | None = None,
) -> str | None:
    """Return only a bounded mismatch category; never return URL components."""
    try:
        candidate, expected = urlparse(candidate_url), urlparse(shop_url)
        candidate_port = candidate.port
        if candidate_port is None:
            candidate_port = 443 if candidate.scheme == "https" else 80
        expected_port = expected.port
        if expected_port is None:
            expected_port = 443 if expected.scheme == "https" else 80
    except (TypeError, ValueError):
        return "path"

    if candidate.scheme.lower() != expected.scheme.lower():
        return "scheme"
    if (candidate.hostname or "").lower() != (expected.hostname or "").lower():
        return "host"
    if candidate_port < 1 or expected_port < 1:
        return "port"
    if candidate_port != expected_port:
        return "port"
    if candidate.username is not None or candidate.password is not None or candidate.fragment:
        return "origin"

    expected_base = expected.path.rstrip("/")
    candidate_path = candidate.path or "/"
    if expected_base:
        if candidate_path == expected_base:
            relative_path = "/"
        elif candidate_path.startswith(expected_base + "/"):
            relative_path = candidate_path[len(expected_base):]
        else:
            return "path"
    else:
        relative_path = candidate_path
    segments = [unquote(part) for part in relative_path.split("/") if part]

    try:
        query = parse_qs(candidate.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return "query"
    if any(len(values) != 1 for values in query.values()):
        return "query"
    if set(query) - {"controller", "id_lang"}:
        return "query"
    id_lang = query.get("id_lang", [])
    if id_lang and (not id_lang[0].isdigit() or int(id_lang[0]) < 1):
        return "query"

    if "controller" in query:
        if query["controller"] != ["contact"]:
            return "controller"
        # Dispatcher::createUrl() uses the front-controller query fallback when
        # a localized meta route is absent. Link::getPageLink() can therefore
        # generate /?controller=contact or /{iso}/?controller=contact; both are
        # native routes when the controller selector is exact and same-origin.
        allowed_paths = {(), ("index.php",)}
        if locale in LOCALES:
            allowed_paths.add((locale,))
        return None if tuple(part.casefold() for part in segments) in allowed_paths else "path"

    allowed_slugs = {"contact", "contact-us"}
    safe_rewrite = safe_contact_rewrite_segment(localized_rewrite)
    if localized_rewrite is not None and safe_rewrite is None:
        return "path"
    if safe_rewrite is not None:
        allowed_slugs.add(safe_rewrite.casefold())
    if locale in LOCALES:
        allowed_paths = {(slug,) for slug in allowed_slugs}
        allowed_paths.add((locale,))
        allowed_paths = {
            path if path == (locale,) else (locale, *path)
            for path in allowed_paths
        } | {(slug,) for slug in allowed_slugs}
    else:
        allowed_paths = {(slug,) for slug in allowed_slugs}
    return None if tuple(part.casefold() for part in segments) in allowed_paths else "path"


def contact_route_class(
    candidate_url: str,
    shop_url: str,
    *,
    locale: str | None = None,
    localized_rewrite: str | None = None,
) -> str:
    return "contact" if contact_route_mismatch(
        candidate_url,
        shop_url,
        locale=locale,
        localized_rewrite=localized_rewrite,
    ) is None else "other"


def read_contact_route_fixture(path: str | Path, shop_url: str) -> dict:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected_keys = {
        "schema", "contact_meta_present", "rewriting_enabled", "canonical_redirect_mode",
        "contactform_enabled", "localized_rewrites", "localized_rewrite_by_iso", "urls_by_iso",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys or payload.get("schema") != 1:
        raise ValueError("native contact route fixture did not match its bounded schema")
    for key in ("contact_meta_present", "rewriting_enabled", "contactform_enabled"):
        if type(payload.get(key)) is not bool:
            raise ValueError("native contact route fixture contains an invalid setting readback")
    if type(payload.get("canonical_redirect_mode")) is not int:
        raise ValueError("native contact route fixture contains an invalid canonical setting")
    rewrites, urls = payload.get("localized_rewrites"), payload.get("urls_by_iso")
    rewrite_paths = payload.get("localized_rewrite_by_iso")
    if (not isinstance(rewrites, dict) or set(rewrites) != set(LOCALES)
            or any(type(rewrites[locale]) is not bool for locale in LOCALES)
            or not isinstance(rewrite_paths, dict) or set(rewrite_paths) != set(LOCALES)
            or any(value is not None and not isinstance(value, str) for value in rewrite_paths.values())
            or not isinstance(urls, dict) or set(urls) != set(LOCALES)):
        raise ValueError("native contact route fixture omitted a supported storefront locale")
    for locale in LOCALES:
        rewrite_path = rewrite_paths[locale]
        if rewrite_path is not None and safe_contact_rewrite_segment(rewrite_path) is None:
            raise ValueError(f"native contact route fixture contains an unsafe localized rewrite: locale={locale}; component=path")
        if rewrites[locale] != (rewrite_path is not None):
            raise ValueError(f"native contact route fixture has inconsistent localized rewrite evidence: locale={locale}; component=path")
        candidate = urls[locale]
        if not isinstance(candidate, str):
            raise ValueError(f"generated contact route left the isolated native route: locale={locale}; component=path")
        mismatch = contact_route_mismatch(
            candidate,
            shop_url,
            locale=locale,
            localized_rewrite=rewrite_paths[locale],
        )
        if mismatch is not None:
            raise ValueError(
                f"generated contact route left the isolated native route: locale={locale}; component={mismatch}"
            )
        query = parse_qs(urlparse(candidate).query, keep_blank_values=True)
        if set(query) - {"controller", "id_lang"} or any(len(values) != 1 for values in query.values()):
            raise ValueError("generated contact route contained unexpected or ambiguous parameters")
        if "controller" in query and query["controller"] != ["contact"]:
            raise ValueError("generated contact route selected an unexpected native controller")
    return payload


def contact_url_for_locale(path: str | Path, shop_url: str, locale: str) -> str:
    if locale not in LOCALES:
        raise ValueError("unsupported native contact locale")
    payload = read_contact_route_fixture(path, shop_url)
    return payload["urls_by_iso"][locale]


def probe_contact_route(
    driver,
    candidate_url: str,
    shop_url: str,
    *,
    locale: str | None = None,
    localized_rewrite: str | None = None,
) -> dict:
    """Probe a same-origin GET and retain only allowlisted response facts."""
    rewrite_segment = safe_contact_rewrite_segment(localized_rewrite)
    if localized_rewrite is not None and rewrite_segment is None:
        raise ValueError("contact route probe left the isolated native route: component=path")
    if contact_route_class(
        candidate_url, shop_url, locale=locale, localized_rewrite=localized_rewrite
    ) != "contact":
        raise ValueError("contact route probe left the isolated native route: component=path")
    raw = driver.execute_async_script("""
      const [url, shopUrl, locale, localizedRewrite, done] = arguments;
      const classify = value => {
        try {
          const candidate = new URL(value, location.href);
          const shop = new URL(shopUrl, location.href);
          if (candidate.origin !== shop.origin || candidate.username || candidate.password || candidate.hash) return 'other';
          let relativePath = candidate.pathname || '/';
          const basePath = shop.pathname.replace(/\\/+$/, '');
          if (basePath) {
            if (relativePath === basePath) relativePath = '/';
            else if (relativePath.startsWith(basePath + '/')) relativePath = relativePath.slice(basePath.length);
            else return 'other';
          }
          const segments = relativePath.split('/').filter(Boolean).map(x => decodeURIComponent(x).toLowerCase());
          if (segments.some(segment => segment === '.' || segment === '..' || /[\\/\\?#&=;\\u0000-\\u001f\\u007f]/.test(segment))) return 'other';
          const controllers = candidate.searchParams.getAll('controller');
          const keys = [...new Set([...candidate.searchParams.keys()])];
          if (keys.some(key => key !== 'controller' && key !== 'id_lang')) return 'other';
          if (candidate.searchParams.getAll('id_lang').length > 1) return 'other';
          const languageIds = candidate.searchParams.getAll('id_lang');
          if (languageIds.some(value => !/^[1-9][0-9]*$/.test(value))) return 'other';
          if (controllers.length) {
            const validPath = segments.length === 0 || (segments.length === 1 && segments[0] === 'index.php')
              || (locale && segments.length === 1 && segments[0] === locale);
            return controllers.length === 1 && controllers[0] === 'contact' && validPath ? 'contact' : 'other';
          }
          const slugs = ['contact', 'contact-us'];
          if (localizedRewrite) slugs.push(decodeURIComponent(localizedRewrite).toLowerCase());
          const expected = new Set(slugs.map(slug => slug.split('/').filter(Boolean)));
          const matches = paths => [...expected].some(slug => JSON.stringify(slug) === JSON.stringify(paths));
          const plain = matches(segments);
          const localized = locale && segments.length > 1 && segments[0] === locale && matches(segments.slice(1));
          return plain || localized ? 'contact' : 'other';
        } catch (_) { return 'other'; }
      };
      fetch(url, {method: 'GET', credentials: 'same-origin', redirect: 'follow', cache: 'no-store'})
        .then(async response => {
          const html = new DOMParser().parseFromString(await response.text(), 'text/html');
          const forms = html.querySelectorAll('.contact-form form').length;
          const bodyId = (html.body && html.body.id || '').toLowerCase();
          const pageClass = forms > 0 || bodyId === 'contact' ? 'contact'
            : (bodyId === 'pagenotfound' || bodyId === 'page-not-found' ? 'not_found' : 'other');
          const cache = (response.headers.get('cache-control') || '').toLowerCase();
          done({status: response.status, same_origin: new URL(response.url).origin === location.origin,
            route_class: classify(response.url), form_count: forms, page_class: pageClass,
            private_no_store: cache.includes('private') && cache.includes('no-store')});
        }).catch(() => done({status: null, same_origin: false, route_class: 'other', form_count: 0,
          page_class: 'other', private_no_store: false}));
    """, candidate_url, shop_url, locale or "", rewrite_segment or "")
    keys = {"status", "same_origin", "route_class", "form_count", "page_class", "private_no_store"}
    if (not isinstance(raw, dict) or set(raw) != keys
            or (raw["status"] is not None and (type(raw["status"]) is not int or not 100 <= raw["status"] <= 599))
            or type(raw["same_origin"]) is not bool
            or raw["route_class"] not in {"contact", "other"}
            or type(raw["form_count"]) is not int or raw["form_count"] < 0
            or raw["page_class"] not in {"contact", "not_found", "other"}
            or type(raw["private_no_store"]) is not bool):
        raise ValueError("contact route probe returned an invalid bounded result")
    return raw
