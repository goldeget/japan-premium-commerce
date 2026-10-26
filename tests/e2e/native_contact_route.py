"""Safe, run-local native contact route fixture reader."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


LOCALES = ("ja", "en", "ko")


def contact_route_class(candidate_url: str, shop_url: str) -> str:
    candidate, expected = urlparse(candidate_url), urlparse(shop_url)
    if ((candidate.scheme, candidate.hostname, candidate.port)
            != (expected.scheme, expected.hostname, expected.port)
            or candidate.username is not None or candidate.password is not None or candidate.fragment):
        return "other"
    controllers = parse_qs(candidate.query, keep_blank_values=True).get("controller", [])
    if controllers:
        return "contact" if controllers == ["contact"] and candidate.path.rstrip("/").endswith("/index.php") else "other"
    segments = {segment.lower() for segment in candidate.path.split("/") if segment}
    return "contact" if segments & {"contact", "contact-us"} else "other"


def read_contact_route_fixture(path: str | Path, shop_url: str) -> dict:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected_keys = {
        "schema", "contact_meta_present", "rewriting_enabled", "canonical_redirect_mode",
        "contactform_enabled", "localized_rewrites", "urls_by_iso",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys or payload.get("schema") != 1:
        raise ValueError("native contact route fixture did not match its bounded schema")
    for key in ("contact_meta_present", "rewriting_enabled", "contactform_enabled"):
        if type(payload.get(key)) is not bool:
            raise ValueError("native contact route fixture contains an invalid setting readback")
    if type(payload.get("canonical_redirect_mode")) is not int:
        raise ValueError("native contact route fixture contains an invalid canonical setting")
    rewrites, urls = payload.get("localized_rewrites"), payload.get("urls_by_iso")
    if (not isinstance(rewrites, dict) or set(rewrites) != set(LOCALES)
            or any(type(rewrites[locale]) is not bool for locale in LOCALES)
            or not isinstance(urls, dict) or set(urls) != set(LOCALES)):
        raise ValueError("native contact route fixture omitted a supported storefront locale")
    for locale in LOCALES:
        candidate = urls[locale]
        if not isinstance(candidate, str) or contact_route_class(candidate, shop_url) != "contact":
            raise ValueError("generated contact route left the isolated native route")
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


def probe_contact_route(driver, candidate_url: str, shop_url: str) -> dict:
    """Probe a same-origin GET and retain only allowlisted response facts."""
    if contact_route_class(candidate_url, shop_url) != "contact":
        raise ValueError("contact route probe left the isolated native route")
    raw = driver.execute_async_script("""
      const [url, done] = arguments;
      const classify = value => {
        try {
          const candidate = new URL(value, location.href);
          const current = new URL(location.href);
          if (candidate.origin !== current.origin) return 'other';
          const controllers = candidate.searchParams.getAll('controller');
          if (controllers.length) return controllers.length === 1 && controllers[0] === 'contact' ? 'contact' : 'other';
          const segments = candidate.pathname.split('/').filter(Boolean).map(x => decodeURIComponent(x).toLowerCase());
          return segments.some(x => x === 'contact' || x === 'contact-us') ? 'contact' : 'other';
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
    """, candidate_url)
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
