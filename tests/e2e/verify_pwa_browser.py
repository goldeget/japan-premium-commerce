#!/usr/bin/env python3
"""Verify the public PWA lifecycle in a disposable Chromium shop."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import uuid
from collections.abc import Callable
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import (
    parse_qs,
    parse_qsl,
    unquote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.remote.websocket_connection import WebSocketConnection
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # Pure manifest contract helpers remain importable without Selenium.
    webdriver = None
    TimeoutException = Exception
    Options = None
    By = None
    WebSocketConnection = None
    EC = None
    WebDriverWait = None

EXPECTED_SHOP_PORT = 18080
MAX_PWA_DIAGNOSTIC_RESPONSE_COUNT = 20
MAX_PWA_DIAGNOSTIC_ELEMENT_COUNT = 20
PWA_LOGOUT_ROUTE_CLASSES = {"authentication", "account", "home", "other"}
PWA_DIAGNOSTIC_MAX_REDIRECTS = 8
PWA_DIAGNOSTIC_MAX_PATH_LENGTH = 160
PWA_DIAGNOSTIC_MAX_QUERY_KEYS = 8
PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS = {
    "authentication",
    "login",
    "\u30ed\u30b0\u30a4\u30f3",
    "\ub85c\uadf8\uc778",
}
PWA_DIAGNOSTIC_ROUTE_SEGMENTS = {
    "account",
    "addresses",
    "address",
    "authentication",
    "cart",
    "discount",
    "guest-tracking",
    "history",
    "identity",
    "index.php",
    "マイアカウント",
    "내 계정",
    *PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS,
    "my-account",
    "order",
    "order-detail",
    "order-follow",
    "password",
    "password-recovery",
    "password-reset",
    "search",
}
PWA_DIAGNOSTIC_QUERY_KEYS = {
    "action",
    "back",
    "controller",
    "id_lang",
    "id_order",
    "lang",
    "mylogout",
    "token",
}
PWA_DIAGNOSTIC_BACK_VALUES = {
    "addresses",
    "authentication",
    "cart",
    "history",
    "identity",
    "my-account",
    "order",
    "order-detail",
    "order-follow",
}
PWA_PRIVATE_CUSTOMER_ROUTES = {
    "address",
    "addresses",
    "cart",
    "discount",
    "getfile",
    "guest-tracking",
    "history",
    "identity",
    "my-account",
    "マイアカウント",
    "내 계정",
    "order",
    "order-confirmation",
    "order-detail",
    "order-follow",
    "order-opc",
    "order-return",
    "order-slip",
    "pdf-invoice",
    "pdf-order-return",
    "pdf-order-slip",
}
PWA_DIAGNOSTIC_BACK_VALUES.update(PWA_PRIVATE_CUSTOMER_ROUTES)
PWA_DIAGNOSTIC_WORKER_SOURCES = {
    "cache-storage",
    "fallback-code",
    "http-cache",
    "network",
}
PWA_SERVICE_WORKER_DIAGNOSTIC_PHASES = {
    "api_check",
    "ready_wait",
    "active_check",
    "controller_wait",
    "complete",
    "webdriver_script",
    "validation",
}
PWA_SERVICE_WORKER_DIAGNOSTIC_CATEGORIES = {
    "none",
    "api_unavailable",
    "observer_unavailable",
    "ready_timeout",
    "ready_rejected",
    "active_missing",
    "controller_timeout",
    "controller_missing",
    "webdriver_timeout",
    "webdriver_error",
    "invalid_result",
    "scope_mismatch",
    "script_origin_mismatch",
    "script_path_mismatch",
}
PWA_SERVICE_WORKER_REGISTRATION_OUTCOMES = {
    "not_attempted",
    "pending",
    "resolved",
    "rejected",
}
PWA_SERVICE_WORKER_STATES = {
    "installing",
    "installed",
    "activating",
    "activated",
    "redundant",
    "none",
}
PWA_SERVICE_WORKER_ERROR_NAMES = {
    "AbortError",
    "Error",
    "InvalidStateError",
    "NetworkError",
    "NotAllowedError",
    "SecurityError",
    "TimeoutError",
    "TypeError",
    "unknown",
    "JavascriptException",
    "TimeoutException",
    "WebDriverException",
}
PWA_SERVICE_WORKER_RESPONSE_MIME_TYPES = {
    "application/ecmascript",
    "application/javascript",
    "application/x-javascript",
    "text/ecmascript",
    "text/javascript",
}
PWA_SUPPORTED_LOCALES = ("ja", "en", "ko")
PWA_VIEWPORTS = (
    ("desktop", 1440, 960),
    ("mobile", 390, 844),
)
PWA_OFFLINE_FALLBACKS = {
    "ja": ("Japanese", "インターネットに接続できません"),
    "en": ("English", "You are offline"),
    "ko": ("Korean", "연결을 확인해 주세요"),
}


class PwaDiagnosticAssertionError(AssertionError):
    """An assertion with bounded machine-readable context safe for CI annotations."""

    def __init__(self, message: str, diagnostic_code: str, safe_metadata: dict[str, object]) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code
        self.safe_metadata = safe_metadata


def response_count_diagnostic(value: object) -> str:
    count = value if type(value) is int else 0
    bounded_count = min(max(count, 0), MAX_PWA_DIAGNOSTIC_RESPONSE_COUNT)
    return f"; response_count={bounded_count}"


def validate_isolated_ci_target(base_url: str) -> None:
    """Refuse to create a PWA test customer outside this run's disposable shop."""
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or re.fullmatch(r"[0-9]+", run_id) is None
        or re.fullmatch(r"[0-9]+", attempt) is None
        or os.environ.get("CI_COMPOSE_PROJECT_NAME", "") != expected_project
    ):
        raise ValueError("PWA QA requires its exact isolated GitHub Actions Compose project")

    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        port = parsed.port
    except (TypeError, ValueError) as error:
        raise ValueError("PWA QA requires the isolated shop on localhost:18080") from error
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host.casefold().rstrip(".") == "localhost"
    if (
        parsed.scheme != "http"
        or not is_loopback
        or port != EXPECTED_SHOP_PORT
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("PWA QA requires the isolated shop on localhost:18080")


def manifest_installability_issues(
    manifest: dict[str, object], base_url: str, secure_context: bool
) -> list[str]:
    """Return unmet Chromium installability prerequisites without browser state."""
    issues: list[str] = []
    if not secure_context:
        issues.append("page is not a secure context")

    try:
        base = urlparse(base_url)
        base_path = base.path.rstrip("/")
        expected_scope = (base_path or "") + "/"
        if expected_scope == "//":
            expected_scope = "/"
    except (TypeError, ValueError):
        return issues + ["shop base URL is invalid"]

    for key in ("id", "start_url", "scope"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value:
            issues.append(f"manifest is missing {key}")
            continue
        target = urlparse(urljoin(base_url.rstrip("/") + "/", value))
        same_origin = (
            target.scheme == base.scheme
            and target.hostname == base.hostname
            and target.port == base.port
        )
        target_path = target.path.rstrip("/") + "/"
        if not same_origin or target_path != expected_scope:
            issues.append(f"manifest {key} is outside the shop scope")

    name = manifest.get("name")
    if not isinstance(name, str) or not name.strip():
        issues.append("manifest has no app name")
    if manifest.get("display") not in {"standalone", "fullscreen", "minimal-ui"}:
        issues.append("manifest display mode is not installable")

    icons = manifest.get("icons")
    valid_icons = [icon for icon in icons if isinstance(icon, dict)] if isinstance(icons, list) else []

    def has_icon(size: str, purpose: str) -> bool:
        for icon in valid_icons:
            sizes = icon.get("sizes")
            purposes = set(str(icon.get("purpose", "any")).split())
            if isinstance(sizes, str) and size in sizes.split() and purpose in purposes:
                return True
        return False

    for size, purpose, description in (
        ("192x192", "any", "a 192x192 standard icon"),
        ("512x512", "any", "a 512x512 standard icon"),
        ("512x512", "maskable", "a 512x512 maskable icon"),
    ):
        if not has_icon(size, purpose):
            issues.append(f"manifest is missing {description}")
    return issues


def same_origin(reference_url: str, candidate_url: str) -> bool:
    """Compare scheme, host, and effective port; reject credentials and invalid URLs."""
    try:
        reference = urlparse(reference_url)
        candidate = urlparse(urljoin(reference_url, candidate_url))
        if any(not parsed.hostname or parsed.username or parsed.password for parsed in (reference, candidate)):
            return False
        if reference.scheme not in {"http", "https"} or candidate.scheme not in {"http", "https"}:
            return False
        reference_port = reference.port or (443 if reference.scheme == "https" else 80)
        candidate_port = candidate.port or (443 if candidate.scheme == "https" else 80)
        return (
            reference.scheme.lower() == candidate.scheme.lower()
            and reference.hostname.lower().rstrip(".") == candidate.hostname.lower().rstrip(".")
            and reference_port == candidate_port
        )
    except (TypeError, ValueError):
        return False


def is_private_customer_back_target(value: object, shop_url: str) -> bool:
    """Recognize same-origin private back destinations without retaining their URL values."""
    if not isinstance(value, str) or not value.strip() or len(value) > 8192:
        return False
    candidate = value.strip()
    if candidate.casefold() in PWA_PRIVATE_CUSTOMER_ROUTES:
        return True
    try:
        absolute_url = urljoin(shop_url.rstrip("/") + "/", candidate)
        if not same_origin(shop_url, absolute_url):
            return False
        parsed = urlparse(absolute_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if any(
            controller.casefold() in PWA_PRIVATE_CUSTOMER_ROUTES
            for controller in query.get("controller", [])
        ):
            return True
        path_segments = (parsed.path or "/").split("/")
        return any(
            unquote(segment, errors="strict").casefold() in PWA_PRIVATE_CUSTOMER_ROUTES
            for segment in path_segments
            if segment
        )
    except (TypeError, UnicodeDecodeError, ValueError):
        return False


def same_storefront_route(candidate_url: str, expected_url: str, shop_url: str) -> bool:
    """Compare same-origin route semantics internally without exposing query values."""
    if not same_origin(shop_url, candidate_url) or not same_origin(shop_url, expected_url):
        return False
    try:
        candidate = urlparse(urljoin(shop_url.rstrip("/") + "/", candidate_url))
        expected = urlparse(urljoin(shop_url.rstrip("/") + "/", expected_url))
        candidate_path = unquote(candidate.path or "/", errors="strict").rstrip("/") or "/"
        expected_path = unquote(expected.path or "/", errors="strict").rstrip("/") or "/"
        if candidate_path != expected_path:
            return False
        candidate_query = parse_qs(candidate.query, keep_blank_values=True)
        expected_query = parse_qs(expected.query, keep_blank_values=True)
        if candidate_query.get("controller", []) != expected_query.get("controller", []):
            return False
        for key in ("id_lang", "isolang", "lang"):
            candidate_values = candidate_query.get(key, [])
            expected_values = expected_query.get(key, [])
            if key in {"isolang", "lang"}:
                candidate_values = [value.casefold() for value in candidate_values]
                expected_values = [value.casefold() for value in expected_values]
            if candidate_values != expected_values:
                return False
    except (TypeError, UnicodeDecodeError, ValueError):
        return False
    return True


def annotate_generated_login_route_match(
    trace: dict[str, object],
    response_url: object,
    expected_login_url: str | None,
    shop_url: str,
) -> bool | None:
    """Store only a safe match between the final response and generated sign-in route."""
    if expected_login_url is None:
        return None
    matches = (
        same_storefront_route(response_url, expected_login_url, shop_url)
        if isinstance(response_url, str)
        else None
    )
    trace["final_route_matches_login"] = matches
    return matches


def browser_locale_profile(locale: str) -> dict[str, str]:
    profiles = {
        "ja": {"browser_tag": "ja-JP", "accept_language": "ja-JP,ja;q=0.9"},
        "en": {"browser_tag": "en-US", "accept_language": "en-US,en;q=0.9"},
        "ko": {"browser_tag": "ko-KR", "accept_language": "ko-KR,ko;q=0.9"},
    }
    try:
        return dict(profiles[locale])
    except KeyError as error:
        raise AssertionError("unsupported storefront locale requested by PWA QA") from error


def pwa_browser_cases() -> tuple[tuple[str, str, int, int, str], ...]:
    """Return one independent browser case for every supported locale and viewport."""
    return tuple(
        (device, locale, width, height, f"{device}-{locale}")
        for device, width, height in PWA_VIEWPORTS
        for locale in PWA_SUPPORTED_LOCALES
    )


def resolve_storefront_locale_url(
    options: object, locale: str, shop_url: str
) -> str:
    """Resolve the native language selector destination without guessing route slugs."""
    if locale not in PWA_SUPPORTED_LOCALES:
        raise AssertionError("unsupported storefront locale requested by PWA QA")
    if not isinstance(options, (list, tuple)):
        raise AssertionError("the PrestaShop language selector is unavailable")
    matches = [
        option
        for option in options
        if isinstance(option, dict)
        and isinstance(option.get("iso_code"), str)
        and option["iso_code"].casefold() == locale
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("value"), str) or not matches[0]["value"]:
        raise AssertionError("the PrestaShop language selector has no unique locale destination")
    destination = urljoin(shop_url.rstrip("/") + "/", matches[0]["value"])
    if not same_origin(shop_url, destination):
        raise AssertionError("the language selector changed the isolated shop origin")
    return destination


def decode_path_for_validation(path: str) -> str:
    """Decode bounded URL-encoding layers and reject separators created by decoding."""
    current = path
    for _ in range(8):
        decoded = unquote(current, errors="strict")
        if decoded == current:
            return current
        if decoded.count("/") != current.count("/") or "\\" in decoded:
            raise ValueError("encoded path separator")
        current = decoded
    raise ValueError("excessively encoded path")


def localized_controller_url(shop_url: str, locale_home_url: str, route: str) -> str:
    """Build a localized index.php URL without carrying unrelated query values."""
    if not all(isinstance(value, str) for value in (shop_url, locale_home_url, route)):
        raise ValueError("localized storefront route is invalid")
    if not same_origin(shop_url, locale_home_url):
        raise ValueError("localized storefront home escaped the isolated shop origin")

    shop = urlparse(shop_url)
    home = urlparse(locale_home_url)
    target = urlparse(route)
    try:
        decoded_shop_path = decode_path_for_validation(shop.path)
        decoded_home_path = decode_path_for_validation(home.path)
        decoded_route_path = decode_path_for_validation(target.path)
    except (UnicodeDecodeError, ValueError):
        raise ValueError("localized storefront route path is invalid") from None
    if (
        home.username is not None
        or home.password is not None
        or home.fragment
        or target.scheme
        or target.netloc
        or target.username is not None
        or target.password is not None
        or target.path.startswith("/")
        or target.fragment
        or target.params
        or decoded_route_path != "index.php"
        or any(segment in {".", ".."} for segment in decoded_home_path.split("/"))
    ):
        raise ValueError("localized storefront controller route is invalid")

    shop_path = decoded_shop_path.rstrip("/")
    locale_path = home.path or "/"
    if shop_path and decoded_home_path.rstrip("/") != shop_path and not decoded_home_path.startswith(
        shop_path + "/"
    ):
        raise ValueError("localized storefront home escaped the shop path")

    locale_query_keys = {"id_lang", "isolang", "lang"}
    route_query = parse_qsl(target.query, keep_blank_values=True)
    allowed_route_query_keys = locale_query_keys | {"controller", "action"}
    if any(key.casefold() not in allowed_route_query_keys for key, _ in route_query):
        raise ValueError("localized storefront controller query is invalid")
    route_keys = {key.casefold() for key, _ in route_query}
    locale_query = [
        (key, value)
        for key, value in parse_qsl(home.query, keep_blank_values=True)
        if key.casefold() in locale_query_keys and key.casefold() not in route_keys
    ]

    locale_directory = locale_path if locale_path.endswith("/") else locale_path + "/"
    target_path = locale_directory + "index.php"
    if shop_path and not (
        decoded_home_path.rstrip("/") == shop_path
        or decoded_home_path.startswith(shop_path + "/")
    ):
        raise ValueError("localized storefront controller escaped the shop path")
    localized_url = urlunparse(
        (home.scheme, home.netloc, target_path, "", urlencode(route_query + locale_query), "")
    )
    if not same_origin(shop_url, localized_url):
        raise ValueError("localized storefront controller escaped the isolated shop origin")
    return localized_url


def assert_document_locale(driver: webdriver.Chrome, locale: str, page_label: str) -> None:
    if locale not in PWA_SUPPORTED_LOCALES:
        raise AssertionError("unsupported storefront locale requested by PWA QA")
    try:
        document_language = (
            driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or ""
        ).casefold()
    except Exception as error:
        raise AssertionError(f"{page_label} did not expose a document language") from error
    if document_language.split("-", 1)[0] != locale:
        raise AssertionError(f"{page_label} did not render the expected storefront locale")


def assert_offline_fallback_content(driver: webdriver.Chrome, locale: str) -> None:
    if locale not in PWA_OFFLINE_FALLBACKS:
        raise AssertionError("unsupported storefront locale requested by PWA QA")
    language_name, expected_heading = PWA_OFFLINE_FALLBACKS[locale]
    assert_document_locale(driver, locale, "offline fallback")
    body = driver.find_element(By.TAG_NAME, "body").text
    if expected_heading not in body:
        raise AssertionError(
            f"offline navigation did not show the expected {language_name} offline fallback"
        )


def select_storefront_locale(
    driver: webdriver.Chrome, shop_url: str, locale: str
) -> str:
    """Open the localized home page using PrestaShop's generated language URL."""
    options = WebDriverWait(driver, 30).until(
        lambda browser: browser.find_elements(
            By.CSS_SELECTOR,
            "select.js-language-selector option[data-iso-code]",
        )
        or False
    )
    option_values = [
        {
            "iso_code": option.get_attribute("data-iso-code") or "",
            "value": option.get_attribute("value") or "",
        }
        for option in options
    ]
    destination = resolve_storefront_locale_url(option_values, locale, shop_url)
    driver.get(destination)
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    assert_document_locale(driver, locale, "localized storefront home")
    return destination


def customer_route_class(candidate_url: str, shop_url: str) -> str:
    """Classify a same-origin customer page without returning any URL components."""
    if not same_origin(shop_url, candidate_url):
        return "other"
    try:
        shop = urlparse(shop_url)
        candidate = urlparse(candidate_url)
        base_path = shop.path.rstrip("/")
        candidate_path = candidate.path.rstrip("/") or "/"
        if base_path and (candidate_path == base_path or candidate_path.startswith(base_path + "/")):
            relative_path = candidate_path[len(base_path) :].strip("/")
        else:
            relative_path = candidate_path.strip("/")
        segments = [unquote(segment).casefold() for segment in relative_path.split("/") if segment]
        controllers = parse_qs(candidate.query).get("controller", [])
        controller = controllers[-1].casefold() if controllers else ""
    except (TypeError, ValueError, IndexError):
        return "other"

    if controller == "authentication" or any(
        segment in PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS
        or segment in {"password-reset", "password-recovery"}
        for segment in segments
    ):
        return "authentication"
    if controller in {
        "my-account",
        "マイアカウント",
        "내 계정",
        "identity",
        "addresses",
        "address",
        "history",
        "order-detail",
        "order-follow",
        "discount",
        "guest-tracking",
    } or any(
        segment in {
            "my-account",
            "マイアカウント",
            "내 계정",
            "account",
            "identity",
            "addresses",
            "address",
            "history",
            "order-detail",
            "order-follow",
            "discount",
            "guest-tracking",
        }
        for segment in segments
    ):
        return "account"

    if segments and re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", segments[0]):
        segments = segments[1:]
    if not segments or segments == ["index.php"]:
        return "home"
    return "other"


def _bounded_logout_element_count(value: object) -> int | None:
    if type(value) is not int:
        return None
    return min(max(value, 0), MAX_PWA_DIAGNOSTIC_ELEMENT_COUNT)


def safe_logout_wait_diagnostics(driver: webdriver.Chrome, shop_url: str) -> dict[str, object]:
    """Read only allowlisted route/form state from the final same-origin document."""
    metadata: dict[str, object] = {
        "final_route_class": "other",
        "final_document_status": None,
        "login_form_count": None,
        "login_form_visible": None,
        "email_field_count": None,
        "email_field_visible": None,
        "ready_state": "unknown",
    }
    try:
        current_url = driver.current_url
    except Exception:
        return metadata
    if not isinstance(current_url, str) or not same_origin(shop_url, current_url):
        return metadata

    metadata["final_route_class"] = customer_route_class(current_url, shop_url)
    try:
        snapshot = driver.execute_script(
            """
        const visible = (element) => {
          if (!element) return false;
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden'
            && rect.width > 0 && rect.height > 0;
        };
        const loginForms = [...document.querySelectorAll('#login-form')];
        const emailFields = [...document.querySelectorAll("#login-form input[name='email']")];
        const navigation = performance.getEntriesByType('navigation')[0];
        let navigationSameOrigin = false;
        try {
          navigationSameOrigin = Boolean(
            navigation && new URL(navigation.name, window.location.href).origin === window.location.origin
          );
        } catch (_) {}
        const status = navigationSameOrigin ? navigation.responseStatus : null;
        return {
          navigation_same_origin: navigationSameOrigin,
          response_status: Number.isInteger(status) ? status : null,
          login_form_count: loginForms.length,
          login_form_visible: loginForms.some(visible),
          email_field_count: emailFields.length,
          email_field_visible: emailFields.some(visible),
          ready_state: document.readyState,
        };
            """
        )
    except Exception:
        return metadata
    if not isinstance(snapshot, dict):
        return metadata

    status = snapshot.get("response_status")
    if (
        snapshot.get("navigation_same_origin") is True
        and type(status) is int
        and 100 <= status <= 599
    ):
        metadata["final_document_status"] = status
    metadata["login_form_count"] = _bounded_logout_element_count(snapshot.get("login_form_count"))
    metadata["email_field_count"] = _bounded_logout_element_count(snapshot.get("email_field_count"))
    for key in ("login_form_visible", "email_field_visible"):
        value = snapshot.get(key)
        metadata[key] = value if type(value) is bool else None
    ready_state = snapshot.get("ready_state")
    metadata["ready_state"] = (
        ready_state
        if isinstance(ready_state, str) and ready_state in {"loading", "interactive", "complete"}
        else "unknown"
    )
    return metadata


def capture_logout_snapshot_preserving_error(
    driver: webdriver.Chrome,
    shop_url: str,
    *,
    prior_error: BaseException | None = None,
) -> tuple[dict[str, object], BaseException | None]:
    """Capture bounded context without replacing the logout assertion that failed first."""
    try:
        snapshot = safe_logout_wait_diagnostics(driver, shop_url)
    except Exception as diagnostic_error:
        return {}, prior_error if prior_error is not None else diagnostic_error
    return snapshot, prior_error


def prefer_primary_failure_substage(
    primary_error: BaseException | None,
    primary_substage: str,
    fallback_substage: str,
) -> str:
    """Keep reporting the stage that first failed even if restoration later fails too."""
    if primary_error is not None and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", primary_substage):
        return primary_substage
    return fallback_substage


def _safe_path(path: object) -> str:
    if not isinstance(path, str) or not path.startswith("/") or len(path) > 2048:
        return "<other>"
    if path == "<off-origin>":
        return path
    safe_segments: list[str] = []
    for raw_segment in path.split("/"):
        if not raw_segment:
            safe_segments.append("")
            continue
        segment = unquote(raw_segment)
        normalized = segment.casefold()
        if normalized in PWA_DIAGNOSTIC_ROUTE_SEGMENTS:
            safe_segments.append(normalized)
        elif normalized in {"ja", "en", "ko"}:
            safe_segments.append(normalized)
        elif segment == "ログイン":
            safe_segments.append(segment)
        elif segment == "<other>":
            safe_segments.append(segment)
        else:
            safe_segments.append("<other>")
    safe_path = "/".join(safe_segments)
    if len(safe_path) > PWA_DIAGNOSTIC_MAX_PATH_LENGTH:
        return "/<other>"
    return safe_path


def _safe_query_keys(values: object) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    keys = {
        value.casefold()
        for value in values
        if isinstance(value, str)
        and value.casefold() in PWA_DIAGNOSTIC_QUERY_KEYS
    }
    return sorted(keys)[:PWA_DIAGNOSTIC_MAX_QUERY_KEYS]


def _safe_navigation_target_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {"path": "<other>", "query_keys": []}
    path = value.get("path")
    if path == "<off-origin>":
        return {"path": "<off-origin>", "query_keys": []}
    safe: dict[str, object] = {
        "path": _safe_path(path),
        "query_keys": _safe_query_keys(value.get("query_keys")),
    }
    controller = value.get("controller")
    if isinstance(controller, str) and controller.casefold() in PWA_DIAGNOSTIC_ROUTE_SEGMENTS:
        safe["controller"] = controller.casefold()
    elif isinstance(safe["path"], str):
        final_segment = safe["path"].rstrip("/").split("/")[-1].casefold()
        if final_segment in PWA_DIAGNOSTIC_ROUTE_SEGMENTS:
            safe["controller"] = final_segment
    back = value.get("back")
    if isinstance(back, str) and back.casefold() in PWA_DIAGNOSTIC_BACK_VALUES:
        safe["back"] = back.casefold()
    back_is_private_route = value.get("back_is_private_route")
    if type(back_is_private_route) is bool:
        safe["back_is_private_route"] = back_is_private_route
    private_customer_route = value.get("private_customer_route")
    if type(private_customer_route) is bool:
        safe["private_customer_route"] = private_customer_route
    return safe


def safe_navigation_target(candidate_url: str, shop_url: str) -> dict[str, object]:
    """Return bounded route metadata without URL origins or query values."""
    if not isinstance(candidate_url, str) or len(candidate_url) > 8192:
        return {"path": "<off-origin>", "query_keys": [], "private_customer_route": False}
    try:
        absolute_url = urljoin(shop_url.rstrip("/") + "/", candidate_url)
        if not same_origin(shop_url, absolute_url):
            return {"path": "<off-origin>", "query_keys": [], "private_customer_route": False}
        shop = urlparse(shop_url)
        candidate = urlparse(absolute_url)
        base_path = shop.path.rstrip("/")
        candidate_path = candidate.path or "/"
        if base_path:
            if candidate_path == base_path:
                candidate_path = "/"
            elif candidate_path.startswith(base_path + "/"):
                candidate_path = candidate_path[len(base_path):]
            else:
                candidate_path = "/<other>"
        query_values = parse_qs(candidate.query, keep_blank_values=True)
        back_values = query_values.get("back", [])
        safe = _safe_navigation_target_metadata(
            {
                "path": candidate_path,
                "query_keys": list(query_values),
                "controller": query_values.get("controller", [""])[-1],
                "back": back_values[-1] if back_values else "",
                "back_is_private_route": any(
                    is_private_customer_back_target(back, shop_url)
                    for back in back_values
                ),
                "private_customer_route": is_private_customer_back_target(
                    absolute_url, shop_url
                ),
            }
        )
        return safe
    except (TypeError, ValueError, IndexError):
        return {"path": "<other>", "query_keys": [], "private_customer_route": False}


def _header_value(headers: object, expected_name: str) -> str | None:
    if not isinstance(headers, dict):
        return None
    for name, value in headers.items():
        if isinstance(name, str) and name.casefold() == expected_name.casefold():
            return value if isinstance(value, str) else None
    return None


def redirect_location_matches_request(
    response_url: object,
    headers: object,
    next_request_url: object,
    shop_url: str,
) -> bool | None:
    """Compare a redirect's Location with the browser's next request without returning either URL."""
    location = _header_value(headers, "location")
    if not isinstance(response_url, str) or not isinstance(location, str) or not location.strip():
        return None
    if not isinstance(next_request_url, str):
        return None
    try:
        destination = urljoin(response_url, location)
        actual = urljoin(shop_url.rstrip("/") + "/", next_request_url)
        if not same_origin(shop_url, destination) or not same_origin(shop_url, actual):
            return False
        expected = urlparse(destination)
        followed = urlparse(actual)
        expected_path = unquote(expected.path or "/", errors="strict")
        followed_path = unquote(followed.path or "/", errors="strict")
        expected_query = sorted(parse_qsl(expected.query, keep_blank_values=True))
        followed_query = sorted(parse_qsl(followed.query, keep_blank_values=True))
        return expected_path == followed_path and expected_query == followed_query
    except (TypeError, UnicodeDecodeError, ValueError):
        return False


def chrome_performance_events(entries: object) -> list[dict[str, object]]:
    """Unwrap Chrome performance-log envelopes into CDP method/params events."""
    if not isinstance(entries, list):
        return []
    events: list[dict[str, object]] = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("method"), str) and isinstance(entry.get("params"), dict):
            events.append({"method": entry["method"], "params": entry["params"]})
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        try:
            decoded = json.loads(message) if isinstance(message, str) else message
            event = decoded.get("message", decoded) if isinstance(decoded, dict) else None
            if not isinstance(event, dict):
                continue
            method = event.get("method")
            params = event.get("params")
            if isinstance(method, str) and isinstance(params, dict):
                events.append({"method": method, "params": params})
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return events


def _navigation_url_matches(candidate_url: object, requested_url: str, shop_url: str) -> bool:
    if not isinstance(candidate_url, str) or not same_origin(shop_url, candidate_url):
        return False
    try:
        requested = urlparse(urljoin(shop_url.rstrip("/") + "/", requested_url))
        candidate = urlparse(candidate_url)
        return candidate.path == requested.path and candidate.query == requested.query
    except (TypeError, ValueError):
        return False


def _safe_response_cache_provenance(response: dict[str, object]) -> dict[str, object]:
    from_service_worker = response.get("fromServiceWorker")
    from_disk_cache = response.get("fromDiskCache")
    from_prefetch_cache = response.get("fromPrefetchCache")
    source = response.get("serviceWorkerResponseSource")
    headers = response.get("headers")
    return {
        "from_service_worker": from_service_worker if type(from_service_worker) is bool else None,
        "from_disk_cache": from_disk_cache if type(from_disk_cache) is bool else None,
        "from_prefetch_cache": from_prefetch_cache if type(from_prefetch_cache) is bool else None,
        "private_cache_policy": (
            response_has_private_cache_policy(headers) if isinstance(headers, dict) else None
        ),
        "revalidation_cache_policy": (
            response_has_revalidation_policy(headers) if isinstance(headers, dict) else None
        ),
        "service_worker_source": (
            source if isinstance(source, str) and source in PWA_DIAGNOSTIC_WORKER_SOURCES else None
        ),
    }


def _safe_http_status(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 100 <= value <= 599 or int(value) != value:
        return None
    return int(value)


def safe_document_navigation_trace(
    events: object,
    requested_url: str,
    shop_url: str,
    main_frame_id: str,
    *,
    sensitive_values: tuple[str, ...] = (),
    expected_final_url: str | None = None,
) -> dict[str, object]:
    """Correlate one main-frame document redirect chain and expose only safe metadata."""
    del sensitive_values  # URLs, query values, headers, and CDP identifiers are never returned.
    trace: dict[str, object] = {
        "observed": False,
        "method": "unknown",
        "initial_target": safe_navigation_target(requested_url, shop_url),
        "navigation_referrer": {"path": "<missing>", "query_keys": []},
        "redirects": [],
        "redirects_truncated": False,
        "final": {
            "status": None,
            "target": {"path": "<other>", "query_keys": []},
            "from_service_worker": None,
            "from_disk_cache": None,
            "from_prefetch_cache": None,
            "private_cache_policy": None,
            "service_worker_source": None,
        },
    }
    if expected_final_url is not None:
        trace["final_route_matches_login"] = None
    if not isinstance(events, (list, tuple)) or not isinstance(main_frame_id, str):
        return trace

    normalized_events = chrome_performance_events(list(events))
    first_index: int | None = None
    request_id: str | None = None
    loader_id: str | None = None
    initial_method = "unknown"
    for index, event in enumerate(normalized_events):
        params = event.get("params")
        request = params.get("request") if isinstance(params, dict) else None
        if (
            event.get("method") != "Network.requestWillBeSent"
            or not isinstance(params, dict)
            or params.get("type") != "Document"
            or params.get("frameId") != main_frame_id
            or not isinstance(request, dict)
            or not _navigation_url_matches(request.get("url"), requested_url, shop_url)
        ):
            continue
        candidate_request_id = params.get("requestId")
        if not isinstance(candidate_request_id, str) or not candidate_request_id:
            continue
        first_index = index
        request_id = candidate_request_id
        candidate_loader_id = params.get("loaderId")
        loader_id = candidate_loader_id if isinstance(candidate_loader_id, str) and candidate_loader_id else None
        method = request.get("method")
        initial_method = method if isinstance(method, str) and method in {"GET", "POST", "HEAD"} else "other"
        referrer = _header_value(request.get("headers"), "referer")
        if referrer:
            trace["navigation_referrer"] = safe_navigation_target(referrer, shop_url)
        break
    if first_index is None or request_id is None:
        return trace

    trace["observed"] = True
    trace["method"] = initial_method
    redirects: list[dict[str, object]] = []
    current_request_url = requested_url
    current_request_served_from_cache: bool | None = None
    final: dict[str, object] | None = None
    for event in normalized_events[first_index:]:
        params = event.get("params")
        if not isinstance(params, dict) or params.get("requestId") != request_id:
            continue
        frame_id = params.get("frameId")
        event_loader_id = params.get("loaderId")
        method = event.get("method")
        if method == "Network.requestServedFromCache":
            # This event has no frameId in the CDP protocol; the pinned requestId is
            # sufficient, and the signal is kept distinct from disk-cache provenance.
            if frame_id is not None and frame_id != main_frame_id:
                continue
            if loader_id is not None and isinstance(event_loader_id, str) and event_loader_id and event_loader_id != loader_id:
                continue
            current_request_served_from_cache = True
            continue
        if method == "Network.requestWillBeSent" and frame_id != main_frame_id:
            continue
        if method != "Network.requestWillBeSent" and frame_id is not None and frame_id != main_frame_id:
            continue
        if loader_id is not None and isinstance(event_loader_id, str) and event_loader_id and event_loader_id != loader_id:
            continue

        if method == "Network.requestWillBeSent":
            request = params.get("request")
            redirect_response = params.get("redirectResponse")
            if isinstance(redirect_response, dict) and isinstance(request, dict):
                redirect_url = redirect_response.get("url", current_request_url)
                raw_location = _header_value(redirect_response.get("headers"), "location")
                try:
                    location_target = (
                        urljoin(redirect_url, raw_location)
                        if isinstance(redirect_url, str) and isinstance(raw_location, str)
                        else None
                    )
                except (TypeError, ValueError):
                    location_target = None
                redirects.append(
                    {
                        "status": _safe_http_status(redirect_response.get("status")),
                        "target": safe_navigation_target(
                            request.get("url", ""), shop_url
                        ),
                        "location_target": (
                            safe_navigation_target(location_target, shop_url)
                            if isinstance(location_target, str)
                            else {"path": "<missing>", "query_keys": []}
                        ),
                        "location_matches_next_request": redirect_location_matches_request(
                            redirect_url,
                            redirect_response.get("headers"),
                            request.get("url"),
                            shop_url,
                        ),
                        "location_matches_expected_login": (
                            same_storefront_route(location_target, expected_final_url, shop_url)
                            if isinstance(location_target, str) and expected_final_url is not None
                            else None
                        ),
                        "request_served_from_cache": current_request_served_from_cache,
                        **_safe_response_cache_provenance(redirect_response),
                    }
                )
                if len(redirects) > PWA_DIAGNOSTIC_MAX_REDIRECTS:
                    trace["redirects_truncated"] = True
                    redirects = redirects[:PWA_DIAGNOSTIC_MAX_REDIRECTS]
                current_request_url = request.get("url") if isinstance(request.get("url"), str) else current_request_url
                current_request_served_from_cache = None
                # A responseReceived event for a redirect is provisional; its redirectResponse
                # counterpart above is the authoritative hop and starts a new request.
                final = None
                if expected_final_url is not None:
                    trace["final_route_matches_login"] = None
            elif isinstance(request, dict) and isinstance(request.get("url"), str):
                current_request_url = request["url"]
                current_request_served_from_cache = None
        elif method == "Network.responseReceived":
            response = params.get("response")
            if not isinstance(response, dict):
                continue
            final = {
                "status": _safe_http_status(response.get("status")),
                "target": safe_navigation_target(
                    response.get("url", current_request_url), shop_url
                ),
                "request_served_from_cache": current_request_served_from_cache,
                **_safe_response_cache_provenance(response),
            }
            if expected_final_url is not None:
                annotate_generated_login_route_match(
                    trace,
                    response.get("url"),
                    expected_final_url,
                    shop_url,
                )

    trace["redirects"] = redirects
    if final is not None:
        trace["final"] = final
    return trace


def _format_safe_target(value: object) -> str:
    target = _safe_navigation_target_metadata(value)
    path = target["path"]
    query_keys = target["query_keys"]
    formatted = path if isinstance(path, str) else "<other>"
    if isinstance(query_keys, list) and query_keys:
        formatted += "?keys=" + ",".join(query_keys)
        formatted += ";query_keys=" + ",".join(query_keys)
    controller = target.get("controller")
    back = target.get("back")
    if isinstance(controller, str):
        formatted += f";controller={controller}"
    if isinstance(back, str):
        formatted += f";back={back}"
    private_customer_route = target.get("private_customer_route")
    if type(private_customer_route) is bool:
        formatted += f";private_customer_route={str(private_customer_route).lower()}"
    return formatted


def _format_navigation_trace(value: object) -> str:
    if not isinstance(value, dict) or value.get("observed") is not True:
        return "unobserved"
    method = value.get("method")
    method = method if isinstance(method, str) and method in {"GET", "POST", "HEAD", "other"} else "unknown"
    formatted = f"{method} {_format_safe_target(value.get('initial_target'))}"
    formatted += f";navigation_referrer={_format_safe_target(value.get('navigation_referrer'))}"
    redirects = value.get("redirects")
    if isinstance(redirects, list):
        for index, redirect in enumerate(redirects[:PWA_DIAGNOSTIC_MAX_REDIRECTS], start=1):
            if not isinstance(redirect, dict):
                continue
            status = redirect.get("status")
            safe_status = status if type(status) is int and 100 <= status <= 599 else "?"
            formatted += f";{safe_status}->{_format_safe_target(redirect.get('target'))}"
            formatted += f";redirect{index}_location_match={_diagnostic_boolean(redirect.get('location_matches_next_request'))}"
            formatted += f";redirect{index}_login_match={_diagnostic_boolean(redirect.get('location_matches_expected_login'))}"
            formatted += f";redirect{index}_service_worker={_diagnostic_boolean(redirect.get('from_service_worker'))}"
            formatted += f";redirect{index}_disk_cache={_diagnostic_boolean(redirect.get('from_disk_cache'))}"
            formatted += f";redirect{index}_prefetch_cache={_diagnostic_boolean(redirect.get('from_prefetch_cache'))}"
            formatted += f";redirect{index}_request_cache={_diagnostic_boolean(redirect.get('request_served_from_cache'))}"
            formatted += f";redirect{index}_private_cache_policy={_diagnostic_boolean(redirect.get('private_cache_policy'))}"
            formatted += f";redirect{index}_revalidation_cache_policy={_diagnostic_boolean(redirect.get('revalidation_cache_policy'))}"
            source = redirect.get("service_worker_source")
            if isinstance(source, str) and source in PWA_DIAGNOSTIC_WORKER_SOURCES:
                formatted += f";redirect{index}_worker_source={source}"
    if value.get("redirects_truncated") is True:
        formatted += ";redirects_truncated=true"
    if "final_route_matches_login" in value:
        route_match = value.get("final_route_matches_login")
        formatted += (
            ";final_route_matches_login="
            + (str(route_match).lower() if type(route_match) is bool else "unknown")
        )
    final = value.get("final")
    if isinstance(final, dict):
        status = final.get("status")
        safe_status = status if type(status) is int and 100 <= status <= 599 else "unavailable"
        final_target = _safe_navigation_target_metadata(final.get("target"))
        formatted += (
            f";final={safe_status}:{final_target.get('path', '<other>')}"
            f";service_worker={_diagnostic_boolean(final.get('from_service_worker'))}"
            f";disk_cache={_diagnostic_boolean(final.get('from_disk_cache'))}"
        )
        if isinstance(final_target.get("query_keys"), list) and final_target["query_keys"]:
            formatted += ";final_query_keys=" + ",".join(final_target["query_keys"])
        if isinstance(final_target.get("controller"), str):
            formatted += f";final_controller={final_target['controller']}"
        if isinstance(final_target.get("back"), str):
            formatted += f";final_back={final_target['back']}"
        formatted += f";request_cache={_diagnostic_boolean(final.get('request_served_from_cache'))}"
        formatted += f";prefetch_cache={_diagnostic_boolean(final.get('from_prefetch_cache'))}"
        formatted += f";private_cache_policy={_diagnostic_boolean(final.get('private_cache_policy'))}"
        source = final.get("service_worker_source")
        if isinstance(source, str) and source in PWA_DIAGNOSTIC_WORKER_SOURCES:
            formatted += f";worker_source={source}"
    return formatted


def _diagnostic_boolean(value: object) -> str:
    return str(value).lower() if type(value) is bool else "unknown"


def navigation_trace_has_cache_hit(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    steps = trace.get("redirects")
    checked_steps = list(steps) if isinstance(steps, list) else []
    final = trace.get("final")
    if isinstance(final, dict):
        checked_steps.append(final)
    return any(
        isinstance(step, dict)
        and (
            step.get("from_disk_cache") is True
            or step.get("from_prefetch_cache") is True
            or step.get("request_served_from_cache") is True
            or step.get("service_worker_source") in {"cache-storage", "http-cache"}
        )
        for step in checked_steps
    )


def validate_logged_out_navigation_trace(
    trace: object,
    *,
    service_worker_expected: bool,
) -> None:
    """Require a login redirect whose service-worker hops use the private network path."""
    if not isinstance(trace, dict) or trace.get("observed") is not True:
        raise AssertionError("logged-out protected account navigation was not observed")
    if trace.get("redirects_truncated") is True:
        raise AssertionError("logged-out protected account redirect chain is incomplete")
    redirects = trace.get("redirects")
    redirects = redirects if isinstance(redirects, list) else []
    if not redirects or not isinstance(redirects[0], dict) or redirects[0].get("status") != 302:
        raise AssertionError("logged-out protected account did not follow the sign-in redirect")
    final = trace.get("final")
    if not isinstance(final, dict) or final.get("status") != 200:
        raise AssertionError("logged-out sign-in destination did not return HTTP 200")
    final_target = _safe_navigation_target_metadata(final.get("target"))
    final_path = final_target.get("path")
    recognized_auth_route = (
        final_target.get("controller") in PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS
        or (
            isinstance(final_path, str)
            and final_path.rstrip("/").split("/")[-1]
            in PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS
        )
    )
    if "final_route_matches_login" in trace:
        route_matches_login = trace.get("final_route_matches_login") is True
    else:
        route_matches_login = recognized_auth_route
    if not route_matches_login:
        raise AssertionError("logged-out redirect did not land on the authentication route")
    worker_steps = [*redirects, final]
    if any(
        not isinstance(step, dict) or step.get("private_cache_policy") is not True
        for step in worker_steps
    ):
        raise AssertionError("logged-out redirect chain lacks a no-store cache policy")
    if navigation_trace_has_cache_hit(trace):
        raise AssertionError("logged-out protected document was served from a browser or service-worker cache")
    if service_worker_expected:
        initial_target = _safe_navigation_target_metadata(trace.get("initial_target"))
        initial_route_is_private = initial_target.get("private_customer_route") is True
        for index, step in enumerate(redirects):
            provenance = step.get("from_service_worker")
            if provenance is True:
                if step.get("service_worker_source") != "network":
                    raise AssertionError("service worker did not use the network for a private document")
                continue
            preceding_redirect = redirects[index - 1] if index > 0 else None
            preceding_target = preceding_redirect.get("target") if isinstance(preceding_redirect, dict) else None
            if (
                provenance is not False
                or not (
                    initial_route_is_private and index == 0
                    or isinstance(preceding_target, dict)
                    and preceding_target.get("back_is_private_route") is True
                )
            ):
                raise AssertionError("native redirect hop did not follow a private back route")
        final_provenance = final.get("from_service_worker")
        if final_provenance is True:
            if final.get("service_worker_source") != "network":
                raise AssertionError("service worker did not use the network for the sign-in page")
        elif (
            final_provenance is not False
            or not (
                isinstance(redirects[-1].get("target"), dict)
                and redirects[-1]["target"].get("back_is_private_route") is True
            )
        ):
            raise AssertionError("native redirect hop did not follow a private back route")
    elif any(step.get("from_service_worker") is not False for step in worker_steps if isinstance(step, dict)):
        raise AssertionError("logged-out navigation provenance did not match network without service worker mode")


def validate_logged_out_empty_order_cart_navigation_trace(
    trace: object,
    set_substage: Callable[[str], None] | None = None,
) -> None:
    """Require the empty checkout route to end at a private cart without cached customer data."""
    def check(name: str) -> None:
        if set_substage is not None:
            set_substage(f"guest_empty_checkout_{name}")

    check("trace_observed")
    if not isinstance(trace, dict) or trace.get("observed") is not True:
        raise AssertionError("logged-out empty checkout navigation was not observed")
    check("trace_complete")
    if trace.get("redirects_truncated") is True:
        raise AssertionError("logged-out empty checkout redirect chain is incomplete")

    check("initial_route")
    initial = _safe_navigation_target_metadata(trace.get("initial_target"))
    if initial.get("controller") != "order":
        raise AssertionError("logged-out empty checkout did not start at the order controller")

    check("redirect_count")
    redirects = trace.get("redirects")
    redirects = redirects if isinstance(redirects, list) else []
    if len(redirects) != 2:
        raise AssertionError("logged-out empty checkout did not follow its canonical cart redirects")
    canonical_order, empty_cart = redirects
    check("canonical_status")
    if not isinstance(canonical_order, dict) or canonical_order.get("status") != 302:
        raise AssertionError("canonical empty-order redirect did not return HTTP 302")
    check("canonical_target")
    canonical_target = _safe_navigation_target_metadata(canonical_order.get("target"))
    if (
        canonical_target.get("controller") != "order"
        or canonical_order.get("location_matches_next_request") is not True
    ):
        raise AssertionError("canonical empty-order redirect changed the requested route")
    if (
        canonical_order.get("private_cache_policy") is not True
        and canonical_order.get("revalidation_cache_policy") is not True
    ):
        raise AssertionError("canonical empty-order redirect lacks a no-store or no-cache policy")

    check("cart_redirect_status")
    if not isinstance(empty_cart, dict) or empty_cart.get("status") != 302:
        raise AssertionError("empty checkout did not redirect to the cart")
    cart_target = _safe_navigation_target_metadata(empty_cart.get("target"))
    if (
        cart_target.get("controller") != "cart"
        or empty_cart.get("location_matches_next_request") is not True
        or empty_cart.get("private_cache_policy") is not True
    ):
        raise AssertionError("empty checkout cart redirect is not a verified no-store cart response")

    check("final_status")
    final = trace.get("final")
    if not isinstance(final, dict) or final.get("status") != 200:
        raise AssertionError("logged-out empty cart did not return HTTP 200")
    final_target = _safe_navigation_target_metadata(final.get("target"))
    if final_target.get("controller") != "cart" or final.get("private_cache_policy") is not True:
        raise AssertionError("logged-out empty checkout did not finish on a no-store cart page")
    check("cache_provenance")
    for step in [*redirects, final]:
        if not isinstance(step, dict):
            raise AssertionError("logged-out empty checkout cache provenance is incomplete")
        if (
            type(step.get("from_service_worker")) is not bool
            or type(step.get("from_disk_cache")) is not bool
            or type(step.get("from_prefetch_cache")) is not bool
        ):
            raise AssertionError("logged-out empty checkout cache provenance is unavailable")
        if (
            step.get("from_disk_cache") is True
            or step.get("from_prefetch_cache") is True
            or step.get("request_served_from_cache") is True
        ):
            raise AssertionError("logged-out empty checkout was served from a browser cache")
        if (
            step.get("from_service_worker") is True
            and step.get("service_worker_source") != "network"
        ):
            raise AssertionError("service worker served cached content for logged-out empty checkout")
    check("cache_hits")
    if navigation_trace_has_cache_hit(trace):
        raise AssertionError("logged-out empty checkout used a browser or service-worker cache")


def validate_logout_navigation_trace(trace: object) -> None:
    """Require the clicked sign-out navigation itself to finish at a safe login page."""
    if not isinstance(trace, dict) or trace.get("observed") is not True:
        raise AssertionError("customer logout navigation was not observed")
    if trace.get("redirects_truncated") is True:
        raise AssertionError("customer logout redirect chain is incomplete")
    redirects = trace.get("redirects")
    redirects = redirects if isinstance(redirects, list) else []
    if not any(
        isinstance(step, dict) and step.get("status") in {301, 302, 303, 307, 308}
        for step in redirects
    ):
        raise AssertionError("customer logout did not follow a sign-in redirect")
    redirect_steps = [
        step for step in redirects
        if isinstance(step, dict) and step.get("status") in {301, 302, 303, 307, 308}
    ]
    if any(step.get("location_matches_next_request") is not True for step in redirect_steps):
        raise AssertionError("customer logout Location did not match the browser's next request")
    if (
        redirect_steps[-1].get("location_matches_expected_login") is not None
        and redirect_steps[-1].get("location_matches_expected_login") is not True
    ):
        raise AssertionError("customer logout Location did not target the generated sign-in route")
    final = trace.get("final")
    if not isinstance(final, dict) or final.get("status") != 200:
        raise AssertionError("customer logout destination did not return HTTP 200")
    if redirect_steps[0].get("from_service_worker") is not False:
        raise AssertionError("customer logout action response was handled by the service worker")
    if any(
        step.get("private_cache_policy") is not True
        for step in [*redirect_steps, final]
        if isinstance(step, dict)
    ):
        raise AssertionError("customer logout redirect chain lacks a no-store cache policy")
    final_target = _safe_navigation_target_metadata(final.get("target"))
    final_path = final_target.get("path")
    recognized_auth_route = (
        final_target.get("controller") in PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS
        or (
            isinstance(final_path, str)
            and final_path.rstrip("/").split("/")[-1] in PWA_DIAGNOSTIC_AUTH_ROUTE_SEGMENTS
        )
    )
    if "final_route_matches_login" in trace:
        route_matches_login = trace.get("final_route_matches_login") is True
    else:
        route_matches_login = recognized_auth_route
    if not route_matches_login:
        raise AssertionError("customer logout did not land on the authentication route")
    if final.get("private_cache_policy") is not True:
        raise AssertionError("customer logout destination lacks a no-store cache policy")
    if navigation_trace_has_cache_hit(trace):
        raise AssertionError("customer logout destination was served from a browser or service-worker cache")
    for step in [*redirect_steps[1:], final]:
        if type(step.get("from_service_worker")) is not bool:
            raise AssertionError("customer logout redirect provenance is unavailable")
        if step.get("from_service_worker") is True and step.get("service_worker_source") != "network":
            raise AssertionError("customer logout service worker did not use the network response")


def _format_selected_signout(value: object) -> str:
    if not isinstance(value, dict):
        return "unavailable"
    containers = {"account_menu", "my_account"}
    container = value.get("container")
    container = container if isinstance(container, str) and container in containers else "other"
    element_id = value.get("element_id")
    if not isinstance(element_id, str) or element_id not in {"signout_link", "none"}:
        element_id = "other"
    formatted = f"{container}#{element_id}"
    target = value.get("target")
    if isinstance(target, dict):
        formatted += f";target={_format_safe_target(target)}"
    return formatted


def format_logout_wait_diagnostic(metadata: dict[str, object]) -> str:
    """Format only bounded, allowlisted logout diagnostics for CI annotations."""
    route_class = metadata.get("final_route_class")
    if not isinstance(route_class, str) or route_class not in PWA_LOGOUT_ROUTE_CLASSES:
        route_class = "other"
    status = metadata.get("final_document_status")
    safe_status = status if type(status) is int and 100 <= status <= 599 else "unavailable"
    ready_state = metadata.get("ready_state")
    if not isinstance(ready_state, str) or ready_state not in {"loading", "interactive", "complete"}:
        ready_state = "unknown"

    def count_label(value: object) -> str:
        bounded = _bounded_logout_element_count(value)
        return str(bounded) if bounded is not None else "unavailable"

    def boolean_label(value: object) -> str:
        return str(value).lower() if type(value) is bool else "unknown"

    diagnostic = (
        f"; final_route_class={route_class}"
        f"; final_document_status={safe_status}"
        f"; login_form_count={count_label(metadata.get('login_form_count'))}"
        f"; login_form_visible={boolean_label(metadata.get('login_form_visible'))}"
        f"; email_field_count={count_label(metadata.get('email_field_count'))}"
        f"; email_field_visible={boolean_label(metadata.get('email_field_visible'))}"
        f"; ready_state={ready_state}"
    )
    selected = metadata.get("selected_signout")
    if isinstance(selected, dict):
        diagnostic += f"; selected_signout={_format_selected_signout(selected)}"
    for key in (
        "logout_trace",
        "protected_pwa_trace",
        "protected_network_trace",
        "post_restore_trace",
    ):
        if key in metadata:
            diagnostic += f"; {key}={_format_navigation_trace(metadata.get(key))}"
    for key in (
        "logout_identity_exposed",
        "logout_cache_empty",
        "controlled_identity_exposed",
        "controlled_cache_empty",
        "network_identity_exposed",
        "network_cache_empty",
        "post_restore_identity_exposed",
        "service_worker_bypass_reset",
        "service_worker_restored",
    ):
        if key in metadata:
            diagnostic += f"; {key}={_diagnostic_boolean(metadata.get(key))}"
    return diagnostic


def wait_for_logout_login_form(driver: webdriver.Chrome, shop_url: str):
    try:
        return wait_visible(driver, "#login-form input[name='email']")
    except TimeoutException as error:
        try:
            error.pwa_logout_diagnostics = safe_logout_wait_diagnostics(driver, shop_url)
        except Exception:
            # Diagnostic capture must never replace the original login-form timeout.
            pass
        raise


def response_has_private_cache_policy(headers: dict[str, object]) -> bool:
    cache_control = next(
        (value for key, value in headers.items() if key.lower() == "cache-control"),
        "",
    )
    if not isinstance(cache_control, str):
        return False
    directives = {part.split("=", 1)[0].strip().lower() for part in cache_control.split(",")}
    return "no-store" in directives


def response_has_revalidation_policy(headers: dict[str, object]) -> bool:
    """Recognize no-cache redirects which must be revalidated before reuse."""
    cache_control = _header_value(headers, "cache-control") or ""
    pragma = _header_value(headers, "pragma") or ""
    directives = {part.split("=", 1)[0].strip().lower() for part in cache_control.split(",")}
    pragma_directives = {part.split("=", 1)[0].strip().lower() for part in pragma.split(",")}
    return "no-cache" in directives or "no-cache" in pragma_directives


def exposes_test_identity(body_text: str, first_name: str, last_name: str, email: str) -> bool:
    for name in (first_name, last_name):
        if name and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", body_text, re.IGNORECASE):
            return True
    return bool(email and email.casefold() in body_text.casefold())


def assert_empty_cache_storage(driver: webdriver.Chrome, stage: str) -> None:
    snapshot = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        (async () => {
          if (!('caches' in window)) return {available: false, caches: 0, entries: 0};
          const names = await caches.keys();
          let entries = 0;
          for (const name of names) entries += (await (await caches.open(name)).keys()).length;
          return {available: true, caches: names.length, entries};
        })().then(done).catch(() => done({available: false, caches: -1, entries: -1}));
        """
    )
    if not isinstance(snapshot, dict) or snapshot.get("available") is not True:
        raise AssertionError(f"CacheStorage was unavailable at {stage}")
    if snapshot.get("caches") != 0 or snapshot.get("entries") != 0:
        raise AssertionError(f"CacheStorage retained entries at {stage}")


def wait_for_empty_cart(driver: webdriver.Chrome) -> None:
    def empty(browser: webdriver.Chrome) -> bool:
        return (
            not browser.find_elements(By.CSS_SELECTOR, ".cart__item")
            and bool(browser.find_elements(By.CSS_SELECTOR, ".cart__empty"))
        )

    WebDriverWait(driver, 30, poll_frequency=0.2).until(
        empty,
        message="logged-out empty checkout did not land on an empty cart",
    )


def wait_visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def authenticated_account_url(driver: webdriver.Chrome, base_url: str) -> str:
    button = wait_visible(driver, "#userMenuButton")
    if button.get_attribute("aria-expanded") != "true":
        button.click()
    links = WebDriverWait(driver, 20).until(
        lambda browser: [
            link
            for link in browser.find_elements(
                By.CSS_SELECTOR, 'div.dropdown-menu[aria-labelledby="userMenuButton"] a[href]'
            )
            if link.is_displayed() and link.get_attribute("href")
        ]
    )
    account_url = urljoin(driver.current_url, links[0].get_attribute("href"))
    if not same_origin(base_url, account_url):
        raise AssertionError("generated authenticated account link left the isolated shop origin")
    return account_url


def verify_manifest(driver: webdriver.Chrome, base_url: str) -> dict[str, object]:
    snapshot = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        (async () => {
          const link = document.querySelector('link[rel="manifest"]');
          if (!link?.href) throw new Error('manifest link missing');
          const response = await fetch(link.href, {cache: 'no-store', credentials: 'same-origin'});
          if (!response.ok) throw new Error('manifest response failed');
          const manifest = await response.json();
          const icons = [];
          for (const icon of manifest.icons || []) {
            const iconResponse = await fetch(icon.src, {cache: 'no-store', credentials: 'same-origin'});
            icons.push({sizes: icon.sizes || '', purpose: icon.purpose || 'any', ok: iconResponse.ok});
          }
          return {
            secureContext: window.isSecureContext,
            linkHref: link.href,
            manifest,
            icons,
            htmlLang: document.documentElement.lang || '',
          };
        })().then(done).catch(error => done({error: String(error)}));
        """
    )
    if not isinstance(snapshot, dict) or snapshot.get("error"):
        raise AssertionError("storefront PWA manifest could not be read")
    secure_context = snapshot.get("secureContext") is True
    issues = manifest_installability_issues(
        snapshot.get("manifest") if isinstance(snapshot.get("manifest"), dict) else {},
        base_url,
        secure_context,
    )
    if issues:
        raise AssertionError("PWA installability prerequisites failed: " + "; ".join(issues))
    icons = snapshot.get("icons")
    if not isinstance(icons, list) or not icons or any(
        not isinstance(icon, dict) or icon.get("ok") is not True for icon in icons
    ):
        raise AssertionError("one or more declared PWA icons could not be fetched")
    snapshot["secureContext"] = secure_context
    return snapshot


def _safe_service_worker_choice(value: object, allowed: set[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "unknown"


def safe_service_worker_registration_metadata(value: object) -> dict[str, object]:
    """Keep registration diagnostics to fixed, bounded fields and allow-listed values."""
    source = value if isinstance(value, dict) else {}
    boolean_keys = (
        "service_worker_supported",
        "observer_installed",
        "registration_attempted",
        "ready_resolved",
        "registration_found",
        "controller_present",
        "controller_change_observed",
        "route_matches_expected",
        "scope_matches_expected",
        "script_origin_matches_expected",
        "script_path_matches_expected",
        "worker_from_service_worker",
        "worker_from_disk_cache",
        "worker_from_prefetch_cache",
    )
    safe: dict[str, object] = {
        "phase": _safe_service_worker_choice(
            source.get("phase"), PWA_SERVICE_WORKER_DIAGNOSTIC_PHASES
        ),
        "category": _safe_service_worker_choice(
            source.get("category"), PWA_SERVICE_WORKER_DIAGNOSTIC_CATEGORIES
        ),
        "error_name": _safe_service_worker_choice(
            source.get("error_name"), PWA_SERVICE_WORKER_ERROR_NAMES
        ),
        "registration_error_name": _safe_service_worker_choice(
            source.get("registration_error_name"), PWA_SERVICE_WORKER_ERROR_NAMES
        ),
        "registration_outcome": _safe_service_worker_choice(
            source.get("registration_outcome"), PWA_SERVICE_WORKER_REGISTRATION_OUTCOMES
        ),
        "active_state": _safe_service_worker_choice(
            source.get("active_state"), PWA_SERVICE_WORKER_STATES
        ),
        "worker_response_status": _safe_http_status(source.get("worker_response_status")),
        "worker_response_mime": _safe_service_worker_choice(
            source.get("worker_response_mime"), PWA_SERVICE_WORKER_RESPONSE_MIME_TYPES
        ),
        "worker_source": _safe_service_worker_choice(
            source.get("worker_source"), PWA_DIAGNOSTIC_WORKER_SOURCES
        ),
    }
    for key in boolean_keys:
        flag = source.get(key)
        safe[key] = flag if type(flag) is bool else None

    return safe


def format_service_worker_registration_diagnostic(value: object) -> str:
    """Format the registration snapshot without exposing browser-controlled strings."""
    safe = safe_service_worker_registration_metadata(value)
    status = safe.get("worker_response_status")
    status_text = str(status) if isinstance(status, int) else "unavailable"
    parts = [
        f"phase={safe['phase']}",
        f"category={safe['category']}",
        f"error_name={safe['error_name']}",
        f"registration_error_name={safe['registration_error_name']}",
    ]
    for key in (
        "service_worker_supported",
        "observer_installed",
        "registration_attempted",
        "registration_outcome",
        "ready_resolved",
        "registration_found",
        "active_state",
        "controller_present",
        "controller_change_observed",
        "route_matches_expected",
        "scope_matches_expected",
        "script_origin_matches_expected",
        "script_path_matches_expected",
    ):
        value = safe.get(key)
        parts.append(
            f"{key}={_diagnostic_boolean(value) if type(value) is bool else value or 'unknown'}"
        )
    parts.extend(
        (
            f"worker_response_status={status_text}",
            f"worker_response_mime={safe['worker_response_mime']}",
            f"worker_from_service_worker={_diagnostic_boolean(safe['worker_from_service_worker'])}",
            f"worker_from_disk_cache={_diagnostic_boolean(safe['worker_from_disk_cache'])}",
            f"worker_from_prefetch_cache={_diagnostic_boolean(safe['worker_from_prefetch_cache'])}",
            f"worker_source={safe['worker_source']}",
        )
    )

    return "; " + "; ".join(parts)


def _matches_expected_worker_script(value: object, shop_url: str, expected_worker_path: str) -> bool:
    if not isinstance(value, str) or not same_origin(shop_url, value):
        return False
    try:
        return urlparse(value).path == expected_worker_path
    except (TypeError, ValueError):
        return False


def service_worker_response_metadata(
    entries: object,
    shop_url: str,
    expected_worker_path: str,
) -> dict[str, object]:
    """Extract only response status, MIME category, and cache provenance for the worker script."""
    metadata: dict[str, object] = {
        "worker_response_status": None,
        "worker_response_mime": "unknown",
        "worker_from_service_worker": None,
        "worker_from_disk_cache": None,
        "worker_from_prefetch_cache": None,
        "worker_source": "unknown",
    }
    request_ids: set[str] = set()
    for event in chrome_performance_events(entries):
        params = event.get("params")
        if not isinstance(params, dict):
            continue
        method = event.get("method")
        if method == "Network.requestWillBeSent":
            request = params.get("request")
            request_id = params.get("requestId")
            if (
                isinstance(request, dict)
                and isinstance(request_id, str)
                and _matches_expected_worker_script(
                    request.get("url"), shop_url, expected_worker_path
                )
            ):
                request_ids.add(request_id)
        if method != "Network.responseReceived" or params.get("requestId") not in request_ids:
            continue
        response = params.get("response")
        if not isinstance(response, dict) or not _matches_expected_worker_script(
            response.get("url"), shop_url, expected_worker_path
        ):
            continue
        mime_type = response.get("mimeType")
        metadata["worker_response_status"] = _safe_http_status(response.get("status"))
        metadata["worker_response_mime"] = _safe_service_worker_choice(
            mime_type, PWA_SERVICE_WORKER_RESPONSE_MIME_TYPES
        )
        for source_key, target_key in (
            ("fromServiceWorker", "worker_from_service_worker"),
            ("fromDiskCache", "worker_from_disk_cache"),
            ("fromPrefetchCache", "worker_from_prefetch_cache"),
        ):
            flag = response.get(source_key)
            metadata[target_key] = flag if type(flag) is bool else None
        worker_source = response.get("serviceWorkerResponseSource")
        if isinstance(worker_source, str) and worker_source in PWA_DIAGNOSTIC_WORKER_SOURCES:
            metadata["worker_source"] = worker_source
        elif metadata["worker_from_disk_cache"] is True:
            metadata["worker_source"] = "http-cache"
        elif metadata["worker_from_service_worker"] is True:
            metadata["worker_source"] = "cache-storage"
        elif all(
            metadata[key] is False
            for key in (
                "worker_from_service_worker",
                "worker_from_disk_cache",
                "worker_from_prefetch_cache",
            )
        ):
            metadata["worker_source"] = "network"

    return metadata


def service_worker_registration_observer_script() -> str:
    """Install a transparent test-only observer for the native register() promise."""
    return """
    (() => {
      const safeErrorName = error => {
        const names = new Set([
          'AbortError', 'Error', 'InvalidStateError', 'NetworkError',
          'NotAllowedError', 'SecurityError', 'TimeoutError', 'TypeError'
        ]);
        return names.has(error?.name) ? error.name : 'unknown';
      };
      const state = {
        observer_installed: false,
        registration_attempted: false,
        registration_outcome: 'not_attempted',
        registration_error_name: 'unknown'
      };
      window.__pwaRegistrationObservation = state;
      try {
        const serviceWorker = navigator.serviceWorker;
        if (!serviceWorker || typeof serviceWorker.register !== 'function') return;
        const originalRegister = serviceWorker.register;
        serviceWorker.register = function (...args) {
          state.registration_attempted = true;
          state.registration_outcome = 'pending';
          let promise;
          try {
            promise = originalRegister.apply(this, args);
          } catch (error) {
            state.registration_outcome = 'rejected';
            state.registration_error_name = safeErrorName(error);
            throw error;
          }
          Promise.resolve(promise).then(
            () => { state.registration_outcome = 'resolved'; },
            error => {
              state.registration_outcome = 'rejected';
              state.registration_error_name = safeErrorName(error);
            }
          );
          return promise;
        };
        state.observer_installed = serviceWorker.register !== originalRegister;
      } catch (_error) {
        state.observer_installed = false;
      }
    })();
    """


def install_service_worker_registration_observer(driver: webdriver.Chrome) -> bool:
    """Install test-only registration diagnostics before the storefront document loads."""
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": service_worker_registration_observer_script()},
        )
        installed = True
    except Exception:
        installed = False
    try:
        setattr(driver, "_pwa_registration_observer_installed", installed)
    except Exception:
        pass

    return installed


def service_worker_registration_wait_script() -> str:
    """Await ready and retain the existing 12-second controller wait with safe status fields."""
    return """
    const expectedOrigin = arguments[0];
    const expectedScope = arguments[1];
    const expectedWorkerPath = arguments[2];
    const expectedRoute = arguments[3];
    const done = arguments[arguments.length - 1];
    const allowedErrorNames = new Set([
      'AbortError', 'Error', 'InvalidStateError', 'NetworkError',
      'NotAllowedError', 'SecurityError', 'TimeoutError', 'TypeError'
    ]);
    const safeErrorName = error => allowedErrorNames.has(error?.name) ? error.name : 'unknown';
    const diagnostic = {
      phase: 'api_check',
      category: 'none',
      error_name: 'unknown',
      registration_error_name: 'unknown',
      service_worker_supported: 'serviceWorker' in navigator,
      observer_installed: false,
      registration_attempted: false,
      registration_outcome: 'not_attempted',
      ready_resolved: false,
      registration_found: false,
      active_state: 'none',
      controller_present: false,
      controller_change_observed: false,
      route_matches_expected: false,
      scope_matches_expected: false,
      script_origin_matches_expected: false,
      script_path_matches_expected: false
    };
    let registration = null;
    let serviceWorker = null;
    let controllerChangeObserved = false;
    let controllerChangeListener = null;
    let controllerChangePromise = null;
    let resolveControllerChange = null;
    const registrationObservation = window.__pwaRegistrationObservation;

    const timedError = phase => {
      const error = new Error();
      error.name = 'TimeoutError';
      error.phase = phase;
      return error;
    };
    const waitForControllerWithinDeadline = async promise => {
      const controllerDeadline = Date.now() + 12000;
      const remaining = Math.max(0, controllerDeadline - Date.now());
      let timerId = 0;
      const timeout = new Promise((resolve, reject) => {
        timerId = setTimeout(() => reject(timedError('controller_wait')), remaining);
      });
      try {
        return await Promise.race([Promise.resolve(promise), timeout]);
      } finally {
        clearTimeout(timerId);
      }
    };
    const finish = () => {
      const observer = registrationObservation && typeof registrationObservation === 'object'
        ? registrationObservation
        : {};
      diagnostic.observer_installed = observer.observer_installed === true;
      diagnostic.registration_attempted = observer.registration_attempted === true;
      const outcome = observer.registration_outcome;
      diagnostic.registration_outcome = ['not_attempted', 'pending', 'resolved', 'rejected'].includes(outcome)
        ? outcome
        : 'unknown';
      const registrationErrorName = observer.registration_error_name;
      diagnostic.registration_error_name = allowedErrorNames.has(registrationErrorName)
        ? registrationErrorName
        : 'unknown';
      diagnostic.controller_change_observed = controllerChangeObserved;
      if (registration) {
        diagnostic.registration_found = true;
        diagnostic.scope_matches_expected = registration.scope === expectedScope;
        const active = registration.active;
        const activeState = active?.state;
        diagnostic.active_state = ['installing', 'installed', 'activating', 'activated', 'redundant'].includes(activeState)
          ? activeState
          : 'none';
      }
      const controller = serviceWorker?.controller;
      diagnostic.controller_present = Boolean(controller);
      if (controller && typeof controller.scriptURL === 'string') {
        try {
          const script = new URL(controller.scriptURL, location.href);
          diagnostic.script_origin_matches_expected = script.origin === expectedOrigin;
          diagnostic.script_path_matches_expected = script.pathname === expectedWorkerPath;
        } catch (_error) {
          diagnostic.script_origin_matches_expected = false;
          diagnostic.script_path_matches_expected = false;
        }
      }
      try {
        const currentRoute = new URL(location.href);
        const expected = new URL(expectedRoute, location.href);
        diagnostic.route_matches_expected = currentRoute.origin === expected.origin
          && currentRoute.pathname === expected.pathname
          && currentRoute.search === expected.search;
      } catch (_error) {
        diagnostic.route_matches_expected = false;
      }

      return diagnostic;
    };

    (async () => {
      if (!diagnostic.service_worker_supported) {
        diagnostic.category = 'api_unavailable';
        return;
      }
      serviceWorker = navigator.serviceWorker;
      controllerChangeListener = () => {
        controllerChangeObserved = true;
        if (resolveControllerChange) resolveControllerChange();
      };
      controllerChangePromise = new Promise(resolve => { resolveControllerChange = resolve; });
      serviceWorker.addEventListener('controllerchange', controllerChangeListener);
      diagnostic.phase = 'ready_wait';
      try {
        registration = await serviceWorker.ready;
      } catch (error) {
        diagnostic.phase = 'ready_wait';
        diagnostic.category = 'ready_rejected';
        diagnostic.error_name = safeErrorName(error);
        return;
      }
      diagnostic.ready_resolved = true;
      diagnostic.registration_found = Boolean(registration);
      diagnostic.phase = 'active_check';
      if (!registration?.active) {
        diagnostic.category = 'active_missing';
        return;
      }
      diagnostic.active_state = ['installing', 'installed', 'activating', 'activated', 'redundant'].includes(registration.active.state)
        ? registration.active.state
        : 'none';
      diagnostic.scope_matches_expected = registration.scope === expectedScope;

      // Observe changes before rechecking controller to avoid missing a change in between.
      if (!serviceWorker.controller) {
        diagnostic.phase = 'controller_wait';
        try {
          // A change observed while awaiting `ready` can precede the missing-controller
          // state, so wait for a subsequent change when the ready-time state is still empty.
          if (controllerChangeObserved) {
            controllerChangePromise = new Promise(resolve => { resolveControllerChange = resolve; });
          }
          await waitForControllerWithinDeadline(controllerChangePromise);
        } catch (error) {
          diagnostic.category = error?.phase === 'controller_wait'
            ? 'controller_timeout'
            : 'controller_missing';
          diagnostic.error_name = safeErrorName(error);
          return;
        }
      }
      if (!serviceWorker.controller) {
        diagnostic.phase = 'controller_wait';
        diagnostic.category = 'controller_missing';
        return;
      }
      diagnostic.phase = 'complete';
    })().catch(error => {
      diagnostic.category = 'ready_rejected';
      diagnostic.error_name = safeErrorName(error);
    }).finally(() => {
      if (serviceWorker && controllerChangeListener) {
        serviceWorker.removeEventListener('controllerchange', controllerChangeListener);
      }
      try {
        done(finish());
      } catch (_error) {
        done({phase: 'webdriver_script', category: 'invalid_result', error_name: 'unknown'});
      }
    });
    """


def _expected_service_worker_paths(shop_url: str) -> tuple[str, str, str]:
    parsed = urlparse(shop_url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    base_path = parsed.path.rstrip("/")
    expected_scope_path = base_path + "/"
    expected_scope = urljoin(shop_url.rstrip("/") + "/", expected_scope_path)
    expected_worker_path = (base_path or "") + "/sw.js"

    return origin, expected_scope, expected_worker_path


def wait_for_service_worker(
    driver: webdriver.Chrome,
    shop_url: str,
    expected_route_url: str,
) -> dict[str, object]:
    """Wait for the active worker and controller while retaining only safe diagnostics."""
    expected_origin, expected_scope, expected_worker_path = _expected_service_worker_paths(shop_url)
    raw_metadata: dict[str, object]
    try:
        result = driver.execute_async_script(
            service_worker_registration_wait_script(),
            expected_origin,
            expected_scope,
            expected_worker_path,
            expected_route_url,
        )
        raw_metadata = result if isinstance(result, dict) else {
            "phase": "webdriver_script",
            "category": "invalid_result",
            "error_name": "unknown",
        }
    except Exception as error:
        error_name = type(error).__name__
        category = (
            "webdriver_timeout"
            if error_name in {"TimeoutException", "ScriptTimeoutException"}
            else "webdriver_error"
        )
        raw_metadata = {
            "phase": "webdriver_script",
            "category": category,
            "error_name": error_name,
        }

    raw_metadata["observer_installed"] = getattr(
        driver, "_pwa_registration_observer_installed", False
    ) is True and raw_metadata.get("observer_installed") is True
    try:
        current_url = driver.current_url
    except Exception:
        current_url = None
    raw_metadata["route_matches_expected"] = (
        same_storefront_route(current_url, expected_route_url, shop_url)
        if isinstance(current_url, str)
        else False
    )
    try:
        performance_entries = driver.get_log("performance")
    except Exception:
        performance_entries = []
    raw_metadata.update(
        service_worker_response_metadata(
            performance_entries,
            shop_url,
            expected_worker_path,
        )
    )
    metadata = safe_service_worker_registration_metadata(raw_metadata)
    if metadata["category"] != "none":
        raise PwaDiagnosticAssertionError(
            "service worker did not become active and control the page",
            "service_worker_registration",
            metadata,
        )

    return metadata


def require_service_worker_registration_match(
    metadata: dict[str, object],
    field: str,
    category: str,
    message: str,
) -> None:
    if metadata.get(field) is True:
        return
    failed_metadata = dict(metadata)
    failed_metadata["phase"] = "validation"
    failed_metadata["category"] = category
    raise PwaDiagnosticAssertionError(
        message,
        "service_worker_registration",
        safe_service_worker_registration_metadata(failed_metadata),
    )


def current_main_frame_id(driver: webdriver.Chrome) -> str | None:
    try:
        frame_tree = driver.execute_cdp_cmd("Page.getFrameTree", {}).get("frameTree", {})
        frame = frame_tree.get("frame", {}) if isinstance(frame_tree, dict) else {}
        frame_id = frame.get("id") if isinstance(frame, dict) else None
        return frame_id if isinstance(frame_id, str) and frame_id else None
    except Exception:
        return None


def matching_document_responses(
    driver: webdriver.Chrome,
    requested_url: str,
    shop_url: str,
    main_frame_id: str,
    performance_entries: object | None = None,
) -> list[dict[str, object]] | None:
    if performance_entries is None:
        try:
            entries = driver.get_log("performance")
        except Exception:
            return None
    else:
        entries = performance_entries
    requested = urlparse(requested_url)
    requested_query = parse_qs(requested.query, keep_blank_values=True)
    responses: list[dict[str, object]] = []
    for event in chrome_performance_events(entries):
        try:
            method = event.get("method")
            params = event.get("params", {})
            if params.get("frameId") != main_frame_id:
                continue
            if params.get("type") != "Document":
                continue
            response = None
            if method == "Network.responseReceived":
                response = params.get("response")
            elif method == "Network.requestWillBeSent":
                response = params.get("redirectResponse")
            if not isinstance(response, dict):
                continue
            response_url = response.get("url")
            if not isinstance(response_url, str) or not same_origin(shop_url, response_url):
                continue
            candidate = urlparse(response_url)
            if candidate.path != requested.path:
                continue
            candidate_query = parse_qs(candidate.query, keep_blank_values=True)
            if any(candidate_query.get(key) != values for key, values in requested_query.items()):
                continue
            responses.append(response)
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return responses


def assert_private_document_cache_headers(
    driver: webdriver.Chrome,
    requested_url: str,
    shop_url: str,
    route_label: str,
    *,
    main_frame_id: str,
    performance_entries: object | None = None,
    trace_main_frame_id: str | None = None,
    navigation_trace_url: str | None = None,
    expected_final_url: str | None = None,
) -> dict[str, object]:
    if performance_entries is None:
        try:
            performance_entries = driver.get_log("performance")
        except Exception:
            performance_entries = None
    responses = matching_document_responses(
        driver,
        requested_url,
        shop_url,
        main_frame_id,
        performance_entries=performance_entries,
    )
    if not responses:
        message = f"UNVERIFIED: document cache headers could not be observed for {route_label}."
        print(message, file=sys.stderr)
        raise PwaDiagnosticAssertionError(
            message,
            "document_response_missing",
            {"response_count": 0},
        )

    response = responses[-1]
    raw_headers = response.get("headers")
    headers = raw_headers if isinstance(raw_headers, dict) else {}
    cache_control = next(
        (value for key, value in headers.items() if isinstance(key, str) and key.lower() == "cache-control"),
        "",
    )
    pragma = next(
        (value for key, value in headers.items() if isinstance(key, str) and key.lower() == "pragma"),
        "",
    )
    expires = next(
        (value for key, value in headers.items() if isinstance(key, str) and key.lower() == "expires"),
        "",
    )
    observed = {
        "status": response.get("status"),
        "cache_control": cache_control if isinstance(cache_control, str) else "",
        "pragma_present": isinstance(pragma, str) and bool(pragma.strip()),
        "expires_present": isinstance(expires, str) and bool(expires.strip()),
        "from_disk_cache": (
            response.get("fromDiskCache") if type(response.get("fromDiskCache")) is bool else None
        ),
        "from_service_worker": (
            response.get("fromServiceWorker")
            if type(response.get("fromServiceWorker")) is bool
            else None
        ),
        "service_worker_source": (
            response.get("serviceWorkerResponseSource")
            if isinstance(response.get("serviceWorkerResponseSource"), str)
            and response.get("serviceWorkerResponseSource") in PWA_DIAGNOSTIC_WORKER_SOURCES
            else None
        ),
    }
    if isinstance(trace_main_frame_id, str):
        observed["navigation_trace"] = safe_document_navigation_trace(
            chrome_performance_events(performance_entries),
            navigation_trace_url if isinstance(navigation_trace_url, str) else requested_url,
            shop_url,
            trace_main_frame_id,
            expected_final_url=expected_final_url,
        )
    if not response_has_private_cache_policy(headers):
        directives = sorted({
            part.split("=", 1)[0].strip().lower()
            for part in observed["cache_control"].split(",")
            if part.strip()
        })
        safe_directives = [
            directive if re.fullmatch(r"[a-z0-9-]{1,32}", directive) else "other"
            for directive in directives
        ][:8]
        status = observed["status"]
        safe_status = int(status) if isinstance(status, (int, float)) and 100 <= status <= 599 else None
        safe_metadata = {
            "response_count": min(len(responses), MAX_PWA_DIAGNOSTIC_RESPONSE_COUNT),
            "status": safe_status,
            "cache_control_directives": safe_directives,
            "pragma_present": observed["pragma_present"],
            "expires_present": observed["expires_present"],
            "from_disk_cache": observed["from_disk_cache"],
            "from_service_worker": observed["from_service_worker"],
        }
        if isinstance(observed.get("navigation_trace"), dict):
            safe_metadata["navigation_trace"] = observed["navigation_trace"]
        directive_summary = ",".join(safe_directives) or "missing"
        message = (
            f"FAIL: {route_label} response lacks Cache-Control no-store semantics "
            f"(observed directives={directive_summary}, pragma={observed['pragma_present']}, "
            f"expires={observed['expires_present']})."
        )
        print(message, file=sys.stderr)
        raise PwaDiagnosticAssertionError(message, "cache_policy_missing", safe_metadata)
    print(f"PASS: {route_label} response uses Cache-Control no-store.")
    return observed


def navigate_private_document(
    driver: webdriver.Chrome,
    requested_url: str,
    shop_url: str,
    route_label: str,
    set_substage: Callable[[str], None] | None = None,
    *,
    capture_navigation_trace: bool = False,
    expected_final_url: str | None = None,
    cache_policy_final_document: bool = False,
) -> dict[str, object]:
    def mark_substage(name: str) -> None:
        if set_substage is not None:
            set_substage(name)

    mark_substage("same_origin")
    if not same_origin(shop_url, requested_url):
        raise AssertionError(f"{route_label} link left the isolated shop origin")
    mark_substage("performance_log")
    try:
        driver.get_log("performance")
    except Exception:
        message = f"UNVERIFIED: Chrome performance response logging is unavailable for {route_label}."
        print(message, file=sys.stderr)
        raise AssertionError(message)
    mark_substage("document_request")
    driver.get(requested_url)
    mark_substage("document_ready")
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    cache_policy_url = requested_url
    if cache_policy_final_document:
        cache_policy_url = driver.current_url
        if not same_origin(shop_url, cache_policy_url):
            raise AssertionError(f"{route_label} canonical destination left the isolated shop origin")
    main_frame_id = current_main_frame_id(driver)
    if not main_frame_id:
        raise AssertionError("Chrome main frame could not be identified for private response verification")
    mark_substage("cache_policy")
    if capture_navigation_trace:
        try:
            performance_entries = driver.get_log("performance")
        except Exception:
            message = f"UNVERIFIED: Chrome performance response logging is unavailable for {route_label}."
            print(message, file=sys.stderr)
            raise AssertionError(message)
        return assert_private_document_cache_headers(
            driver,
            cache_policy_url,
            shop_url,
            route_label,
            main_frame_id=main_frame_id,
            performance_entries=performance_entries,
            trace_main_frame_id=main_frame_id,
            navigation_trace_url=requested_url,
            expected_final_url=expected_final_url,
        )
    return assert_private_document_cache_headers(
        driver,
        cache_policy_url,
        shop_url,
        route_label,
        main_frame_id=main_frame_id,
    )


def customer_checkout_url_from_cart(driver: webdriver.Chrome, shop_url: str) -> str:
    """Use the native cart CTA's canonical order URL without exposing its query string."""
    links = [
        link
        for link in driver.find_elements(
            By.CSS_SELECTOR,
            ".js-cart-detailed-actions > .d-grid > a.btn-primary[href]",
        )
        if link.is_displayed() and link.is_enabled()
    ]
    if len(links) != 1:
        raise AssertionError("authenticated cart must expose exactly one enabled checkout link")

    href = links[0].get_attribute("href")
    if not isinstance(href, str) or not href:
        raise AssertionError("authenticated cart checkout link is empty")
    checkout_url = urljoin(shop_url.rstrip("/") + "/", href)
    if not same_origin(shop_url, checkout_url):
        raise AssertionError("authenticated cart checkout link left the isolated shop origin")
    return checkout_url


def worker_network_conditions(offline: bool) -> dict[str, object]:
    """Build worker-target network conditions for a direct flattened CDP session."""
    return {
        "offline": offline,
        "latency": 0,
        "downloadThroughput": 0 if offline else -1,
        "uploadThroughput": 0 if offline else -1,
    }


class ChromeBrowserCdpError(RuntimeError):
    """A bounded error for a Chrome DevTools command or connection failure."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: str,
        cause_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code
        self.cause_type = cause_type


def safe_exception_type(error: BaseException) -> str:
    error_type = type(error).__name__
    return error_type if error_type.isidentifier() else "unexpected_exception"


def safe_cdp_operation(method: str) -> str:
    operation = re.sub(r"[^A-Za-z0-9]+", "_", method).strip("_").lower()
    return operation if re.fullmatch(r"[a-z0-9_]+", operation) else "unknown"


def validate_local_chromedriver_debugger_address(debugger_address: object) -> tuple[str, int]:
    """Parse ChromeDriver's host:port capability, refusing non-loopback destinations."""
    if not isinstance(debugger_address, str) or not debugger_address:
        raise ChromeBrowserCdpError(
            "ChromeDriver did not expose a debugger address",
            diagnostic_code="devtools_endpoint_missing",
        )
    try:
        parsed = urlparse("//" + debugger_address)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except (TypeError, ValueError):
        raise ChromeBrowserCdpError(
            "ChromeDriver debugger address is malformed",
            diagnostic_code="devtools_debugger_address_invalid",
        ) from None

    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname == "localhost"
    if (
        parsed.netloc != debugger_address
        or not is_loopback
        or port is None
        or not 1 <= port <= 65535
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ChromeBrowserCdpError(
            "ChromeDriver debugger address is not a local endpoint",
            diagnostic_code="devtools_debugger_address_invalid",
        )
    return hostname, port


def discover_chromedriver_browser_websocket(capabilities: object) -> tuple[str, int]:
    """Read ChromeDriver's local `/json/version` endpoint without following redirects."""
    chrome_options = capabilities.get("goog:chromeOptions") if isinstance(capabilities, dict) else None
    debugger_address = chrome_options.get("debuggerAddress") if isinstance(chrome_options, dict) else None
    hostname, port = validate_local_chromedriver_debugger_address(debugger_address)

    connection = None
    try:
        connection = HTTPConnection(hostname, port, timeout=3)
        connection.request("GET", "/json/version")
        response = connection.getresponse()
        if response.status != 200:
            raise ChromeBrowserCdpError(
                "Chrome DevTools discovery endpoint returned a non-success response",
                diagnostic_code="devtools_discovery_failed",
            )
        body = response.read(65537)
        if len(body) > 65536:
            raise ChromeBrowserCdpError(
                "Chrome DevTools discovery response exceeded its size limit",
                diagnostic_code="devtools_response_invalid",
            )
        payload = json.loads(body.decode("utf-8"))
    except ChromeBrowserCdpError:
        raise
    except Exception as error:
        raise ChromeBrowserCdpError(
            "Chrome DevTools discovery request failed",
            diagnostic_code="devtools_discovery_failed",
            cause_type=safe_exception_type(error),
        ) from None
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    websocket_url = payload.get("webSocketDebuggerUrl") if isinstance(payload, dict) else None
    if not isinstance(websocket_url, str) or not websocket_url:
        raise ChromeBrowserCdpError(
            "Chrome DevTools discovery response omitted its browser websocket",
            diagnostic_code="devtools_endpoint_missing",
        )
    return websocket_url, port


def local_browser_devtools_url(driver: webdriver.Chrome) -> str:
    """Return Selenium's loopback browser endpoint without importing versioned CDP bindings."""
    capabilities = getattr(driver, "capabilities", None)
    websocket_url = capabilities.get("se:cdp") if isinstance(capabilities, dict) else None
    expected_port = None
    if not isinstance(websocket_url, str) or not websocket_url:
        websocket_url, expected_port = discover_chromedriver_browser_websocket(capabilities)
    try:
        parsed = urlparse(websocket_url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except (TypeError, ValueError):
        raise ChromeBrowserCdpError(
            "Chrome DevTools endpoint is malformed",
            diagnostic_code="devtools_endpoint_invalid",
        ) from None
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname == "localhost"

    if (
        parsed.scheme != "ws"
        or not is_loopback
        or port is None
        or not 1 <= port <= 65535
        or (expected_port is not None and port != expected_port)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or re.fullmatch(r"/devtools/browser/[^/]+", parsed.path) is None
    ):
        raise ChromeBrowserCdpError(
            "Chrome DevTools endpoint is not a local browser websocket",
            diagnostic_code="devtools_endpoint_invalid",
        )
    return websocket_url


def execute_browser_cdp_command(
    connection,
    method: str,
    parameters: dict[str, object] | None = None,
    session_id: str | None = None,
) -> dict[str, object]:
    """Send a flattened CDP command and wait for its matching protocol response."""
    previous_session = connection.session_id
    connection.session_id = session_id

    def command():
        result = yield {"method": method, "params": parameters or {}}
        return result

    try:
        result = connection.execute(command())
    except Exception as error:
        operation = safe_cdp_operation(method)
        raise ChromeBrowserCdpError(
            f"Chrome rejected or did not answer {method}",
            diagnostic_code=f"cdp_command_{operation}",
            cause_type=safe_exception_type(error),
        ) from None
    finally:
        connection.session_id = previous_session

    if not isinstance(result, dict):
        raise ChromeBrowserCdpError(
            f"Chrome returned an invalid response for {method}",
            diagnostic_code=f"cdp_response_{safe_cdp_operation(method)}",
        )
    return result


class ChromeBrowserCdp:
    """Use Selenium's pinned websocket connection for response-checked CDP calls."""

    def __init__(self, connection) -> None:
        self.connection = connection
        self.closed = False

    @classmethod
    def connect(cls, driver: webdriver.Chrome) -> "ChromeBrowserCdp":
        if WebSocketConnection is None:
            raise ChromeBrowserCdpError(
                "Selenium websocket support is unavailable",
                diagnostic_code="devtools_websocket_unavailable",
            )
        websocket_url = local_browser_devtools_url(driver)
        try:
            connection = WebSocketConnection(websocket_url)
        except Exception as error:
            raise ChromeBrowserCdpError(
                "Chrome DevTools websocket could not be opened",
                diagnostic_code="devtools_connection_open",
                cause_type=safe_exception_type(error),
            ) from None
        return cls(connection)

    def execute(
        self,
        method: str,
        parameters: dict[str, object] | None = None,
        session_id: str | None = None,
    ) -> dict[str, object]:
        if self.closed:
            raise ChromeBrowserCdpError(
                "Chrome DevTools websocket is closed",
                diagnostic_code="devtools_connection_closed",
            )
        return execute_browser_cdp_command(self.connection, method, parameters, session_id)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        close_errors: list[Exception] = []
        # Selenium 4.27.1 joins its websocket receiver before closing the socket.
        # Wake the pinned receiver first so close does not wait for its 30s timeout.
        try:
            socket = getattr(self.connection, "_ws", None)
            if socket is not None:
                socket.close()
        except Exception as error:
            close_errors.append(error)
        try:
            self.connection.close()
        except Exception as error:
            close_errors.append(error)
        if close_errors:
            raise ChromeBrowserCdpError(
                "Chrome DevTools websocket could not be closed",
                diagnostic_code="devtools_connection_close",
                cause_type=safe_exception_type(close_errors[0]),
            ) from None


def connect_browser_cdp(driver: webdriver.Chrome) -> ChromeBrowserCdp:
    return ChromeBrowserCdp.connect(driver)


def restore_offline_network_state(
    driver: webdriver.Chrome,
    primary_error: BaseException | None,
    worker_session: str | None = None,
    worker_cdp: ChromeBrowserCdp | None = None,
) -> None:
    """Reset page and worker networking without replacing an earlier QA failure."""
    resets = (
        (
            "Network.emulateNetworkConditions",
            {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1},
        ),
        ("Network.setCacheDisabled", {"cacheDisabled": False}),
    )
    cleanup_errors: list[Exception] = []
    if worker_session is not None and worker_cdp is not None:
        try:
            worker_cdp.execute(
                "Network.emulateNetworkConditions",
                worker_network_conditions(False),
                session_id=worker_session,
            )
        except Exception as error:
            cleanup_errors.append(error)

    for command, parameters in resets:
        try:
            driver.execute_cdp_cmd(command, parameters)
        except Exception as error:
            cleanup_errors.append(error)

    if worker_session is not None and worker_cdp is not None:
        try:
            worker_cdp.execute("Target.detachFromTarget", {"sessionId": worker_session})
        except Exception as error:
            cleanup_errors.append(error)
    if worker_cdp is not None:
        try:
            worker_cdp.close()
        except Exception as error:
            cleanup_errors.append(error)

    if not cleanup_errors:
        return

    error_types = []
    for error in cleanup_errors:
        error_type = type(error).__name__
        error_types.append(error_type if error_type.isidentifier() else "unexpected exception")

    if primary_error is not None:
        print(
            "WARNING: PWA network cleanup failed after the primary QA failure; "
            f"exception_types={','.join(error_types)}",
            file=sys.stderr,
        )
        return

    raise cleanup_errors[0]


def verify_offline_fallback(
    driver: webdriver.Chrome,
    base_url: str,
    locale: str,
    screenshot: Path,
    set_stage: Callable[[str], None],
) -> None:
    primary_error: BaseException | None = None
    worker_session: str | None = None
    worker_cdp: ChromeBrowserCdp | None = None
    try:
        set_stage("offline_devtools_enable")
        driver.execute_cdp_cmd("Network.enable", {})
        set_stage("offline_cache_bypass")
        driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        set_stage("offline_network_emulation")
        driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {"offline": True, "latency": 0, "downloadThroughput": 0, "uploadThroughput": 0},
        )
        set_stage("offline_devtools_connect")
        worker_cdp = connect_browser_cdp(driver)
        set_stage("offline_worker_target_list")
        targets = worker_cdp.execute("Target.getTargets")["targetInfos"]
        worker_url = base_url.rstrip("/") + "/sw.js"
        worker = next(
            (target for target in targets
             if target["type"] == "service_worker" and target["url"] == worker_url),
            None,
        )
        if worker is None:
            raise AssertionError("the storefront service-worker target is unavailable")
        set_stage("offline_worker_target_attach")
        worker_session = worker_cdp.execute(
            "Target.attachToTarget", {"targetId": worker["targetId"], "flatten": True}
        ).get("sessionId")
        if not isinstance(worker_session, str) or not worker_session:
            raise ChromeBrowserCdpError(
                "Chrome did not attach to the storefront worker",
                diagnostic_code="service_worker_session_missing",
            )
        set_stage("offline_worker_network_emulation")
        worker_cdp.execute("Network.enable", {}, session_id=worker_session)
        worker_cdp.execute(
            "Network.emulateNetworkConditions",
            worker_network_conditions(True),
            session_id=worker_session,
        )
        set_stage("offline_fallback_navigation")
        driver.get(base_url + "/")
        set_stage("offline_fallback_content")
        assert_offline_fallback_content(driver, locale)
        set_stage("offline_fallback_screenshot")
        driver.save_screenshot(str(screenshot))
        set_stage("offline_cache_storage")
        assert_empty_cache_storage(driver, "offline navigation")
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if primary_error is None:
            set_stage("offline_state_restore")
        restore_offline_network_state(driver, primary_error, worker_session, worker_cdp)
    set_stage("online_recovery_navigation")
    driver.get(base_url + "/")
    set_stage("online_recovery_content")
    if "ORDENOWA" not in driver.page_source.upper():
        raise AssertionError("the online storefront did not recover after offline navigation")


def click_native_when_unobstructed(driver: webdriver.Chrome, element) -> None:
    """Use a real WebDriver click only after its visible center is clear."""
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'instant', block: 'center', inline: 'nearest'});",
        element,
    )
    WebDriverWait(driver, 20, poll_frequency=0.2).until(
        lambda _browser: element.is_displayed() and element.is_enabled(),
        message="PWA registration control did not become visible and enabled",
    )
    WebDriverWait(driver, 20, poll_frequency=0.2).until(
        lambda browser: browser.execute_script(
            """
            const element = arguments[0];
            const rect = element.getBoundingClientRect();
            const target = document.elementFromPoint(
              rect.left + rect.width / 2,
              rect.top + rect.height / 2
            );
            return Boolean(target && (target === element || element.contains(target)));
            """,
            element,
        ),
        message="PWA registration control center is obstructed",
    )
    element.click()


def add_isolated_product_to_customer_cart(
    driver: webdriver.Chrome,
    base_url: str,
    product_id: int,
    set_stage: Callable[[str], None],
) -> None:
    """Add the CI fixture product so the authenticated checkout route renders real content."""
    if product_id < 1:
        raise AssertionError("PWA private-order QA requires the isolated synthetic product id")
    product_url = urljoin(
        base_url + "/",
        f"index.php?controller=product&id_product={product_id}",
    )
    if not same_origin(base_url, product_url):
        raise AssertionError("synthetic PWA product escaped the isolated shop")

    set_stage("customer_order_product_navigation")
    driver.get(product_url)
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    product_ids = [
        field.get_attribute("value")
        for field in driver.find_elements(By.CSS_SELECTOR, 'input[name="id_product"]')
    ]
    if str(product_id) not in product_ids:
        raise AssertionError("PWA customer product page did not match the isolated product id")

    set_stage("customer_order_product_add")
    add_button = wait_visible(driver, 'button[data-ps-ref="add-to-cart"]')
    click_native_when_unobstructed(driver, add_button)
    modal = WebDriverWait(driver, 25, poll_frequency=0.2).until(
        lambda browser: next(
            (
                candidate
                for candidate in browser.find_elements(By.CSS_SELECTOR, '[data-ps-ref="blockcart-modal"]')
                if candidate.is_displayed()
                and candidate.find_elements(By.CSS_SELECTOR, ".blockcart-modal__name")
                and "[CI ONLY]" in candidate.find_element(By.CSS_SELECTOR, ".blockcart-modal__name").text
            ),
            False,
        ),
        message="isolated PWA product was not added to the customer cart",
    )
    proceed = next(
        (
            link
            for link in modal.find_elements(By.CSS_SELECTOR, ".modal-footer > a.btn-primary")
            if link.is_displayed() and link.is_enabled()
        ),
        None,
    )
    if proceed is None:
        raise AssertionError("PWA cart confirmation has no visible cart link")
    click_native_when_unobstructed(driver, proceed)
    WebDriverWait(driver, 30, poll_frequency=0.2).until(
        lambda browser: [
            item.get_attribute("data-id-product")
            for item in browser.find_elements(
                By.CSS_SELECTOR,
                '.cart__item [data-link-action="delete-from-cart"][data-id-product]',
            )
        ] == [str(product_id)],
        message="PWA customer cart contents could not be confirmed",
    )


def create_session_customer(
    driver: webdriver.Chrome,
    base_url: str,
    email: str,
    password: str,
    start_url: str,
    locale: str,
    set_stage: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    def mark_stage(name: str) -> None:
        if set_stage is not None:
            set_stage(name)

    if not same_origin(base_url, start_url):
        raise AssertionError("localized customer sign-in home escaped the isolated shop")
    mark_stage("customer_signin_navigation")
    driver.get(start_url)
    assert_document_locale(driver, locale, "localized customer home")
    signin_links = driver.find_elements(
        By.CSS_SELECTOR,
        "#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]",
    )
    signin_url = next(
        (link.get_attribute("href") for link in signin_links if link.get_attribute("href")),
        "",
    )
    if not signin_url:
        raise AssertionError("storefront customer sign-in link is missing")
    if not same_origin(base_url, signin_url):
        raise AssertionError("customer sign-in link escaped the isolated shop")
    mark_stage("customer_signin_page")
    driver.get(signin_url)
    assert_document_locale(driver, locale, "customer sign-in page")
    signin_url = driver.current_url
    if not same_origin(base_url, signin_url):
        raise AssertionError("customer sign-in page redirected outside the isolated shop")
    mark_stage("customer_registration_navigation")
    registration = wait_visible(driver, 'a[data-link-action="display-register-form"]')
    registration_url = urljoin(driver.current_url, registration.get_attribute("href") or "")
    if not same_origin(base_url, registration_url):
        raise AssertionError("customer registration link escaped the isolated shop")
    mark_stage("customer_registration_form")
    driver.get(registration_url)
    assert_document_locale(driver, locale, "customer registration page")
    form = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#customer-form"))
    )
    for name, value in (("firstname", "Pwa"), ("lastname", "Session"), ("email", email)):
        fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
        usable = next((field for field in fields if field.is_displayed() and field.is_enabled()), None)
        if usable is None:
            raise AssertionError(f"customer registration form is missing {name}")
        usable.clear()
        usable.send_keys(value)
    passwords = [
        field for field in form.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
        if field.is_displayed() and field.is_enabled()
    ]
    if not passwords:
        raise AssertionError("customer registration form has no password control")
    for field in passwords:
        field.clear()
        field.send_keys(password)
    for field in form.find_elements(By.CSS_SELECTOR, "input[required]"):
        if not field.is_displayed() or not field.is_enabled():
            continue
        field_type = (field.get_attribute("type") or "").lower()
        if field_type == "checkbox":
            if field.is_selected():
                continue
            field_id = field.get_attribute("id") or ""
            label = next(
                (item for item in form.find_elements(By.CSS_SELECTOR, "label[for]")
                 if item.get_attribute("for") == field_id and item.is_displayed()),
                None,
            )
            if label is None:
                raise AssertionError("required customer consent has no visible label")
            mark_stage("customer_registration_required_consent")
            click_native_when_unobstructed(driver, label)
        elif field_type == "radio":
            if not any(
                item.is_selected()
                for item in form.find_elements(
                    By.CSS_SELECTOR, f'input[type="radio"][name="{field.get_attribute("name")}"]'
                )
            ):
                field.click()
        elif field.get_attribute("value"):
            continue
    if not driver.execute_script("return arguments[0].checkValidity()", form):
        raise AssertionError("synthetic PWA customer registration form is invalid")
    mark_stage("customer_registration_submit")
    submit = wait_visible(driver, "#customer-form button.form-control-submit")
    click_native_when_unobstructed(driver, submit)
    mark_stage("customer_registration_success_wait")
    WebDriverWait(driver, 30).until(
        lambda browser: browser.find_elements(By.ID, "identity_main_link")
        or browser.find_elements(By.ID, "userMenuButton")
    )
    account_url = authenticated_account_url(driver, base_url)
    navigate_private_document(driver, account_url, base_url, "authenticated account")
    assert_document_locale(driver, locale, "authenticated customer account")
    wait_visible(driver, "#identity_main_link")
    page_text = driver.find_element(By.TAG_NAME, "body").text
    if "Pwa" not in page_text or "Session" not in page_text:
        raise AssertionError("authenticated account page did not show the synthetic customer")
    assert_empty_cache_storage(driver, "authenticated customer account")
    return account_url, signin_url


def verify_logged_out_private_routes(
    driver: webdriver.Chrome,
    shop_url: str,
    set_substage: Callable[[str], None],
) -> None:
    """Check private customer redirects and public order lookup without logging URLs."""
    route_cases = (
        ("addresses", "addresses", 302),
        ("history", "history", 302),
        ("order_detail", "order-detail", 302),
        ("guest_tracking", "guest-tracking", None),
    )
    base = shop_url.rstrip("/") + "/"
    for route_stage, controller_name, expected_status in route_cases:
        set_substage(f"request_{route_stage}")
        # These controller selectors are fixed literals. The URL is internal to the isolated shop
        # and is never copied to diagnostics, screenshots, or annotations.
        requested_url = urljoin(base, f"index.php?controller={controller_name}")
        observed = navigate_private_document(
            driver,
            requested_url,
            shop_url,
            f"logged-out {route_stage.replace('_', ' ')}",
            set_substage=lambda name: set_substage(f"request_{route_stage}_{name}"),
            cache_policy_final_document=route_stage == "guest_tracking",
        )
        if expected_status is not None and observed.get("status") != expected_status:
            raise AssertionError(
                f"logged-out {route_stage.replace('_', ' ')} did not redirect to sign-in"
            )
        if route_stage == "guest_tracking":
            if observed.get("status") != 200:
                raise AssertionError(
                    "logged-out guest tracking did not render its public lookup form"
                )
            set_substage("require_guest_tracking_form")
            wait_visible(driver, "#guestOrderTrackingForm")
        else:
            set_substage(f"require_{route_stage}_login_form")
            wait_visible(driver, "#login-form input[name='email']")


def safe_selected_signout_metadata(signout: object, shop_url: str) -> dict[str, object]:
    try:
        element_id = signout.get_attribute("id")
        href = signout.get_attribute("href")
    except Exception:
        element_id = None
        href = None
    safe_id = element_id if element_id == "signout_link" else "none"
    container = "account_menu" if safe_id == "signout_link" else "my_account"
    target = safe_navigation_target(href, shop_url) if isinstance(href, str) else {
        "path": "<other>", "query_keys": []
    }
    return {"container": container, "element_id": safe_id, "target": target}


def attach_logout_context(
    error: BaseException,
    *,
    snapshot: dict[str, object],
    selected_signout: dict[str, object],
    logout_trace: dict[str, object],
    protected_pwa_trace: dict[str, object],
    protected_network_trace: dict[str, object],
) -> None:
    diagnostics = dict(snapshot)
    diagnostics.update(
        {
            "selected_signout": selected_signout,
            "logout_trace": logout_trace,
            "protected_pwa_trace": protected_pwa_trace,
            "protected_network_trace": protected_network_trace,
        }
    )
    try:
        error.pwa_logout_diagnostics = diagnostics
    except Exception:
        pass


def verify_logout_protection(
    driver: webdriver.Chrome,
    account_url: str,
    shop_url: str,
    first_name: str,
    last_name: str,
    email: str,
    screenshot: Path,
    set_substage: Callable[[str], None],
    expected_login_url: str | None = None,
    expected_locale: str | None = None,
) -> None:
    logout_substage = ""

    def mark_stage(name: str) -> None:
        nonlocal logout_substage
        logout_substage = name
        set_substage(name)

    mark_stage("resolve_signout_link")
    signout = WebDriverWait(driver, 30).until(
        lambda browser: next(
            (link for link in browser.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
             if link.is_displayed() and link.is_enabled()),
            False,
        )
    )
    selected_signout = safe_selected_signout_metadata(signout, shop_url)
    try:
        raw_signout_href = signout.get_attribute("href")
    except Exception:
        raw_signout_href = None
    signout_url = (
        urljoin(driver.current_url, raw_signout_href)
        if isinstance(raw_signout_href, str)
        else ""
    )
    signout_frame_id = current_main_frame_id(driver)
    try:
        driver.get_log("performance")
    except Exception:
        error = AssertionError("Chrome performance response logging is unavailable for logout")
        attach_logout_context(
            error,
            snapshot=safe_logout_wait_diagnostics(driver, shop_url),
            selected_signout=selected_signout,
            logout_trace=safe_document_navigation_trace([], signout_url, shop_url, ""),
            protected_pwa_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
            protected_network_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
        )
        raise error
    mark_stage("click_signout")
    signout.click()
    mark_stage("wait_signed_out_header")
    WebDriverWait(driver, 30).until(
        lambda browser: not any(
            link.is_displayed()
            for link in browser.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
        )
    )
    try:
        WebDriverWait(driver, 30).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        logout_entries = driver.get_log("performance")
    except Exception:
        logout_entries = []
    logout_trace = safe_document_navigation_trace(
        chrome_performance_events(logout_entries),
        signout_url,
        shop_url,
        signout_frame_id or "",
        expected_final_url=expected_login_url,
    )
    if logout_trace.get("observed") is not True or not any(
        isinstance(hop, dict) and hop.get("status") in {301, 302, 303, 307, 308}
        for hop in logout_trace.get("redirects", [])
    ):
        error = AssertionError("customer logout navigation and redirect were not observed")
        attach_logout_context(
            error,
            snapshot=safe_logout_wait_diagnostics(driver, shop_url),
            selected_signout=selected_signout,
            logout_trace=logout_trace,
            protected_pwa_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
            protected_network_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
        )
        raise error
    logout_navigation_error: BaseException | None = None
    logout_identity_exposed: bool | None = None
    logout_cache_empty: bool | None = None
    mark_stage("assert_logout_destination")
    try:
        validate_logout_navigation_trace(logout_trace)
    except Exception as error:
        logout_navigation_error = error
    try:
        if not any(
            element.is_displayed()
            for element in driver.find_elements(By.CSS_SELECTOR, "#login-form input[name='email']")
        ):
            raise AssertionError("customer logout did not display the login form")
        if expected_locale is not None:
            assert_document_locale(driver, expected_locale, "customer logout login page")
    except Exception as error:
        if logout_navigation_error is None:
            logout_navigation_error = error
    try:
        logout_body_text = driver.find_element(By.TAG_NAME, "body").text
        logout_identity_exposed = exposes_test_identity(
            logout_body_text, first_name, last_name, email
        )
        if logout_identity_exposed and logout_navigation_error is None:
            logout_navigation_error = AssertionError(
                "customer logout page exposed the synthetic customer's identity"
            )
    except Exception as error:
        if logout_navigation_error is None:
            logout_navigation_error = error
    try:
        assert_empty_cache_storage(driver, "customer logout destination")
        logout_cache_empty = True
    except Exception as error:
        logout_cache_empty = False
        if logout_navigation_error is None:
            logout_navigation_error = error
    mark_stage("request_protected_account")
    try:
        account_response = navigate_private_document(
            driver,
            account_url,
            shop_url,
            "logged-out account",
            set_substage=lambda name: mark_stage(f"request_protected_account_{name}"),
            capture_navigation_trace=True,
            expected_final_url=expected_login_url,
        )
    except Exception as error:
        attach_logout_context(
            error,
            snapshot=safe_logout_wait_diagnostics(driver, shop_url),
            selected_signout=selected_signout,
            logout_trace=logout_trace,
            protected_pwa_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
            protected_network_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
        )
        raise
    protected_pwa_trace = account_response.get("navigation_trace")
    if not isinstance(protected_pwa_trace, dict):
        protected_pwa_trace = safe_document_navigation_trace([], account_url, shop_url, "")
    if account_response.get("status") != 302:
        error = AssertionError("logged-out account did not redirect to sign-in")
        attach_logout_context(
            error,
            snapshot=safe_logout_wait_diagnostics(driver, shop_url),
            selected_signout=selected_signout,
            logout_trace=logout_trace,
            protected_pwa_trace=protected_pwa_trace,
            protected_network_trace=safe_document_navigation_trace([], account_url, shop_url, ""),
        )
        raise error
    mark_stage("wait_protected_document")
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    mark_stage("assert_no_account_links")
    if any(
        element.is_displayed() for element in driver.find_elements(By.ID, "identity_main_link")
    ):
        raise AssertionError("logged-out browser can still open the protected account page")
    if any(
        element.is_displayed() for element in driver.find_elements(By.ID, "userMenuButton")
    ):
        raise AssertionError("logged-out browser still shows an authenticated user menu")
    mark_stage("require_login_form")
    normal_form_error: BaseException | None = logout_navigation_error
    normal_failure_substage = (
        "assert_logout_destination" if logout_navigation_error is not None else "require_login_form"
    )
    try:
        wait_for_logout_login_form(driver, shop_url)
        if expected_locale is not None:
            assert_document_locale(driver, expected_locale, "service-worker-controlled login page")
    except Exception as error:
        normal_form_error = error
    try:
        validate_logged_out_navigation_trace(
            protected_pwa_trace,
            service_worker_expected=True,
        )
    except Exception as error:
        if normal_form_error is None:
            normal_form_error = error
            normal_failure_substage = "validate_pwa_navigation_trace"

    pwa_identity_exposed: bool | None = None
    pwa_cache_empty: bool | None = None
    mark_stage("assert_no_identity_in_pwa_document")
    try:
        pwa_body_text = driver.find_element(By.TAG_NAME, "body").text
        pwa_identity_exposed = exposes_test_identity(pwa_body_text, first_name, last_name, email)
        if pwa_identity_exposed and normal_form_error is None:
            normal_form_error = AssertionError(
                "controlled logged-out page exposed the synthetic customer's identity"
            )
            normal_failure_substage = "assert_no_identity_in_pwa_document"
    except Exception as error:
        if normal_form_error is None:
            normal_form_error = error
            normal_failure_substage = "assert_no_identity_in_pwa_document"
    mark_stage("assert_empty_pwa_cache")
    try:
        assert_empty_cache_storage(driver, "service-worker-controlled logged-out account route")
        pwa_cache_empty = True
    except Exception as error:
        pwa_cache_empty = False
        if normal_form_error is None:
            normal_form_error = error
            normal_failure_substage = "assert_empty_pwa_cache"
    pwa_snapshot, snapshot_error = capture_logout_snapshot_preserving_error(
        driver,
        shop_url,
        prior_error=normal_form_error,
    )
    if normal_form_error is None and snapshot_error is not None:
        normal_form_error = snapshot_error
        normal_failure_substage = "capture_pwa_diagnostic_snapshot"
    pwa_snapshot["controlled_identity_exposed"] = pwa_identity_exposed
    pwa_snapshot["controlled_cache_empty"] = pwa_cache_empty
    pwa_snapshot["logout_identity_exposed"] = logout_identity_exposed
    pwa_snapshot["logout_cache_empty"] = logout_cache_empty
    if pwa_identity_exposed is False:
        try:
            driver.save_screenshot(str(screenshot))
        except Exception as error:
            if normal_form_error is None:
                normal_form_error = error
                normal_failure_substage = "capture_logged_out_pwa_screenshot"

    protected_network_trace = safe_document_navigation_trace([], account_url, shop_url, "")
    network_form_error: BaseException | None = None
    network_identity_exposed: bool | None = None
    network_cache_empty: bool | None = None
    bypass_reset_ok = False
    service_worker_restored = False
    service_worker_ready_after_reset = False
    network_failure_substage = ""
    mark_stage("compare_service_worker_bypass")
    try:
        driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})
        network_response = navigate_private_document(
            driver,
            account_url,
            shop_url,
            "logged-out account without service worker",
            set_substage=lambda name: mark_stage(f"request_network_account_{name}"),
            capture_navigation_trace=True,
            expected_final_url=expected_login_url,
        )
        candidate_trace = network_response.get("navigation_trace")
        if isinstance(candidate_trace, dict):
            protected_network_trace = candidate_trace
        if network_response.get("status") != 302:
            network_form_error = AssertionError(
                "logged-out account did not redirect to sign-in with service worker bypassed"
            )
        else:
            try:
                wait_for_logout_login_form(driver, shop_url)
                if expected_locale is not None:
                    assert_document_locale(driver, expected_locale, "network-only login page")
            except Exception as error:
                network_form_error = error
            try:
                validate_logged_out_navigation_trace(
                    protected_network_trace,
                    service_worker_expected=False,
                )
            except Exception as error:
                if network_form_error is None:
                    network_form_error = error
            try:
                network_body_text = driver.find_element(By.TAG_NAME, "body").text
                network_identity_exposed = exposes_test_identity(
                    network_body_text, first_name, last_name, email
                )
                if network_identity_exposed and network_form_error is None:
                    network_form_error = AssertionError(
                        "network-only logged-out page exposed the synthetic customer's identity"
                    )
            except Exception as error:
                if network_form_error is None:
                    network_form_error = error
            try:
                assert_empty_cache_storage(driver, "network-only logged-out account route")
                network_cache_empty = True
            except Exception as error:
                network_cache_empty = False
                if network_form_error is None:
                    network_form_error = error
    except Exception as error:
        network_form_error = error
    finally:
        if network_form_error is not None and not network_failure_substage:
            network_failure_substage = logout_substage
        try:
            driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": False})
            bypass_reset_ok = True
        except Exception as error:
            if network_form_error is None:
                network_form_error = error
                network_failure_substage = logout_substage
    if network_form_error is not None and not network_failure_substage:
        network_failure_substage = logout_substage
    post_restore_trace = safe_document_navigation_trace([], account_url, shop_url, "")
    post_restore_identity_exposed: bool | None = None
    if bypass_reset_ok:
        mark_stage("verify_service_worker_restored_navigation")
        try:
            restored_response = navigate_private_document(
                driver,
                account_url,
                shop_url,
                "logged-out account after service worker restore",
                set_substage=lambda name: mark_stage(f"request_restored_account_{name}"),
                capture_navigation_trace=True,
                expected_final_url=expected_login_url,
            )
            restored_trace = restored_response.get("navigation_trace")
            if isinstance(restored_trace, dict):
                post_restore_trace = restored_trace
            if restored_response.get("status") != 302:
                raise AssertionError("logged-out account did not redirect after service worker restore")
            wait_for_service_worker(
                driver,
                shop_url,
                expected_login_url or driver.current_url,
            )
            service_worker_ready_after_reset = True
            validate_logged_out_navigation_trace(
                post_restore_trace,
                service_worker_expected=True,
            )
            wait_for_logout_login_form(driver, shop_url)
            if expected_locale is not None:
                assert_document_locale(driver, expected_locale, "restored service-worker login page")
            restored_body_text = driver.find_element(By.TAG_NAME, "body").text
            post_restore_identity_exposed = exposes_test_identity(
                restored_body_text, first_name, last_name, email
            )
            if post_restore_identity_exposed:
                raise AssertionError("restored service worker page exposed the synthetic customer's identity")
            assert_empty_cache_storage(driver, "logged-out account after service worker restore")
            service_worker_restored = service_worker_ready_after_reset
        except Exception as error:
            if network_form_error is None:
                network_form_error = error
    pwa_snapshot["service_worker_bypass_reset"] = bypass_reset_ok
    pwa_snapshot["service_worker_restored"] = service_worker_restored
    pwa_snapshot["network_identity_exposed"] = network_identity_exposed
    pwa_snapshot["network_cache_empty"] = network_cache_empty
    pwa_snapshot["post_restore_identity_exposed"] = post_restore_identity_exposed
    pwa_snapshot["post_restore_trace"] = post_restore_trace

    if normal_form_error is not None:
        mark_stage(normal_failure_substage)
        attach_logout_context(
            normal_form_error,
            snapshot=pwa_snapshot,
            selected_signout=selected_signout,
            logout_trace=logout_trace,
            protected_pwa_trace=protected_pwa_trace,
            protected_network_trace=protected_network_trace,
        )
        raise normal_form_error
    if network_form_error is not None:
        mark_stage(
            prefer_primary_failure_substage(
                network_form_error,
                network_failure_substage,
                logout_substage,
            )
        )
        attach_logout_context(
            network_form_error,
            snapshot=pwa_snapshot,
            selected_signout=selected_signout,
            logout_trace=logout_trace,
            protected_pwa_trace=protected_pwa_trace,
            protected_network_trace=protected_network_trace,
        )
        raise network_form_error
    mark_stage("assert_no_identity_on_protected_page")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if exposes_test_identity(body_text, first_name, last_name, email):
        raise AssertionError("protected account page exposed the synthetic customer's name after logout")
    mark_stage("assert_empty_logged_out_cache")
    assert_empty_cache_storage(driver, "logged-out protected account route")
    mark_stage("verify_logged_out_private_routes")
    verify_logged_out_private_routes(
        driver,
        shop_url,
        set_substage=mark_stage,
    )

    for history_stage in ("browser_history_first_back", "browser_history_second_back"):
        mark_stage(history_stage)
        driver.back()
        WebDriverWait(driver, 15).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        mark_stage("assert_no_identity_in_history")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if exposes_test_identity(body_text, first_name, last_name, email):
            raise AssertionError("browser history exposed the synthetic customer's name after logout")
    mark_stage("reopen_protected_account")
    driver.get(account_url)
    mark_stage("require_login_form_after_history")
    wait_for_logout_login_form(driver, shop_url)
    if expected_locale is not None:
        assert_document_locale(driver, expected_locale, "login page after browser history")
    mark_stage("assert_empty_account_cache_after_history")
    assert_empty_cache_storage(driver, "account route after browser back")


def _assert_localized_privacy_link(driver: webdriver.Chrome, locale: str) -> None:
    expected_labels = {
        "ja": "個人情報",
        "en": "Personal data",
        "ko": "개인정보",
    }
    if locale not in expected_labels:
        raise AssertionError("PWA account privacy link was checked with an unsupported locale")
    links = WebDriverWait(driver, 30).until(
        lambda browser: [
            link
            for link in browser.find_elements(By.CSS_SELECTOR, ".account-menu__link--psgdpr")
            if link.is_displayed()
        ]
        or False
    )
    labels = [
        " ".join((link.find_element(By.TAG_NAME, "span").text or "").split())
        for link in links
    ]
    if not labels or any(label != expected_labels[locale] for label in labels):
        raise AssertionError(f"customer privacy link is not localized for {locale}")


def _assert_customer_account_chrome(
    driver: webdriver.Chrome, locale: str, device: str
) -> None:
    localized_chrome = {
        "ja": ("マイアカウント", "マイアカウントメニュー"),
        "ko": ("내 계정", "내 계정 메뉴"),
    }
    if locale not in localized_chrome or device != "desktop":
        return
    title = " ".join(
        (driver.find_element(By.CSS_SELECTOR, ".account-menu__title").text or "").split()
    )
    navigation_label = driver.find_element(
        By.CSS_SELECTOR, ".account-menu__nav"
    ).get_attribute("aria-label")
    expected_title, expected_navigation_label = localized_chrome[locale]
    if title != expected_title or navigation_label != expected_navigation_label:
        raise AssertionError(f"{locale} customer account sidebar is not localized")


def run_viewport(
    base_url: str,
    artifact_dir: Path,
    width: int,
    height: int,
    device: str,
    locale: str,
    label: str,
    isolated_product_id: int,
) -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    locale_profile = browser_locale_profile(locale)
    options.add_argument(f"--lang={locale_profile['browser_tag']}")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = None
    stage = "chrome_start"
    primary_failure = False
    logout_substage = ""
    locale_home_url = ""

    def update_offline_stage(next_stage: str) -> None:
        nonlocal stage
        stage = next_stage

    def update_logout_substage(next_substage: str) -> None:
        nonlocal logout_substage
        logout_substage = next_substage

    try:
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(width, height)
        stage = "network_enable"
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders",
            {"headers": {"Accept-Language": locale_profile["accept_language"]}},
        )
        install_service_worker_registration_observer(driver)
        stage = "storefront_navigation"
        driver.get(base_url + "/")
        stage = "storefront_ready"
        WebDriverWait(driver, 40).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        # Let the first document be claimed before starting another navigation;
        # activation during that navigation can leave its new document uncontrolled.
        stage = "service_worker_bootstrap"
        wait_for_service_worker(driver, base_url, driver.current_url)
        stage = "storefront_locale"
        locale_home_url = select_storefront_locale(driver, base_url, locale)
        stage = "manifest"
        manifest = verify_manifest(driver, base_url)
        driver.save_screenshot(str(artifact_dir / f"pwa-{label}-installability.png"))
        stage = "service_worker_registration"
        registration = wait_for_service_worker(driver, base_url, locale_home_url)
        require_service_worker_registration_match(
            registration,
            "scope_matches_expected",
            "scope_mismatch",
            "service worker registration escaped the storefront scope",
        )
        require_service_worker_registration_match(
            registration,
            "script_origin_matches_expected",
            "script_origin_mismatch",
            "service worker controller script left the isolated shop origin",
        )
        require_service_worker_registration_match(
            registration,
            "script_path_matches_expected",
            "script_path_mismatch",
            "service worker controller is not the storefront worker",
        )
        assert_empty_cache_storage(driver, "initial storefront")

        stage = "service_worker_update"
        worker_update = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            (async () => {
              const registration = await navigator.serviceWorker.ready;
              await registration.update();
              return {activeState: registration.active?.state || '', hasController: Boolean(navigator.serviceWorker.controller)};
            })().then(done).catch(error => done({error: String(error)}));
            """
        )
        if not isinstance(worker_update, dict) or worker_update.get("activeState") != "activated":
            raise AssertionError("service worker update check did not retain an activated worker")
        stage = "online_refresh"
        driver.refresh()
        wait_for_service_worker(driver, base_url, locale_home_url)
        assert_empty_cache_storage(driver, "after online refresh")

        stage = "offline_fallback"
        verify_offline_fallback(
            driver,
            base_url,
            locale,
            artifact_dir / f"pwa-{label}-offline-fallback.png",
            update_offline_stage,
        )

        stage = "customer_account_setup"
        run_id = re.sub(r"[^0-9]", "", os.environ.get("GITHUB_RUN_ID", ""))
        attempt = re.sub(r"[^0-9]", "", os.environ.get("GITHUB_RUN_ATTEMPT", ""))
        unique = (run_id + attempt)[:20] or uuid.uuid4().hex[:16]
        email = f"qa-ordenowa-pwa-{unique}-{label}@example.invalid"
        password = f"Pwa-CI-{uuid.uuid4().hex[:20]}!"
        account_url, signin_url = create_session_customer(
            driver,
            base_url,
            email,
            password,
            locale_home_url,
            locale,
            set_stage=update_offline_stage,
        )
        stage = "customer_account_route"
        if not is_private_customer_back_target(account_url, base_url):
            raise AssertionError("generated account URL was not recognized as a private customer route")
        if customer_route_class(account_url, base_url) != "account":
            raise AssertionError("generated account URL was not classified as an account route")
        if device == "desktop" and locale == "ja":
            stage = "customer_order_cart_setup"
            add_isolated_product_to_customer_cart(
                driver,
                base_url,
                isolated_product_id,
                set_stage=update_offline_stage,
            )
            stage = "customer_private_routes"
            for route_stage, route_label, route_url in (
                ("customer_account_route", "authenticated account", account_url),
                (
                    "customer_cart_route",
                    "authenticated cart",
                    urljoin(base_url + "/", "index.php?controller=cart&action=show"),
                ),
            ):
                stage = route_stage
                navigate_private_document(driver, route_url, base_url, route_label)
                assert_empty_cache_storage(driver, route_label)
            stage = "customer_order_route"
            order_url = customer_checkout_url_from_cart(driver, base_url)
            navigate_private_document(driver, order_url, base_url, "authenticated order")
            assert_empty_cache_storage(driver, "authenticated order")
            stage = "customer_account_before_logout"
            navigate_private_document(driver, account_url, base_url, "authenticated account before logout")
            wait_visible(driver, "#identity_main_link")
            assert_document_locale(driver, locale, "authenticated account before logout")
        else:
            stage = "customer_account_navigation"
            navigate_private_document(driver, account_url, base_url, "authenticated account before logout")
            stage = "customer_account_main_link"
            wait_visible(driver, "#identity_main_link")
            stage = "customer_account_locale"
            assert_document_locale(driver, locale, "authenticated account before logout")
        stage = "customer_account_account_chrome"
        _assert_customer_account_chrome(driver, locale, device)
        stage = "customer_account_privacy_link"
        _assert_localized_privacy_link(driver, locale)
        stage = "customer_account_screenshot"
        driver.save_screenshot(str(artifact_dir / f"pwa-{label}-account.png"))
        stage = "customer_logout"
        verify_logout_protection(
            driver,
            account_url,
            base_url,
            "Pwa",
            "Session",
            email,
            artifact_dir / f"pwa-{label}-logged-out-account.png",
            set_substage=update_logout_substage,
            expected_login_url=signin_url,
            expected_locale=locale,
        )
        logout_substage = ""
        for route_stage, route_url in (
            ("guest_authentication_route", signin_url),
            (
                "guest_account_route",
                localized_controller_url(
                    base_url, locale_home_url, "index.php?controller=my-account"
                ),
            ),
            (
                "guest_cart_route",
                localized_controller_url(
                    base_url, locale_home_url, "index.php?controller=cart&action=show"
                ),
            ),
            (
                "guest_order_detail_route",
                localized_controller_url(
                    base_url, locale_home_url, "index.php?controller=order-detail"
                ),
            ),
        ):
            stage = route_stage
            if not same_origin(base_url, route_url):
                raise AssertionError("guest route escaped the isolated storefront origin")
            expected_login_url = (
                signin_url
                if route_stage in {"guest_account_route", "guest_order_detail_route"}
                else None
            )
            observed = navigate_private_document(
                driver,
                route_url,
                base_url,
                f"logged-out {route_stage.replace('_', ' ')}",
                capture_navigation_trace=True,
                expected_final_url=expected_login_url,
            )
            if expected_login_url is not None:
                if observed.get("status") != 302:
                    raise AssertionError(
                        f"logged-out {route_stage.replace('_', ' ')} did not redirect to sign-in"
                    )
                validate_logged_out_navigation_trace(
                    observed.get("navigation_trace"),
                    service_worker_expected=False,
                )
                wait_for_logout_login_form(driver, base_url)
            elif route_stage == "guest_authentication_route":
                wait_for_logout_login_form(driver, base_url)
            assert_document_locale(driver, locale, f"logged-out {route_stage.replace('_', ' ')}")
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if exposes_test_identity(body_text, "Pwa", "Session", email):
                raise AssertionError(
                    f"logged-out {route_stage.replace('_', ' ')} exposed the synthetic customer's identity"
                )
            assert_empty_cache_storage(driver, f"guest {route_stage}")

        if locale == "en":
            stage = "guest_empty_checkout_navigation"
            empty_order_url = localized_controller_url(
                base_url, locale_home_url, "index.php?controller=order"
            )
            empty_checkout = navigate_private_document(
                driver,
                empty_order_url,
                base_url,
                "logged-out empty checkout",
                capture_navigation_trace=True,
                cache_policy_final_document=True,
            )
            stage = "guest_empty_checkout_final_response"
            if empty_checkout.get("status") != 200:
                raise AssertionError("logged-out empty checkout did not return to the cart")
            stage = "guest_empty_checkout_trace"
            try:
                validate_logged_out_empty_order_cart_navigation_trace(
                    empty_checkout.get("navigation_trace"),
                    set_substage=update_offline_stage,
                )
            except AssertionError as error:
                raise PwaDiagnosticAssertionError(
                    "logged-out empty checkout redirect trace failed validation",
                    "empty_checkout_route",
                    {"navigation_trace": empty_checkout.get("navigation_trace")},
                ) from error
            stage = "guest_empty_checkout_route"
            final_target = safe_navigation_target(driver.current_url, base_url)
            if final_target.get("controller") != "cart":
                raise AssertionError("logged-out empty checkout did not finish on the cart route")
            stage = "guest_empty_checkout_locale"
            assert_document_locale(driver, locale, "logged-out empty checkout cart")
            stage = "guest_empty_checkout_empty_cart"
            wait_for_empty_cart(driver)
            stage = "guest_empty_checkout_identity"
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if exposes_test_identity(body_text, "Pwa", "Session", email):
                raise AssertionError("logged-out empty checkout exposed the synthetic customer's identity")
            stage = "guest_empty_checkout_cache"
            assert_empty_cache_storage(driver, "guest empty checkout")

        print(
            f"PASS: {label} Chromium secure-context installability prerequisites, official manifest icons, "
            "service-worker control/update/reload, localized offline navigation, and empty private cache state"
        )
    except Exception as error:
        primary_failure = True
        try:
            current_path = urlparse(driver.current_url).path if driver is not None else ""
        except Exception:
            # The Chrome session may already be gone; keep the original QA failure.
            current_path = ""
        safe_path = current_path if current_path in {"/", "/index.php"} else "/<other>"
        error_type = type(error).__name__
        if not error_type.isidentifier():
            error_type = "unexpected exception"
        diagnostic = ""
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", logout_substage):
            diagnostic = f"; substage={logout_substage}"
        logout_diagnostics = getattr(error, "pwa_logout_diagnostics", None)
        if isinstance(logout_diagnostics, dict):
            diagnostic += format_logout_wait_diagnostic(logout_diagnostics)
        if isinstance(error, PwaDiagnosticAssertionError):
            code = error.diagnostic_code
            if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code):
                diagnostic += f"; diagnostic={code}"
                metadata = error.safe_metadata
                if code in {"document_response_missing", "cache_policy_missing"}:
                    diagnostic += response_count_diagnostic(metadata.get("response_count"))
                if code == "cache_policy_missing":
                    safe_status = metadata.get("status")
                    if isinstance(safe_status, int) and 100 <= safe_status <= 599:
                        diagnostic += f"; response_status={safe_status}"
                    directives = metadata.get("cache_control_directives")
                    if isinstance(directives, list) and all(
                        isinstance(item, str) and re.fullmatch(r"[a-z0-9-]{1,32}", item)
                        for item in directives
                    ):
                        diagnostic += f"; cache_control_directives={','.join(directives) or 'missing'}"
                    for key in ("pragma_present", "expires_present", "from_disk_cache", "from_service_worker"):
                        value = metadata.get(key)
                        if isinstance(value, bool):
                            diagnostic += f"; {key}={str(value).lower()}"
                    navigation_trace = metadata.get("navigation_trace")
                    if isinstance(navigation_trace, dict):
                        diagnostic += f"; navigation_trace={_format_navigation_trace(navigation_trace)}"
                elif code == "empty_checkout_route":
                    navigation_trace = metadata.get("navigation_trace")
                    if isinstance(navigation_trace, dict):
                        diagnostic += f"; navigation_trace={_format_navigation_trace(navigation_trace)}"
                elif code == "service_worker_registration":
                    diagnostic += format_service_worker_registration_diagnostic(metadata)
        if isinstance(error, ChromeBrowserCdpError):
            code = getattr(error, "diagnostic_code", "")
            cause = getattr(error, "cause_type", "")
            if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]+", code):
                diagnostic += f"; diagnostic={code}"
            if isinstance(cause, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cause):
                diagnostic += f"; cause={cause}"
        print(
            f"FAIL: {label} PWA browser QA at stage={stage} ({error_type}); path={safe_path}{diagnostic}.",
            file=sys.stderr,
        )
        print(
            f"::error title=ORDENOWA PWA browser QA::{label}; stage={stage}; "
            f"exception={error_type}; path={safe_path}{diagnostic}",
            file=sys.stderr,
        )
        raise
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as cleanup_error:
                error_type = type(cleanup_error).__name__
                if not error_type.isidentifier():
                    error_type = "unexpected exception"
                if primary_failure:
                    print(
                        f"WARNING: {label} PWA browser cleanup failed ({error_type}) after the primary failure.",
                        file=sys.stderr,
                    )
                else:
                    stage = "chrome_shutdown"
                    print(
                        f"FAIL: {label} PWA browser QA at stage={stage} ({error_type}).",
                        file=sys.stderr,
                    )
                    print(
                        f"::error title=ORDENOWA PWA browser QA::{label}; stage={stage}; exception={error_type}",
                        file=sys.stderr,
                    )
                    raise


def main() -> int:
    if webdriver is None:
        print("FAIL: Selenium is required for the PWA browser QA.", file=sys.stderr)
        return 2
    base_url = os.environ["SHOP_BASE_URL"].rstrip("/")
    try:
        validate_isolated_ci_target(base_url)
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    artifact_dir = Path(os.environ["QA_ARTIFACT_DIR"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        print("FAIL: SHOP_BASE_URL is not a safe shop origin.", file=sys.stderr)
        return 2
    try:
        ipaddress.ip_address(parsed.hostname)
        is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        is_loopback = parsed.hostname.lower() == "localhost"
    if not is_loopback:
        print("FAIL: PWA QA may only run against the isolated shop on a loopback origin.", file=sys.stderr)
        return 2
    if parsed.scheme not in {"http", "https"}:
        print("FAIL: PWA QA requires HTTP or HTTPS on the isolated loopback origin.", file=sys.stderr)
        return 2
    product_id_text = os.environ.get("CI_TEST_PRODUCT_ID", "")
    if re.fullmatch(r"[1-9][0-9]*", product_id_text) is None:
        print("FAIL: PWA QA requires the isolated synthetic product fixture.", file=sys.stderr)
        return 2
    isolated_product_id = int(product_id_text)
    failed = []
    for device, locale, width, height, label in pwa_browser_cases():
        try:
            run_viewport(
                base_url,
                artifact_dir,
                width,
                height,
                device,
                locale,
                label,
                isolated_product_id,
            )
        except Exception as error:
            print(f"FAIL: {device}/{locale} PWA browser QA ({type(error).__name__}).", file=sys.stderr)
            failed.append(label)
    print("INFO: real iOS and Android device installation was not tested.")
    print("INFO: Chromium headless installability prerequisites passed; native install prompt was not opened.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
