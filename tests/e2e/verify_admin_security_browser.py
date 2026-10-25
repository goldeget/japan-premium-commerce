#!/usr/bin/env python3
"""Exercise real Back Office authorization and CSRF rejection in isolated CI."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from admin_locale_diagnostics import (
    SAFE_ADMIN_LOCALE_RESPONSE_PATTERN,
    format_orders_body_match_sources,
    parse_admin_locale_response_diagnostic,
)
from shipping_admin_routes import is_korean_admin_language
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
VIEW_ONLY_EMAIL = os.environ["VIEW_ONLY_EMPLOYEE_EMAIL"]
DASHBOARD_VIEW_ONLY_EMAIL = os.environ["DASHBOARD_VIEW_ONLY_EMAIL"]
COMPOSE_PROJECT = os.environ.get("CI_COMPOSE_PROJECT_NAME", "")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SHOP_PORT = 18080
SETTING_FIELD = "profile[brand][name][ko-KR]"
MUTATION_SENTINEL = "ORDENOWA CI security rejection sentinel"
SAFE_ADMIN_SECURITY_RESPONSE_PATTERN = (
    r"classification=[a-z_]+; status=(?:[0-9]{1,3}|invalid); final_path=[A-Za-z0-9/._?-]{1,160}; "
    r"settings_form=(?:true|false); danger_alert=(?:true|false); admin_login_form=(?:true|false); "
    r"native_compromised_page=(?:true|false); "
    r"compromised_request_origin=(?:true|false); compromised_request_path=(?:true|false); "
    r"compromised_marker=(?:true|false); compromised_warning=(?:true|false); "
    r"compromised_continue=(?:true|false); compromised_dashboard=(?:true|false); "
    r"compromised_response_origin=(?:true|false); compromised_response_path=(?:true|false); "
    r"compromised_continue_origin=(?:true|false); compromised_continue_path=(?:true|false); "
    r"compromised_continue_controller=(?:true|false); compromised_continue_token=(?:true|false); "
    r"compromised_dashboard_origin=(?:true|false); compromised_dashboard_path=(?:true|false); "
    r"compromised_dashboard_controller=(?:true|false); compromised_dashboard_token=(?:true|false); "
    r"response_controller=(?:AdminBusinessProfile|AdminDashboard|AdminOrders|AdminLogin|none|other); "
    r"invalid_token_warning=(?:true|false); invalid_token_continue=(?:true|false); "
    r"invalid_token_cancel=(?:true|false); recovery_same_origin=(?:true|false); "
    r"recovery_same_path=(?:true|false); "
    r"recovery_controller=(?:AdminBusinessProfile|AdminDashboard|AdminLogin|none|other|unavailable); "
    r"recovery_token_present=(?:true|false); invalid_token_page=(?:true|false)"
)
SAFE_ADMIN_NAVIGATION_STATE_PATTERN = (
    r"login_form_visible=(?:true|false); current_controller=(?:AdminBusinessProfile|AdminDashboard|AdminOrders|AdminLogin|none|other); "
    r"business_profile_link_count=(?:0|[1-9][0-9]{0,3}); dashboard_link_count=(?:0|[1-9][0-9]{0,3})"
)
SAFE_ADMIN_ORDERS_STATE_PATTERN = (
    r"route=AdminOrders;orders_path=(?:orders_list|other|unknown);"
    r"http_status=(?:[1-5][0-9]{2}|unknown);"
    r"document_ready=(?:loading|interactive|complete|unknown);"
    r"document_locale=(?:korean|other|missing|unknown);"
    r"login_form_visible=(?:true|false|unknown);admin_shell_visible=(?:true|false|unknown);"
    r"body_text=(?:empty|present|unknown);"
    r"orders_heading=(?:korean|english|other|missing|unknown);"
    r"orders_grid_heading=(?:korean|english|other|missing|unknown);"
    r"orders_grid_visible=(?:true|false|unknown);"
    r"orders_empty_state_visible=(?:true|false|unknown);"
    r"orders_empty_state_korean=(?:true|false|unknown);"
    r"permission_denied=(?:true|false|unknown);english_order_label=(?:true|false|unknown);"
    r"body_match_source_categories=(?:unknown|none|other_visible_content|"
    r"(?:toolbar|breadcrumb|navigation|kpi|grid_header|grid_controls|grid_actions|grid_body|modal|alert|empty_state)"
    r"(?:,(?:toolbar|breadcrumb|navigation|kpi|grid_header|grid_controls|grid_actions|grid_body|modal|alert|empty_state))*);"
    r"alert_visible=(?:true|false|unknown);"
    r"body_has_korean_order_label=(?:true|false|unknown)"
)
SAFE_ADMIN_ORDERS_LINK_PATTERN = (
    r"orders_path_candidates=(?:[0-9]{1,4}|unknown);"
    r"orders_root_candidates=(?:[0-9]{1,4}|unknown);"
    r"orders_new_candidates=(?:[0-9]{1,4}|unknown);"
    r"orders_item_candidates=(?:[0-9]{1,4}|unknown);"
    r"orders_other_subroute_candidates=(?:[0-9]{1,4}|unknown);"
    r"legacy_orders_candidates=(?:[0-9]{1,4}|unknown);"
    r"eligible_list_links=(?:[0-9]{1,4}|unknown)"
)
TOKEN_DOM_DETECTOR_JS = r"""
function inspectInvalidTokenPage(body, responseUrl, targetUrl) {
  const responseDocument = new DOMParser().parseFromString(body, 'text/html');
  const warning = responseDocument.querySelector('.container > .error-msg img[alt="warning"]');
  const tokenContinue = responseDocument.querySelector('.action-container a.btn-continue[href]');
  const tokenCancel = responseDocument.querySelector('.action-container a.btn-cancel[href="index.php"]');
  let recoverySameOrigin = false;
  let recoverySamePath = false;
  let recoveryController = 'unavailable';
  let recoveryTokenPresent = false;
  if (tokenContinue) {
    try {
      const recovery = new URL(tokenContinue.getAttribute('href'), responseUrl);
      const target = new URL(targetUrl);
      recoverySameOrigin = recovery.origin === target.origin;
      recoverySamePath = recovery.pathname === target.pathname;
      const controller = recovery.searchParams.get('controller');
      recoveryController = controller === 'AdminBusinessProfile' || controller === 'AdminDashboard'
        ? controller
        : controller ? 'other' : 'none';
      recoveryTokenPresent = Boolean(recovery.searchParams.get('token'));
    } catch (_) {
      // The safe diagnostic flags below remain false for malformed recovery links.
    }
  }
  const hasWarning = Boolean(warning);
  const hasContinue = Boolean(tokenContinue);
  const hasCancel = Boolean(tokenCancel);
  const bodyHasInvalidTokenPage = hasWarning && hasContinue && hasCancel
    && recoverySameOrigin && recoverySamePath
    && recoveryController === 'AdminBusinessProfile' && recoveryTokenPresent;
  return {
    bodyHasInvalidTokenPage,
    bodyHasInvalidTokenWarning: hasWarning,
    bodyHasInvalidTokenContinue: hasContinue,
    bodyHasInvalidTokenCancel: hasCancel,
    invalidTokenRecoverySameOrigin: recoverySameOrigin,
    invalidTokenRecoverySamePath: recoverySamePath,
    invalidTokenRecoveryController: recoveryController,
    invalidTokenRecoveryTokenPresent: recoveryTokenPresent
  };
}

function inspectNativeCompromisedPage(body, responseUrl, targetUrl, adminBaseUrl) {
  const responseDocument = new DOMParser().parseFromString(body, 'text/html');
  const page = responseDocument.querySelector('#security-compromised-page');
  const details = {
    bodyHasNativeCompromisedPage: false,
    compromisedRequestSameOrigin: false,
    compromisedRequestInAdminPath: false,
    compromisedPageMarker: Boolean(page),
    compromisedWarning: false,
    compromisedContinueLink: false,
    compromisedDashboardLink: false,
    compromisedResponseSameOrigin: false,
    compromisedResponsePath: false,
    compromisedContinueSameOrigin: false,
    compromisedContinuePath: false,
    compromisedContinueController: false,
    compromisedContinueTokenPresent: false,
    compromisedDashboardSameOrigin: false,
    compromisedDashboardPath: false,
    compromisedDashboardController: false,
    compromisedDashboardTokenPresent: false
  };
  if (!page) return details;

  const warning = page.querySelector('.alert.alert-danger[role="alert"] .alert-text');
  const continueLink = page.querySelector('a.btn-outline-danger[href]');
  const dashboardLink = page.querySelector('a.btn-primary[href]');
  details.compromisedWarning = Boolean(warning && warning.textContent.trim());
  details.compromisedContinueLink = Boolean(continueLink);
  details.compromisedDashboardLink = Boolean(dashboardLink);
  if (!warning || !warning.textContent.trim() || !continueLink || !dashboardLink) return details;

  try {
    const response = new URL(responseUrl);
    const adminBase = new URL(adminBaseUrl);
    const target = new URL(targetUrl, adminBaseUrl);
    const adminPath = adminBase.pathname.replace(/\/+$/, '');
    if (!adminPath || adminPath === '/' || adminBase.search || adminBase.hash) return details;
    const adminIndexSuffix = '/index.php';
    const continueUrl = new URL(continueLink.getAttribute('href'), responseUrl);
    const dashboardUrl = new URL(dashboardLink.getAttribute('href'), responseUrl);
    const tokenPresent = url => {
      const tokens = [...url.searchParams.getAll('token'), ...url.searchParams.getAll('_token')];
      return tokens.length === 1 && tokens[0].trim().length > 0;
    };
    const hasController = (url, expected) => {
      const controllers = url.searchParams.getAll('controller');
      return controllers.length === 1 && controllers[0] === expected;
    };
    details.compromisedRequestSameOrigin = target.origin === adminBase.origin;
    details.compromisedRequestInAdminPath = target.pathname === adminPath
      || target.pathname.startsWith(adminPath + '/');
    if (!details.compromisedRequestSameOrigin || !details.compromisedRequestInAdminPath) return details;
    const expectedAdminIndexPath = adminPath + adminIndexSuffix;
    const isAdminControllerRoutePath = pathname => {
      if (pathname === adminPath || pathname === adminPath + '/') return true;
      if (pathname === expectedAdminIndexPath) return true;
      if (!pathname.startsWith(adminPath + '/')) return false;
      const route = pathname.slice(adminPath.length + 1).replace(/\/+$/, '');
      return route.length > 0 && route.split('/').every(segment => segment.length > 0 && !segment.includes('.'));
    };
    details.compromisedResponseSameOrigin = response.origin === adminBase.origin;
    details.compromisedResponsePath = response.pathname === adminPath + '/security/compromised';
    details.compromisedContinueSameOrigin = continueUrl.origin === adminBase.origin;
    details.compromisedContinuePath = continueUrl.pathname === target.pathname
      && isAdminControllerRoutePath(continueUrl.pathname);
    details.compromisedContinueController = hasController(continueUrl, 'AdminBusinessProfile');
    details.compromisedContinueTokenPresent = tokenPresent(continueUrl);
    details.compromisedDashboardSameOrigin = dashboardUrl.origin === adminBase.origin;
    details.compromisedDashboardPath = isAdminControllerRoutePath(dashboardUrl.pathname);
    details.compromisedDashboardController = hasController(dashboardUrl, 'AdminDashboard');
    details.compromisedDashboardTokenPresent = tokenPresent(dashboardUrl);
    details.bodyHasNativeCompromisedPage = details.compromisedResponseSameOrigin
      && details.compromisedRequestSameOrigin
      && details.compromisedRequestInAdminPath
      && details.compromisedResponsePath
      && details.compromisedContinueSameOrigin
      && details.compromisedContinuePath
      && details.compromisedContinueController
      && details.compromisedDashboardSameOrigin
      && details.compromisedDashboardPath
      && details.compromisedDashboardController
      && details.compromisedDashboardTokenPresent;
    return details;
  } catch (_) {
    return details;
  }
}
"""


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def _admin_controller_for_url(url: str) -> str:
    actual = urlparse(url)
    expected = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (actual.scheme, actual.hostname, actual.port) != (
        expected.scheme,
        expected.hostname,
        expected.port,
    ) or not actual.path.startswith(admin_path + "/"):
        return "other"
    if actual.path.startswith(admin_path + "/sell/orders"):
        return "AdminOrders"
    controllers = parse_qs(actual.query).get("controller", [])
    if controllers == ["AdminBusinessProfile"]:
        return "AdminBusinessProfile"
    if controllers == ["AdminDashboard"]:
        return "AdminDashboard" if actual.path == admin_path + "/index.php" else "other"
    if controllers == ["AdminOrders"]:
        return "AdminOrders"
    if controllers == ["AdminLogin"]:
        return "AdminLogin"
    return "none" if not controllers else "other"


def is_admin_orders_list_url(url: str) -> bool:
    """Accept only the same-origin AdminOrders list route, never its create/detail routes."""
    try:
        actual = urlparse(url)
        expected = urlparse(BASE)
        admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
        actual_origin = (actual.scheme, actual.hostname, actual.port)
        expected_origin = (expected.scheme, expected.hostname, expected.port)
    except ValueError:
        return False
    if actual.username is not None or actual.password is not None or actual_origin != expected_origin:
        return False
    if actual.path in {admin_path + "/sell/orders", admin_path + "/sell/orders/"}:
        return True
    if actual.path != admin_path + "/index.php":
        return False
    query = parse_qs(actual.query, keep_blank_values=True)
    return (
        set(query) == {"controller", "token"}
        and query.get("controller") == ["AdminOrders"]
        and len(query.get("token", [])) == 1
        and bool(query["token"][0].strip())
    )


def safe_admin_orders_link_state(driver: webdriver.Chrome) -> str:
    """Count only route categories; never expose tokenized or customer-specific hrefs."""
    try:
        admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
        expected = urlparse(BASE)
        expected_origin = (expected.scheme, expected.hostname, expected.port)
        path_candidates = 0
        root_candidates = 0
        new_candidates = 0
        item_candidates = 0
        other_subroute_candidates = 0
        legacy_candidates = 0
        eligible_list_links = 0
        for link in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = link.get_attribute("href") or ""
            try:
                parsed = urlparse(href)
                query = parse_qs(parsed.query, keep_blank_values=True)
            except ValueError:
                continue
            try:
                actual_origin = (parsed.scheme, parsed.hostname, parsed.port)
            except ValueError:
                continue
            if actual_origin != expected_origin or not parsed.path.startswith(admin_path + "/"):
                continue
            orders_root = admin_path + "/sell/orders"
            if parsed.path == orders_root or parsed.path.startswith(orders_root + "/"):
                path_candidates += 1
                suffix = parsed.path[len(orders_root):].strip("/")
                segments = [segment for segment in suffix.split("/") if segment]
                if not segments:
                    root_candidates += 1
                elif segments == ["new"]:
                    new_candidates += 1
                elif segments[0].isascii() and segments[0].isdecimal():
                    item_candidates += 1
                else:
                    other_subroute_candidates += 1
            if parsed.path == admin_path + "/index.php" and query.get("controller") == ["AdminOrders"]:
                legacy_candidates += 1
            if is_admin_orders_list_url(href):
                eligible_list_links += 1
        return (
            f"orders_path_candidates={min(path_candidates, 1000)};"
            f"orders_root_candidates={min(root_candidates, 1000)};"
            f"orders_new_candidates={min(new_candidates, 1000)};"
            f"orders_item_candidates={min(item_candidates, 1000)};"
            f"orders_other_subroute_candidates={min(other_subroute_candidates, 1000)};"
            f"legacy_orders_candidates={min(legacy_candidates, 1000)};"
            f"eligible_list_links={min(eligible_list_links, 1000)}"
        )
    except Exception:
        return (
            "orders_path_candidates=unknown;orders_root_candidates=unknown;orders_new_candidates=unknown;"
            "orders_item_candidates=unknown;orders_other_subroute_candidates=unknown;"
            "legacy_orders_candidates=unknown;eligible_list_links=unknown"
        )


def safe_admin_navigation_state(driver: webdriver.Chrome) -> dict[str, object]:
    """Expose only login visibility, allowlisted controller, and bounded menu counts."""
    login_form_visible = any(
        element.is_displayed()
        for element in driver.find_elements(By.CSS_SELECTOR, "#login_form")
    )
    profile_count = sum(
        _admin_controller_for_url(link.get_attribute("href") or "") == "AdminBusinessProfile"
        for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminBusinessProfile"]')
    )
    dashboard_count = sum(
        _admin_controller_for_url(link.get_attribute("href") or "") == "AdminDashboard"
        for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminDashboard"]')
    )
    return {
        "login_form_visible": login_form_visible,
        "current_controller": _admin_controller_for_url(driver.current_url),
        "business_profile_link_count": min(profile_count, 1000),
        "dashboard_link_count": min(dashboard_count, 1000),
    }


def _safe_admin_navigation_state_text(driver: webdriver.Chrome) -> str:
    state = safe_admin_navigation_state(driver)
    return (
        f"login_form_visible={str(state['login_form_visible']).lower()}; "
        f"current_controller={state['current_controller']}; "
        f"business_profile_link_count={state['business_profile_link_count']}; "
        f"dashboard_link_count={state['dashboard_link_count']}"
    )


def _authenticated_admin_route_ready(driver: webdriver.Chrome) -> bool:
    try:
        login_form_visible = any(
            element.is_displayed()
            for element in driver.find_elements(By.CSS_SELECTOR, "#login_form")
        )
    except StaleElementReferenceException:
        # A successful login can replace the login form while this wait is polling.
        return False
    if login_form_visible:
        return False

    current = urlparse(driver.current_url)
    expected = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (
        (current.scheme, current.hostname, current.port)
        != (expected.scheme, expected.hostname, expected.port)
        or not (current.path == admin_path or current.path.startswith(admin_path + "/"))
        or _admin_controller_for_url(driver.current_url) == "AdminLogin"
    ):
        return False

    try:
        navigation = safe_admin_navigation_state(driver)
    except StaleElementReferenceException:
        return False
    return (
        navigation["business_profile_link_count"] > 0
        or navigation["dashboard_link_count"] > 0
    )


def current_profile_settings_url(driver: webdriver.Chrome) -> str:
    """Return the current employee's tokenized settings URL after same-origin checks."""
    current_url = driver.current_url
    actual = urlparse(current_url)
    expected = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (actual.scheme, actual.hostname, actual.port) != (
        expected.scheme,
        expected.hostname,
        expected.port,
    ) or not actual.path.startswith(admin_path + "/"):
        raise AssertionError("the authenticated settings route left the isolated Back Office origin")
    query = parse_qs(actual.query, keep_blank_values=True)
    if query.get("controller") != ["AdminBusinessProfile"]:
        raise AssertionError("the authenticated route is not the business profile settings controller")
    if len(query.get("token", [])) != 1 or not query["token"][0].strip():
        raise AssertionError("the authenticated settings route lacks its employee-scoped admin token")
    return current_url


def _same_admin_locale_route(first_url: str, second_url: str) -> bool:
    if (
        _admin_controller_for_url(first_url) != "AdminBusinessProfile"
        or _admin_controller_for_url(second_url) != "AdminBusinessProfile"
    ):
        return False
    first = urlparse(first_url)
    second = urlparse(second_url)
    return (
        (first.scheme, first.hostname, first.port, first.path)
        == (second.scheme, second.hostname, second.port, second.path)
    )


def _diagnostic_bool(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def _diagnostic_status(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = int(value)
        if numeric == value and 100 <= numeric <= 599:
            return str(numeric)
    return "unknown"


def _safe_locale_document_state(driver: webdriver.Chrome) -> dict[str, str]:
    try:
        state = driver.execute_script(
            """
            const category = value => {
              if (typeof value !== 'string' || value.trim() === '') return 'none';
              return ['ko', 'ko-kr'].includes(value.trim().toLowerCase()) ? 'korean' : 'other';
            };
            const timing = performance.getEntriesByType('navigation')[0];
            const responseStatus = timing && Number.isInteger(timing.responseStatus)
              ? timing.responseStatus
              : null;
            return {
              document_lang: category(document.documentElement?.getAttribute('lang') ?? null),
              document_sw_controlled: Boolean(navigator.serviceWorker?.controller),
              navigation_worker_used: timing ? timing.workerStart > 0 : null,
              navigation_status: responseStatus
            };
            """
        )
    except Exception:
        return {
            "document_lang": "unavailable",
            "document_sw_controlled": "unknown",
            "navigation_worker_used": "unknown",
            "navigation_status": "unknown",
        }

    if not isinstance(state, dict):
        state = {}
    language = state.get("document_lang")
    if language not in {"korean", "other", "none"}:
        language = "unavailable"
    return {
        "document_lang": language,
        "document_sw_controlled": _diagnostic_bool(state.get("document_sw_controlled")),
        "navigation_worker_used": _diagnostic_bool(state.get("navigation_worker_used")),
        "navigation_status": _diagnostic_status(state.get("navigation_status")),
    }


def navigate_admin_locale_probe(driver: webdriver.Chrome, target_url: str) -> str:
    """Capture bounded metadata for the exact business profile document navigation."""
    if _admin_controller_for_url(target_url) != "AdminBusinessProfile":
        return "unavailable:invalid_diagnostic"

    header_name = "X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC"
    diagnostic_header = "missing"
    navigation_status = "unknown"
    navigation_route_match = False
    navigation_url_exact = False
    navigation_from_service_worker = "unknown"
    navigation_from_disk_cache = "unknown"
    navigation_from_prefetch_cache = "unknown"

    header_installed = False
    try:
        # Drain the login/settings request records before enabling the explicit
        # response probe for this one AdminBusinessProfile navigation.
        driver.get_log("performance")
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {header_name: "1"}})
        header_installed = True
    except Exception:
        # Still perform the real route navigation if Chrome diagnostics are unavailable.
        pass

    try:
        driver.get(target_url)
    finally:
        if header_installed:
            try:
                driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {}})
            except Exception:
                pass

    try:
        for entry in driver.get_log("performance"):
            try:
                message = json.loads(entry.get("message", "")).get("message", {})
                if message.get("method") != "Network.responseReceived":
                    continue
                params = message.get("params", {})
                if params.get("type") != "Document":
                    continue
                response = params.get("response", {})
                response_url = response.get("url")
                if not isinstance(response_url, str) or not _same_admin_locale_route(response_url, target_url):
                    continue

                # Keep only the last same-route Document response; raw CDP
                # entries, URLs, request IDs, headers, and tokens stay in memory.
                navigation_route_match = True
                navigation_url_exact = response_url == target_url
                navigation_status = _diagnostic_status(response.get("status"))
                navigation_from_service_worker = _diagnostic_bool(response.get("fromServiceWorker"))
                navigation_from_disk_cache = _diagnostic_bool(response.get("fromDiskCache"))
                navigation_from_prefetch_cache = _diagnostic_bool(response.get("fromPrefetchCache"))
                headers = response.get("headers", {})
                if isinstance(headers, dict):
                    for name, value in headers.items():
                        if isinstance(name, str) and name.lower() == header_name.lower() and isinstance(value, str):
                            diagnostic_header = value
                            break
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
    except Exception:
        # Instrumentation failure remains diagnostic-only; the unchanged Korean
        # document assertion below still decides whether the check passes.
        pass

    dom_state = _safe_locale_document_state(driver)
    metadata = (
        f"navigation_status={navigation_status};"
        f"navigation_route_match={_diagnostic_bool(navigation_route_match)};"
        f"navigation_url_exact={_diagnostic_bool(navigation_url_exact)};"
        f"navigation_from_service_worker={navigation_from_service_worker};"
        f"navigation_from_disk_cache={navigation_from_disk_cache};"
        f"navigation_from_prefetch_cache={navigation_from_prefetch_cache};"
        f"document_lang={dom_state['document_lang']};"
        f"document_sw_controlled={dom_state['document_sw_controlled']};"
        f"navigation_worker_used={dom_state['navigation_worker_used']}"
    )
    return parse_admin_locale_response_diagnostic(f"{diagnostic_header};{metadata}")


def generated_admin_controller_url(driver: webdriver.Chrome, controller: str) -> str:
    """Find a same-origin, employee-tokenized link for an installed custom controller."""
    for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller="]'):
        href = link.get_attribute("href") or ""
        actual = urlparse(href)
        expected = urlparse(BASE)
        admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
        query = parse_qs(actual.query, keep_blank_values=True)
        if query.get("controller") != [controller]:
            continue
        if (actual.scheme, actual.hostname, actual.port) != (
            expected.scheme,
            expected.hostname,
            expected.port,
        ) or not actual.path.startswith(admin_path + "/"):
            raise AssertionError(f"the generated {controller} link left the isolated Back Office")
        tokens = query.get("token", [])
        if len(tokens) != 1 or not tokens[0].strip():
            raise AssertionError(f"the generated {controller} link lacks the employee-scoped admin token")
        return href
    raise AssertionError(f"the full administrator cannot reach the {controller} screen")


def assert_korean_admin_locale(
    driver: webdriver.Chrome,
    route_label: str,
    navigation_diagnostic: str | None = None,
) -> None:
    document_locale = driver.find_element(By.TAG_NAME, "html").get_attribute("lang")
    if not isinstance(document_locale, str) or not is_korean_admin_language(document_locale):
        error = AssertionError(f"{route_label} did not force the Korean Back Office locale")
        error.admin_security_locale_flags = "korean=false"
        error.admin_security_locale_diagnostics = read_admin_locale_response_diagnostic(driver)
        error.admin_security_locale_navigation_diagnostics = navigation_diagnostic
        raise error


def safe_admin_orders_state(driver: webdriver.Chrome) -> str:
    """Classify only bounded, non-customer-specific signals from the orders page."""
    body_match_source_categories = "unknown"
    try:
        actual_url = urlparse(driver.current_url)
        admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
        orders_path = (
            "orders_list"
            if actual_url.path in {admin_path + "/sell/orders", admin_path + "/sell/orders/"}
            else "other"
        )
        performance_state = driver.execute_script(
            """
            const entry = performance.getEntriesByType('navigation')[0];
            return {
              http_status: entry && Number.isInteger(entry.responseStatus) ? entry.responseStatus : null,
              document_ready: document.readyState
            };
            """
        )
        http_status_value = (
            performance_state.get("http_status")
            if isinstance(performance_state, dict)
            else None
        )
        http_status = (
            str(http_status_value)
            if isinstance(http_status_value, int)
            and not isinstance(http_status_value, bool)
            and 100 <= http_status_value <= 599
            else "unknown"
        )
        ready_state_value = (
            performance_state.get("document_ready")
            if isinstance(performance_state, dict)
            else None
        )
        document_ready = (
            ready_state_value
            if ready_state_value in {"loading", "interactive", "complete"}
            else "unknown"
        )
        document_locale_value = driver.find_element(By.TAG_NAME, "html").get_attribute("lang")
        document_locale = "korean" if is_korean_admin_language(document_locale_value or "") else "other"
        login_form_visible = any(
            element.is_displayed()
            for element in driver.find_elements(By.CSS_SELECTOR, "#login_form")
        )
        body_text = driver.find_element(By.TAG_NAME, "body").text
        body_has_korean_order_label = "주문" in body_text
        body_text_state = "present" if body_text.strip() else "empty"
        lowered_body_text = body_text.casefold()
        permission_denied = any(
            marker in lowered_body_text
            for marker in (
                "access denied",
                "not authorized",
                "permission denied",
                "you are not allowed",
                "권한이 없습니다",
                "접근 권한",
                "접근할 수 없습니다",
            )
        )
        english_order_label = bool(re.search(r"\border(s)?\b", body_text, re.IGNORECASE))
        try:
            source_category_flags = driver.execute_script(
                r"""
                const orderLabelPattern = /\border(s)?\b/i;
                const isVisibleTextMatch = (element) => {
                  const style = window.getComputedStyle(element);
                  return element.getClientRects().length > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && orderLabelPattern.test(element.innerText || '');
                };
                const sourceSelectors = {
                  toolbar: ['.header-toolbar'],
                  breadcrumb: ['.breadcrumb', 'nav[aria-label="Breadcrumb"]'],
                  navigation: ['#nav-sidebar', '.nav-bar'],
                  kpi: ['.card-kpis', '.kpi-row'],
                  grid_header: ['.js-grid-panel thead'],
                  grid_controls: ['.js-grid-panel .js-grid-header', '.js-grid-panel .card-header'],
                  grid_actions: [
                    '.js-grid-panel .js-bulk-actions-btn',
                    '.js-grid-panel .dropdown-menu.show',
                    '.js-grid-panel .js-grid-actions'
                  ],
                  grid_body: ['.js-grid-panel tbody'],
                  modal: ['.modal.show', '[role="dialog"]'],
                  alert: ['[role="alert"]', '.alert'],
                  empty_state: ['.showcase-list-card']
                };
                return Object.fromEntries(Object.entries(sourceSelectors).map(([category, selectors]) => [
                  category,
                  selectors.some((selector) => Array.from(document.querySelectorAll(selector)).some(isVisibleTextMatch))
                ]));
                """
            )
            body_match_source_categories = format_orders_body_match_sources(
                source_category_flags,
                english_order_label,
            )
        except Exception:
            # Category instrumentation is diagnostic only; the strict assertion below remains decisive.
            body_match_source_categories = "unknown"
        heading_state = "missing"
        for heading in driver.find_elements(By.CSS_SELECTOR, ".header-toolbar h1.title"):
            if not heading.is_displayed():
                continue
            heading_text = heading.text
            if "주문" in heading_text:
                heading_state = "korean"
            elif re.search(r"\border(s)?\b", heading_text, re.IGNORECASE):
                heading_state = "english"
            else:
                heading_state = "other"
            break
        grid_heading_state = "missing"
        for heading in driver.find_elements(By.CSS_SELECTOR, ".js-grid-panel .card-header-title"):
            if not heading.is_displayed():
                continue
            heading_text = heading.text
            if "주문" in heading_text:
                grid_heading_state = "korean"
            elif re.search(r"\border(s)?\b", heading_text, re.IGNORECASE):
                grid_heading_state = "english"
            else:
                grid_heading_state = "other"
            break
        admin_shell_visible = any(
            element.is_displayed()
            for element in driver.find_elements(
                By.CSS_SELECTOR,
                "#main-div, #main-div .content-div",
            )
        )
        orders_grid_visible = any(
            element.is_displayed()
            for element in driver.find_elements(
                By.CSS_SELECTOR,
                "#main-div table.js-grid-table",
            )
        )
        orders_empty_state_visible = any(
            element.is_displayed()
            for element in driver.find_elements(By.CSS_SELECTOR, ".showcase-list-card")
        )
        empty_state_heading = " ".join(
            element.text
            for element in driver.find_elements(By.CSS_SELECTOR, ".showcase-list-card__header")
            if element.is_displayed()
        )
        empty_state_message = " ".join(
            element.text
            for element in driver.find_elements(By.CSS_SELECTOR, ".showcase-list-card__message")
            if element.is_displayed()
        )
        orders_empty_state_korean = (
            not orders_empty_state_visible
            or (
                "주문 관리" in empty_state_heading
                and "모든 주문" in empty_state_message
                and "주문 상태" in empty_state_message
            )
        )
        alert_visible = any(
            element.is_displayed()
            for element in driver.find_elements(By.CSS_SELECTOR, "[role='alert'], .alert-danger")
        )
        document_locale_state = document_locale
    except Exception:
        orders_path = "unknown"
        http_status = "unknown"
        document_ready = "unknown"
        document_locale_state = "unknown"
        login_form_visible = "unknown"
        admin_shell_visible = "unknown"
        body_text_state = "unknown"
        heading_state = "unknown"
        grid_heading_state = "unknown"
        orders_grid_visible = "unknown"
        orders_empty_state_visible = "unknown"
        orders_empty_state_korean = "unknown"
        permission_denied = "unknown"
        english_order_label = "unknown"
        body_match_source_categories = "unknown"
        alert_visible = "unknown"
        body_has_korean_order_label = "unknown"

    return (
        f"route=AdminOrders;orders_path={orders_path};http_status={http_status};"
        f"document_ready={document_ready};document_locale={document_locale_state};"
        f"login_form_visible={_diagnostic_bool(login_form_visible)};"
        f"admin_shell_visible={_diagnostic_bool(admin_shell_visible)};body_text={body_text_state};"
        f"orders_heading={heading_state};orders_grid_heading={grid_heading_state};"
        f"orders_grid_visible={_diagnostic_bool(orders_grid_visible)};"
        f"orders_empty_state_visible={_diagnostic_bool(orders_empty_state_visible)};"
        f"orders_empty_state_korean={_diagnostic_bool(orders_empty_state_korean)};"
        f"permission_denied={_diagnostic_bool(permission_denied)};"
        f"english_order_label={_diagnostic_bool(english_order_label)};"
        f"body_match_source_categories={body_match_source_categories};"
        f"alert_visible={_diagnostic_bool(alert_visible)};"
        f"body_has_korean_order_label={_diagnostic_bool(body_has_korean_order_label)}"
    )


def wait_for_korean_orders_label(driver: webdriver.Chrome) -> bool:
    """Wait for the visible Orders title and, when empty, its Korean empty-state copy."""
    def visible_text(browser: webdriver.Chrome, selector: str) -> list[str]:
        return [
            element.text
            for element in browser.find_elements(By.CSS_SELECTOR, selector)
            if element.is_displayed()
        ]

    def has_korean_order_labels(browser: webdriver.Chrome) -> bool:
        try:
            page_titles = visible_text(browser, ".header-toolbar h1.title")
            grid_titles = visible_text(browser, ".js-grid-panel .card-header-title")
            if not any("주문" in title for title in page_titles):
                return False
            if not any("주문" in title for title in grid_titles):
                return False
            body_text = browser.find_element(By.TAG_NAME, "body").text
            if re.search(r"\border(s)?\b", body_text, re.IGNORECASE):
                return False

            empty_state_visible = any(
                element.is_displayed()
                for element in browser.find_elements(By.CSS_SELECTOR, ".showcase-list-card")
            )
            if not empty_state_visible:
                return True

            empty_titles = visible_text(browser, ".showcase-list-card__header")
            empty_messages = visible_text(browser, ".showcase-list-card__message")
            return (
                any("주문 관리" in title for title in empty_titles)
                and any(
                    "모든 주문" in message and "주문 상태" in message
                    for message in empty_messages
                )
            )
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, 30).until(has_korean_order_labels)
    except TimeoutException:
        return False
    return True


def read_admin_locale_response_diagnostic(driver: webdriver.Chrome) -> str:
    try:
        driver.set_script_timeout(15)
        diagnostic = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            fetch(window.location.href, {
              cache: "no-store",
              credentials: "same-origin",
              redirect: "manual",
              headers: {"X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC": "1"}
            }).then(async response => {
              const requestUrl = new URL(window.location.href);
              let sameRoute = false;
              let urlExact = false;
              try {
                const responseUrl = new URL(response.url);
                sameRoute = responseUrl.origin === requestUrl.origin
                  && responseUrl.pathname === requestUrl.pathname
                  && requestUrl.searchParams.get("controller") === "AdminBusinessProfile"
                  && responseUrl.searchParams.get("controller") === "AdminBusinessProfile";
                urlExact = response.url === window.location.href;
              } catch (_) {
                // Keep URL details private; the safe boolean below records only the comparison.
              }
              const diagnosticHeader = response.type === "opaqueredirect"
                ? "redirect=opaque"
                : response.headers.get("X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC") || "missing";
              let responseHtmlLang = "unavailable";
              try {
                const responseBody = await response.text();
                const responseDocument = new DOMParser().parseFromString(responseBody, "text/html");
                const responseLang = responseDocument.documentElement?.getAttribute("lang");
                responseHtmlLang = typeof responseLang !== "string" || responseLang.trim() === ""
                  ? "none"
                  : ["ko", "ko-kr"].includes(responseLang.trim().toLowerCase()) ? "korean" : "other";
              } catch (_) {
                // Only the bounded category is returned; response content stays in memory.
              }
              const currentLang = document.documentElement?.getAttribute("lang");
              const documentLang = typeof currentLang !== "string" || currentLang.trim() === ""
                ? "none"
                : ["ko", "ko-kr"].includes(currentLang.trim().toLowerCase()) ? "korean" : "other";
              const navigation = performance.getEntriesByType("navigation")[0];
              const navigationStatus = navigation && Number.isInteger(navigation.responseStatus)
                ? navigation.responseStatus
                : "unknown";
              const controlled = Boolean(navigator.serviceWorker?.controller);
              const workerUsed = navigation ? navigation.workerStart > 0 : "unknown";
              done(`${diagnosticHeader};browser_status=${response.status};browser_type=${response.type};browser_redirected=${response.redirected};browser_same_route=${sameRoute};browser_url_exact=${urlExact};document_lang=${documentLang};response_html_lang=${responseHtmlLang};document_sw_controlled=${controlled};navigation_worker_used=${workerUsed};navigation_status=${navigationStatus}`);
            })
              .catch(error => done(`unavailable:${error.name}`));
            """
        )
    except Exception as error:
        error_type = type(error).__name__
        safe_error_type = error_type if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", error_type) else "Error"
        return f"unavailable:{safe_error_type}"

    return parse_admin_locale_response_diagnostic(
        diagnostic if isinstance(diagnostic, str) else None
    )


def login(driver: webdriver.Chrome, email: str) -> None:
    driver.get(ADMIN_LOGIN + "/login")
    visible(driver, '#login_form input[name="email"]').send_keys(email)
    visible(driver, '#login_form input[name="passwd"]').send_keys(ADMIN_PASSWORD)
    visible(driver, "#login_form button[type='submit'], #login_form input[type='submit']").click()
    try:
        WebDriverWait(driver, 30).until(_authenticated_admin_route_ready)
    except Exception as error:
        error.admin_security_navigation_state = _safe_admin_navigation_state_text(driver)
        raise


def settings_url(driver: webdriver.Chrome) -> str:
    links = WebDriverWait(driver, 30).until(
        lambda browser: [
            link
            for link in browser.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminBusinessProfile"]')
            if parse_qs(urlparse(link.get_attribute("href") or "").query).get("controller")
            == ["AdminBusinessProfile"]
        ]
    )
    href = links[0].get_attribute("href") or ""
    actual = urlparse(href)
    expected = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (actual.scheme, actual.hostname, actual.port) != (
        expected.scheme,
        expected.hostname,
        expected.port,
    ):
        raise AssertionError("business profile settings left the isolated shop origin")
    if not actual.path.startswith(admin_path + "/"):
        raise AssertionError("business profile settings left the isolated Back Office directory")
    return href


def emit_admin_post_login_state(driver: webdriver.Chrome, session: str) -> None:
    if session not in {"admin", "view_only"}:
        raise ValueError("unknown isolated administrator session label")
    state = _safe_admin_navigation_state_text(driver)
    message = f"session={session}; {state}"
    print(f"ORDENOWA_ADMIN_POST_LOGIN_STATE={message}", file=sys.stderr)
    print(f"::notice title=ORDENOWA admin post-login state::{message}", file=sys.stderr)


def current_setting(driver: webdriver.Chrome) -> str:
    return visible(driver, f'input[name="{SETTING_FIELD}"]').get_attribute("value") or ""


def current_draft_pointer(driver: webdriver.Chrome) -> str:
    for row in driver.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-history tbody tr"):
        if "현재 초안" not in row.text:
            continue
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        match = re.fullmatch(r"#([1-9][0-9]*)", cells[0].text.strip()) if cells else None
        if match is None:
            raise AssertionError("the current draft version row did not contain a valid version ID")
        return match.group(1)
    raise AssertionError("the business profile history did not identify the current draft version")


def validate_isolated_ci_project() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or not run_id.isascii()
        or not run_id.isdecimal()
        or not attempt.isascii()
        or not attempt.isdecimal()
        or not COMPOSE_PROJECT
        or COMPOSE_PROJECT != expected_project
        or os.environ.get("CI_COMPOSE_PROJECT_NAME", "") != expected_project
        or not ADMIN_EMAIL.strip().lower().endswith("@example.invalid")
        or not VIEW_ONLY_EMAIL.strip().lower().endswith("@example.invalid")
        or not DASHBOARD_VIEW_ONLY_EMAIL.strip().lower().endswith("@example.invalid")
    ):
        raise ValueError("admin security QA requires its exact isolated GitHub Actions Compose project")


def _loopback_http_origin(value: str, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must be a valid isolated loopback URL") from None
    if host.lower() == "localhost":
        loopback = True
    else:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    if (
        parsed.scheme != "http"
        or not loopback
        or port != EXPECTED_SHOP_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use the isolated loopback shop origin on port {EXPECTED_SHOP_PORT}")
    return parsed.scheme, host.lower(), port


def validate_loopback_admin_targets() -> None:
    shop = urlparse(BASE)
    if shop.path not in ("", "/"):
        raise ValueError("SHOP_BASE_URL must be the isolated shop root")
    shop_origin = _loopback_http_origin(BASE, "SHOP_BASE_URL")
    admin_origin = _loopback_http_origin(ADMIN_LOGIN, "ADMIN_LOGIN_URL")
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if admin_origin != shop_origin or not admin_path.startswith("/") or admin_path == "":
        raise ValueError("ADMIN_LOGIN_URL must share the isolated shop origin and name its Back Office path")


def submit_settings_attempt(driver: webdriver.Chrome, mode: str) -> dict[str, object]:
    script = """
        const mode = arguments[0];
        const sentinel = arguments[1];
        const adminBaseUrl = arguments[2];
        const done = arguments[arguments.length - 1];
        const form = document.querySelector('form.ordenowa-profile-settings');
        if (!form) {
          done({formPresent: false});
          return;
        }
        const data = new FormData(form);
        data.set('profile[brand][name][ko-KR]', sentinel);
        data.set('submitOrdenowaSaveDraft', '1');
        const action = new URL(form.action || window.location.href, window.location.href);
        if (mode === 'missing') {
          action.searchParams.delete('token');
          data.delete('token');
        } else if (mode === 'invalid') {
          action.searchParams.set('token', 'invalid-ci-security-token');
          data.set('token', 'invalid-ci-security-token');
        }
        fetch(action.href, {
          method: 'POST',
          body: data,
          credentials: 'same-origin',
          redirect: 'follow',
          cache: 'no-store'
        }).then(async response => {
          const responseBody = await response.text();
          const tokenPage = inspectInvalidTokenPage(responseBody, response.url, action.href);
          const nativeCompromisedPage = inspectNativeCompromisedPage(
            responseBody,
            response.url,
            action.href,
            adminBaseUrl
          );
          const responseDocument = new DOMParser().parseFromString(responseBody, 'text/html');
          const loginForm = responseDocument.querySelector('#login_form');
          done({
            formPresent: true,
            status: response.status,
            responseUrl: response.url,
            bodyHasSettingsForm: responseBody.includes('ordenowa-profile-settings'),
            bodyHasDangerAlert: responseBody.includes('alert-danger'),
            ...nativeCompromisedPage,
            ...tokenPage,
            bodyHasAdminLoginForm: Boolean(
              loginForm && loginForm.querySelector('input[name="email"]') && loginForm.querySelector('input[name="passwd"]')
            ),
            bodyHasViewOnlyDenial: responseBody.includes('설정 초안을 수정할 권한이 없습니다.')
          });
        })
          .catch(() => done({formPresent: true, status: 0}));
        """ + TOKEN_DOM_DETECTOR_JS
    result = driver.execute_async_script(
        script,
        mode,
        MUTATION_SENTINEL,
        ADMIN_LOGIN,
    )
    return result if isinstance(result, dict) else {"formPresent": False}


def verify_native_invalid_token_dom_fixture(driver: webdriver.Chrome) -> None:
    fixture = ROOT / "tests" / "fixtures" / "prestashop-9.2-invalid-token.html"
    markup = fixture.read_text(encoding="utf-8")
    action_url = ADMIN_LOGIN + "/index.php?controller=AdminBusinessProfile"
    variants = (
        ("native", markup, True),
        ("missing_warning", markup.replace('class="error-msg"', 'class="other"'), False),
        ("missing_continue", markup.replace("btn-continue", "other"), False),
        ("missing_cancel", markup.replace("btn-cancel", "other"), False),
        ("missing_recovery_token", markup.replace("&amp;token=fixture-token", ""), False),
        (
            "wrong_controller",
            markup.replace("controller=AdminBusinessProfile&amp;token", "controller=AdminDashboard&amp;token"),
            False,
        ),
        (
            "wrong_recovery_path",
            markup.replace("/admin-kuranea/index.php?controller=", "/admin-kuranea/other.php?controller="),
            False,
        ),
        (
            "external_recovery",
            markup.replace(
                "http://localhost:18080/admin-kuranea/",
                "http://outside.example/admin-kuranea/",
            ),
            False,
        ),
    )
    for name, body, expected in variants:
        result = driver.execute_script(
            TOKEN_DOM_DETECTOR_JS + "return inspectInvalidTokenPage(arguments[0], arguments[1], arguments[2]);",
            body,
            action_url,
            action_url,
        )
        if not isinstance(result, dict) or result.get("bodyHasInvalidTokenPage") is not expected:
            raise AssertionError(f"native invalid-token DOM detector fixture failed at {name}")


def verify_native_compromised_page_fixture(driver: webdriver.Chrome) -> None:
    fixture = ROOT / "tests" / "fixtures" / "prestashop-9.2-security-compromised.html"
    markup = fixture.read_text(encoding="utf-8")
    action_url = ADMIN_LOGIN + "/index.php?controller=AdminBusinessProfile"
    response_url = ADMIN_LOGIN + "/security/compromised"
    pretty_admin_links = markup.replace(
        "/admin-kuranea/index.php?controller=AdminBusinessProfile",
        "/admin-kuranea/improve/design/business-profile?controller=AdminBusinessProfile",
    ).replace(
        "/admin-kuranea/index.php?controller=AdminDashboard",
        "/admin-kuranea/sell/dashboard?controller=AdminDashboard",
    )
    variants = (
        ("native", markup, True),
        ("missing_page_marker", markup.replace("security-compromised-page", "other-page"), False),
        ("missing_warning", markup.replace('class="alert alert-danger"', 'class="alert"'), False),
        ("missing_warning_text", markup.replace('<p class="alert-text">', '<p class="other-text">'), False),
        ("missing_continue", markup.replace("btn-outline-danger", "other-button"), False),
        ("missing_dashboard", markup.replace("btn-primary", "other-button"), False),
        ("tokenless_request_link", markup, True),
        ("pretty_admin_request_path", pretty_admin_links, True),
        ("target_outside_admin_prefix", markup, False),
        ("external_request_origin", markup, False),
        (
            "tokenized_request_link",
            markup.replace(
                "controller=AdminBusinessProfile\">",
                "controller=AdminBusinessProfile&amp;_token=fixture-csrf-token\">",
            ),
            True,
        ),
        (
            "wrong_continue_controller",
            markup.replace('controller=AdminBusinessProfile">', 'controller=AdminDashboard">'),
            False,
        ),
        (
            "wrong_continue_path",
            markup.replace("/admin-kuranea/index.php?controller=AdminBusinessProfile", "/admin-kuranea/other.php?controller=AdminBusinessProfile"),
            False,
        ),
        (
            "external_continue",
            markup.replace("http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile", "http://outside.example/admin-kuranea/index.php?controller=AdminBusinessProfile"),
            False,
        ),
        (
            "missing_dashboard_token",
            markup.replace(
                "/index.php?controller=AdminDashboard&amp;token=fixture-token",
                "/index.php?controller=AdminDashboard",
            ),
            False,
        ),
        (
            "dashboard_symfony_token",
            markup.replace(
                "controller=AdminDashboard&amp;token=fixture-token",
                "controller=AdminDashboard&amp;_token=fixture-csrf-token",
            ),
            True,
        ),
        (
            "duplicate_dashboard_tokens",
            markup.replace(
                "controller=AdminDashboard&amp;token=fixture-token",
                "controller=AdminDashboard&amp;token=fixture-token&amp;_token=fixture-csrf-token",
            ),
            False,
        ),
        (
            "wrong_dashboard_controller",
            markup.replace("controller=AdminDashboard&amp;token", "controller=AdminBusinessProfile&amp;token"),
            False,
        ),
        (
            "wrong_dashboard_path",
            markup.replace("/admin-kuranea/index.php?controller=AdminDashboard", "/admin-kuranea/other.php?controller=AdminDashboard"),
            False,
        ),
        (
            "external_dashboard",
            markup.replace("http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard", "http://outside.example/admin-kuranea/index.php?controller=AdminDashboard"),
            False,
        ),
        ("wrong_response_path", markup, False),
    )
    for name, body, expected in variants:
        fixture_response_url = (
            response_url + "/other" if name == "wrong_response_path" else response_url
        )
        fixture_target_url = action_url
        if name == "pretty_admin_request_path":
            fixture_target_url = ADMIN_LOGIN + "/improve/design/business-profile?controller=AdminBusinessProfile"
        elif name == "target_outside_admin_prefix":
            fixture_target_url = BASE + "/admin-kuranea-evil/index.php?controller=AdminBusinessProfile"
        elif name == "external_request_origin":
            fixture_target_url = "http://outside.example/admin-kuranea/index.php?controller=AdminBusinessProfile"
        result = driver.execute_script(
            TOKEN_DOM_DETECTOR_JS + "return inspectNativeCompromisedPage(arguments[0], arguments[1], arguments[2], arguments[3]);",
            body,
            fixture_response_url,
            fixture_target_url,
            ADMIN_LOGIN,
        )
        if not isinstance(result, dict) or result.get("bodyHasNativeCompromisedPage") is not expected:
            raise AssertionError(f"native compromised-page DOM detector fixture failed at {name}")


def is_prestashop_admin_login_rejection(result: dict[str, object]) -> bool:
    if (
        result.get("status") != 200
        or result.get("bodyHasAdminLoginForm") is not True
        or result.get("bodyHasSettingsForm") is True
    ):
        return False

    response_url = result.get("responseUrl")
    if not isinstance(response_url, str):
        return False
    try:
        response_location = urlparse(response_url)
        base_location = urlparse(BASE)
    except ValueError:
        return False
    if (
        (response_location.scheme, response_location.hostname, response_location.port)
        != (base_location.scheme, base_location.hostname, base_location.port)
    ):
        return False

    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    controllers = parse_qs(response_location.query).get("controller", [])
    if response_location.path == admin_path + "/login":
        return not controllers or controllers == ["AdminLogin"]
    if response_location.path == admin_path + "/index.php":
        return controllers == ["AdminLogin"]
    return False


def is_prestashop_compromised_token_rejection(result: dict[str, object]) -> bool:
    if (
        result.get("status") != 200
        or result.get("bodyHasNativeCompromisedPage") is not True
        or result.get("bodyHasDangerAlert") is not True
        or result.get("bodyHasSettingsForm") is True
        or result.get("bodyHasAdminLoginForm") is True
        or result.get("bodyHasViewOnlyDenial") is True
    ):
        return False

    response_url = result.get("responseUrl")
    if not isinstance(response_url, str):
        return False
    try:
        response_location = urlparse(response_url)
        base_location = urlparse(BASE)
    except ValueError:
        return False
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    return (
        (response_location.scheme, response_location.hostname, response_location.port)
        == (base_location.scheme, base_location.hostname, base_location.port)
        and response_location.path == admin_path + "/security/compromised"
        and "controller" not in parse_qs(response_location.query)
    )


def response_classification(result: object) -> str:
    if not isinstance(result, dict):
        return "unavailable"
    if result.get("status") in (400, 401, 403):
        return "http_rejection"
    if result.get("bodyHasSettingsForm") is True and result.get("bodyHasDangerAlert") is True:
        return "business_profile_error"
    if is_prestashop_admin_login_rejection(result):
        return "prestashop_admin_login"
    if is_prestashop_compromised_token_rejection(result):
        return "prestashop_compromised_token"
    if (
        result.get("status") == 200
        and result.get("bodyHasInvalidTokenPage") is True
        and result.get("bodyHasSettingsForm") is not True
        and result.get("bodyHasAdminLoginForm") is not True
    ):
        try:
            location = urlparse(result.get("responseUrl", ""))
            base = urlparse(BASE)
            admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
            if (
                (location.scheme, location.hostname, location.port) == (base.scheme, base.hostname, base.port)
                and location.path == admin_path + "/index.php"
                and parse_qs(location.query).get("controller") == ["AdminBusinessProfile"]
            ):
                return "prestashop_invalid_token"
        except (TypeError, ValueError):
            pass
    return "unrecognized"


def response_summary(result: object) -> str:
    if not isinstance(result, dict):
        return "classification=unavailable; status=invalid; final_path=unavailable; settings_form=false; danger_alert=false; admin_login_form=false"
    response_url = result.get("responseUrl")
    final_path = "unavailable"
    if isinstance(response_url, str):
        try:
            final_path = re.sub(r"[^A-Za-z0-9/._-]", "?", urlparse(response_url).path or "/")[:160]
        except ValueError:
            final_path = "invalid"
    status_value = result.get("status")
    status_summary = (
        str(status_value)
        if isinstance(status_value, int) and not isinstance(status_value, bool)
        else "invalid"
    )
    try:
        response_controllers = parse_qs(urlparse(response_url).query).get("controller", []) if isinstance(response_url, str) else []
    except ValueError:
        response_controllers = []
    allowed_controllers = {"AdminBusinessProfile", "AdminDashboard", "AdminLogin"}
    if len(response_controllers) == 1 and response_controllers[0] in allowed_controllers:
        response_controller = response_controllers[0]
    else:
        response_controller = "other" if response_controllers else "none"

    def flag(name: str) -> str:
        return "true" if result.get(name) is True else "false"

    recovery_controller = result.get("invalidTokenRecoveryController")
    if not isinstance(recovery_controller, str) or recovery_controller not in allowed_controllers | {
        "none",
        "other",
        "unavailable",
    }:
        recovery_controller = "other"
    return (
        f"classification={response_classification(result)}; status={status_summary}; final_path={final_path}; "
        f"settings_form={flag('bodyHasSettingsForm')}; "
        f"danger_alert={flag('bodyHasDangerAlert')}; "
        f"admin_login_form={flag('bodyHasAdminLoginForm')}; "
        f"native_compromised_page={flag('bodyHasNativeCompromisedPage')}; "
        f"compromised_request_origin={flag('compromisedRequestSameOrigin')}; "
        f"compromised_request_path={flag('compromisedRequestInAdminPath')}; "
        f"compromised_marker={flag('compromisedPageMarker')}; "
        f"compromised_warning={flag('compromisedWarning')}; "
        f"compromised_continue={flag('compromisedContinueLink')}; "
        f"compromised_dashboard={flag('compromisedDashboardLink')}; "
        f"compromised_response_origin={flag('compromisedResponseSameOrigin')}; "
        f"compromised_response_path={flag('compromisedResponsePath')}; "
        f"compromised_continue_origin={flag('compromisedContinueSameOrigin')}; "
        f"compromised_continue_path={flag('compromisedContinuePath')}; "
        f"compromised_continue_controller={flag('compromisedContinueController')}; "
        f"compromised_continue_token={flag('compromisedContinueTokenPresent')}; "
        f"compromised_dashboard_origin={flag('compromisedDashboardSameOrigin')}; "
        f"compromised_dashboard_path={flag('compromisedDashboardPath')}; "
        f"compromised_dashboard_controller={flag('compromisedDashboardController')}; "
        f"compromised_dashboard_token={flag('compromisedDashboardTokenPresent')}; "
        f"response_controller={response_controller}; "
        f"invalid_token_warning={flag('bodyHasInvalidTokenWarning')}; "
        f"invalid_token_continue={flag('bodyHasInvalidTokenContinue')}; "
        f"invalid_token_cancel={flag('bodyHasInvalidTokenCancel')}; "
        f"recovery_same_origin={flag('invalidTokenRecoverySameOrigin')}; "
        f"recovery_same_path={flag('invalidTokenRecoverySamePath')}; "
        f"recovery_controller={recovery_controller}; "
        f"recovery_token_present={flag('invalidTokenRecoveryTokenPresent')}; "
        f"invalid_token_page={flag('bodyHasInvalidTokenPage')}"
    )


def raise_admin_security_response_failure(substage: str, result: object) -> None:
    error = AssertionError("admin security response classification failed")
    error.admin_security_substage = substage
    error.admin_security_response = response_summary(result)
    raise error


def assert_security_attempt_rejected(result: object, mode: str) -> None:
    if not isinstance(result, dict) or result.get("formPresent") is not True:
        raise_admin_security_response_failure("settings_form_missing", result)
    status = result.get("status")
    if not isinstance(status, int) or status < 200 or status >= 500:
        raise_admin_security_response_failure("response_status_unusable", result)
    if status == 404:
        raise_admin_security_response_failure("response_route_not_found", result)

    response_url = result.get("responseUrl")
    if not isinstance(response_url, str):
        raise_admin_security_response_failure("response_url_missing", result)
    try:
        response_location = urlparse(response_url)
        base_location = urlparse(BASE)
    except ValueError:
        raise_admin_security_response_failure("response_url_invalid", result)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (
        (response_location.scheme, response_location.hostname, response_location.port)
        != (base_location.scheme, base_location.hostname, base_location.port)
        or not response_location.path.startswith(admin_path + "/")
    ):
        raise_admin_security_response_failure("response_route_out_of_scope", result)

    framework_rejection = status in {400, 401, 403}
    admin_page_rejection = (
        result.get("bodyHasSettingsForm") is True
        and result.get("bodyHasDangerAlert") is True
    )
    login_gate_rejection = is_prestashop_admin_login_rejection(result)
    if mode == "view_only" and not framework_rejection and result.get("bodyHasViewOnlyDenial") is not True:
        raise_admin_security_response_failure("view_only_denial_missing", result)
    if mode in {"missing", "invalid"} and not (
        framework_rejection or admin_page_rejection or login_gate_rejection
        or response_classification(result) in {
            "prestashop_invalid_token",
            "prestashop_compromised_token",
        }
    ):
        raise_admin_security_response_failure(f"{mode}_token_rejection_unrecognized", result)


def assert_draft_pointer_unchanged(driver: webdriver.Chrome, expected: str, label: str) -> None:
    actual = current_draft_pointer(driver)
    if actual != expected:
        error = AssertionError(f"{label} changed the business profile draft version pointer")
        error.admin_security_state_check = "draft_pointer_mismatch"
        raise error


def assert_setting_unchanged(
    driver: webdriver.Chrome,
    expected: str,
    expected_draft_pointer: str,
    label: str,
) -> None:
    page = settings_url(driver)
    driver.get(page)
    visible(driver, "form.ordenowa-profile-settings")
    actual = current_setting(driver)
    if actual != expected:
        error = AssertionError(f"{label} changed a saved Korean brand setting")
        error.admin_security_state_check = "setting_value_mismatch"
        raise error
    assert_draft_pointer_unchanged(driver, expected_draft_pointer, label)
    driver.save_screenshot(str(DEST / f"admin-security-{label}.png"))


def verify_security_attempt_without_mutation(
    driver: webdriver.Chrome,
    mode: str,
    expected_value: str,
    expected_draft_pointer: str,
    label: str,
) -> None:
    response = None
    request_error = None
    try:
        response = submit_settings_attempt(driver, mode)
    except Exception as error:
        request_error = error

    try:
        assert_setting_unchanged(driver, expected_value, expected_draft_pointer, label)
    except Exception as state_error:
        failure = AssertionError("admin security no-mutation state recheck failed")
        state_check = getattr(state_error, "admin_security_state_check", "state_recheck_failed")
        if state_check not in {"setting_value_mismatch", "draft_pointer_mismatch"}:
            state_check = "state_recheck_failed"
        failure.admin_security_substage = state_check
        failure.admin_security_request = (
            f"failed:{type(request_error).__name__}" if request_error is not None else "completed"
        )
        failure.admin_security_state_recheck = f"failed:{type(state_error).__name__}"
        failure.admin_security_response = "not_evaluated"
        raise failure from state_error

    if request_error is not None:
        failure = AssertionError("admin security browser request failed")
        failure.admin_security_substage = "request_execution"
        failure.admin_security_request = f"failed:{type(request_error).__name__}"
        failure.admin_security_state_recheck = "passed"
        failure.admin_security_response = "not_evaluated"
        raise failure from request_error
    try:
        assert_security_attempt_rejected(response, mode)
    except Exception as error:
        error.admin_security_request = "completed"
        error.admin_security_state_recheck = "passed"
        if not hasattr(error, "admin_security_response"):
            error.admin_security_response = f"classification_error:{type(error).__name__}"
        raise


def new_driver(enable_performance_logging: bool = False) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    if enable_performance_logging:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return webdriver.Chrome(options=options)


def close_browser_drivers(drivers, primary_failure: bool) -> bool:
    cleanup_ok = True
    for label, driver in drivers:
        if driver is None:
            continue
        try:
            driver.quit()
        except Exception as error:
            cleanup_ok = False
            error_type = type(error).__name__
            if not error_type.isidentifier():
                error_type = "unexpected exception"
            stage = f"{label}_chrome_shutdown"
            if primary_failure:
                print(
                    f"WARNING: isolated admin browser cleanup failed at {stage} ({error_type}) after the primary failure.",
                    file=sys.stderr,
                )
            else:
                print(f"FAIL: isolated admin security check at {stage} ({error_type})", file=sys.stderr)
                print(
                    f"::error title=ORDENOWA admin security browser QA::stage={stage}; exception={error_type}",
                    file=sys.stderr,
                )
    return cleanup_ok


def run() -> bool:
    stage = "isolated_ci_guard"
    admin_driver = None
    restricted_driver = None
    primary_failure = False
    completed = False
    try:
        validate_isolated_ci_project()
        validate_loopback_admin_targets()
        stage = "admin_browser_start"
        admin_driver = new_driver(enable_performance_logging=True)
        stage = "admin_token_dom_fixture"
        verify_native_invalid_token_dom_fixture(admin_driver)
        verify_native_compromised_page_fixture(admin_driver)
        stage = "admin_login"
        login(admin_driver, ADMIN_EMAIL)
        stage = "admin_settings_load"
        admin_settings_url = settings_url(admin_driver)
        admin_driver.get(admin_settings_url)
        visible(admin_driver, "form.ordenowa-profile-settings")
        original_value = current_setting(admin_driver)
        original_draft_pointer = current_draft_pointer(admin_driver)

        for mode in ("missing", "invalid"):
            stage = f"admin_{mode}_token_post"
            verify_security_attempt_without_mutation(
                admin_driver,
                mode,
                original_value,
                original_draft_pointer,
                f"{mode}-token",
            )

        legacy_admin_screens = (
            ("AdminBusinessProfile", admin_settings_url, "브랜드·로고", "admin-security-legacy-profile-korean.png"),
            ("AdminBusinessProfileBanks", None, "은행 계좌", "admin-security-legacy-bank-accounts-korean.png"),
            ("AdminOrdenowaProductManager", None, "새 상품 등록", "admin-security-legacy-product-manager-korean.png"),
            ("AdminKuraneaCatalogReview", None, "상품 검수 대기열", "admin-security-legacy-catalog-review-korean.png"),
        )
        for controller, route_url, content_marker, screenshot in legacy_admin_screens:
            stage = f"admin_legacy_{controller.lower()}_route"
            navigation_diagnostic = None
            if controller == "AdminBusinessProfile":
                navigation_diagnostic = navigate_admin_locale_probe(admin_driver, route_url or "")
            else:
                admin_driver.get(route_url or generated_admin_controller_url(admin_driver, controller))
            WebDriverWait(admin_driver, 30).until(
                lambda browser: parse_qs(urlparse(browser.current_url).query).get("controller") == [controller]
            )
            if any(element.is_displayed() for element in admin_driver.find_elements(By.CSS_SELECTOR, "#login_form")):
                raise AssertionError(f"the {controller} route returned to the Back Office login form")
            if content_marker not in admin_driver.find_element(By.TAG_NAME, "body").text:
                raise AssertionError(f"the {controller} route is missing its Korean screen marker")
            stage = f"admin_legacy_{controller.lower()}_korean_locale"
            assert_korean_admin_locale(admin_driver, controller, navigation_diagnostic)
            admin_driver.save_screenshot(str(DEST / screenshot))

        stage = "view_only_employee_login"
        restricted_driver = new_driver()
        login(restricted_driver, VIEW_ONLY_EMAIL)
        stage = "view_only_employee_post_login_state"
        emit_admin_post_login_state(restricted_driver, "view_only")
        # The fixture's permitted default tab makes PrestaShop generate this
        # employee's own tokenized settings URL at login. Do not reuse the full
        # administrator's menu link or token for the restricted session.
        stage = "view_only_employee_settings_route"
        restricted_settings_url = current_profile_settings_url(restricted_driver)
        stage = "view_only_employee_direct_route"
        restricted_driver.get(restricted_settings_url)
        stage = "view_only_employee_settings_form_visible"
        visible(restricted_driver, "form.ordenowa-profile-settings")
        stage = "view_only_employee_settings_korean_label"
        if "브랜드·로고" not in restricted_driver.find_element(By.TAG_NAME, "body").text:
            raise AssertionError("Korean locale: the view-only profile page is missing Korean settings labels")
        stage = "view_only_employee_settings_document_locale"
        assert_korean_admin_locale(restricted_driver, "view-only profile settings")
        restricted_driver.save_screenshot(str(DEST / "admin-security-view-only-settings-korean.png"))

        stage = "view_only_employee_orders_korean_locale"
        orders_links = [
            link
            for link in restricted_driver.find_elements(By.CSS_SELECTOR, "a[href]")
            if is_admin_orders_list_url(link.get_attribute("href") or "")
        ]
        if not orders_links:
            error = AssertionError("the view-only employee cannot reach the permitted admin orders list")
            error.admin_security_orders_link_state = safe_admin_orders_link_state(restricted_driver)
            raise error
        restricted_driver.get(orders_links[0].get_attribute("href"))
        WebDriverWait(restricted_driver, 30).until(
            lambda browser: _admin_controller_for_url(browser.current_url) == "AdminOrders"
        )
        assert_korean_admin_locale(restricted_driver, "view-only orders")
        orders_label_ready = wait_for_korean_orders_label(restricted_driver)
        restricted_driver.save_screenshot(str(DEST / "admin-security-view-only-orders-korean.png"))
        if not orders_label_ready:
            error = AssertionError("Korean locale: the orders list is missing Korean order labels")
            error.admin_security_orders_state = safe_admin_orders_state(restricted_driver)
            raise error

        stage = "view_only_employee_settings_restore"
        restricted_driver.get(restricted_settings_url)
        visible(restricted_driver, "form.ordenowa-profile-settings")
        assert_korean_admin_locale(restricted_driver, "view-only profile settings after orders navigation")
        stage = "view_only_employee_settings_value"
        restricted_original_value = current_setting(restricted_driver)
        stage = "view_only_employee_draft_pointer"
        restricted_draft_pointer = current_draft_pointer(restricted_driver)
        stage = "view_only_employee_valid_token_post"
        verify_security_attempt_without_mutation(
            restricted_driver,
            "view_only",
            restricted_original_value,
            restricted_draft_pointer,
            "view-only",
        )

        stage = "storefront_stays_japanese_after_admin_locale_test"
        restricted_driver.delete_all_cookies()
        restricted_driver.get(BASE + "/")
        storefront_locale = (restricted_driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
        if not storefront_locale.startswith("ja"):
            raise AssertionError("the Back Office Korean locale setting changed the Japanese-first storefront locale")

        stage = "view_only_dashboard_employee_login"
        login(restricted_driver, DASHBOARD_VIEW_ONLY_EMAIL)
        stage = "view_only_employee_dashboard_post_login_state"
        emit_admin_post_login_state(restricted_driver, "view_only")
        stage = "view_only_employee_dashboard_route"
        if _admin_controller_for_url(restricted_driver.current_url) != "AdminDashboard":
            raise AssertionError("the permitted view-only employee did not open its configured Dashboard tab")
        stage = "view_only_employee_dashboard_korean_locale"
        assert_korean_admin_locale(restricted_driver, "view-only dashboard")
        WebDriverWait(restricted_driver, 15).until(
            lambda browser: "시작일" in browser.find_element(By.TAG_NAME, "body").text
            and "종료일" in browser.find_element(By.TAG_NAME, "body").text
        )
        restricted_driver.save_screenshot(str(DEST / "admin-security-view-only-dashboard-korean.png"))

        completed = True
    except Exception as error:
        primary_failure = True
        error_type = type(error).__name__
        if not error_type.isidentifier():
            error_type = "unexpected exception"
        print(f"FAIL: isolated admin security check at {stage} ({error_type})", file=sys.stderr)
        print(f"ORDENOWA_ADMIN_SECURITY_STAGE={stage}", file=sys.stderr)
        diagnostic_substage = getattr(error, "admin_security_substage", None)
        diagnostic_response = getattr(error, "admin_security_response", None)
        diagnostic_request = getattr(error, "admin_security_request", None)
        diagnostic_state = getattr(error, "admin_security_state_recheck", None)
        diagnostic_navigation_state = getattr(error, "admin_security_navigation_state", None)
        diagnostic_locale_flags = getattr(error, "admin_security_locale_flags", None)
        diagnostic_locale_response = getattr(error, "admin_security_locale_diagnostics", None)
        diagnostic_locale_navigation = getattr(error, "admin_security_locale_navigation_diagnostics", None)
        diagnostic_orders_state = getattr(error, "admin_security_orders_state", None)
        diagnostic_orders_link_state = getattr(error, "admin_security_orders_link_state", None)
        safe_fields = []
        safe_response = False
        if isinstance(diagnostic_locale_flags, str) and re.fullmatch(
            r"korean=false",
            diagnostic_locale_flags,
        ):
            safe_fields.append(f"profile_locale={diagnostic_locale_flags}")
        if isinstance(diagnostic_locale_response, str) and re.fullmatch(
            SAFE_ADMIN_LOCALE_RESPONSE_PATTERN,
            diagnostic_locale_response,
        ):
            safe_fields.append(f"locale_response={diagnostic_locale_response}")
        if isinstance(diagnostic_locale_navigation, str) and re.fullmatch(
            SAFE_ADMIN_LOCALE_RESPONSE_PATTERN,
            diagnostic_locale_navigation,
        ):
            safe_fields.append(f"locale_navigation={diagnostic_locale_navigation}")
        if isinstance(diagnostic_substage, str) and re.fullmatch(r"[a-z0-9_]+", diagnostic_substage):
            safe_fields.append(f"substage={diagnostic_substage}")
        if isinstance(diagnostic_request, str) and re.fullmatch(
            r"(?:completed|failed:[A-Za-z][A-Za-z0-9]*)", diagnostic_request
        ):
            safe_fields.append(f"request={diagnostic_request}")
        if isinstance(diagnostic_state, str) and re.fullmatch(
            r"(?:passed|failed:[A-Za-z][A-Za-z0-9]*)", diagnostic_state
        ):
            safe_fields.append(f"state_recheck={diagnostic_state}")
        if isinstance(diagnostic_navigation_state, str) and re.fullmatch(
            SAFE_ADMIN_NAVIGATION_STATE_PATTERN,
            diagnostic_navigation_state,
        ):
            safe_fields.append(f"navigation={diagnostic_navigation_state}")
        if isinstance(diagnostic_orders_state, str) and re.fullmatch(
            SAFE_ADMIN_ORDERS_STATE_PATTERN,
            diagnostic_orders_state,
        ):
            safe_fields.append(f"orders_page={diagnostic_orders_state}")
        if isinstance(diagnostic_orders_link_state, str) and re.fullmatch(
            SAFE_ADMIN_ORDERS_LINK_PATTERN,
            diagnostic_orders_link_state,
        ):
            safe_fields.append(f"orders_links={diagnostic_orders_link_state}")
        if isinstance(diagnostic_response, str) and (
            diagnostic_response == "not_evaluated"
            or re.fullmatch(r"classification_error:[A-Za-z][A-Za-z0-9]*", diagnostic_response)
            or re.fullmatch(SAFE_ADMIN_SECURITY_RESPONSE_PATTERN, diagnostic_response)
        ):
            safe_fields.append(f"response={diagnostic_response}")
            safe_response = True
        safe_diagnostic = f"; {'; '.join(safe_fields)}" if safe_fields else ""
        if safe_fields:
            print(f"ORDENOWA_ADMIN_SECURITY_DIAGNOSTIC={'; '.join(safe_fields)}", file=sys.stderr)
        if isinstance(diagnostic_substage, str) and re.fullmatch(r"[a-z0-9_]+", diagnostic_substage):
            print(f"ORDENOWA_ADMIN_SECURITY_SUBSTAGE={diagnostic_substage}", file=sys.stderr)
        if isinstance(diagnostic_orders_state, str) and re.fullmatch(
            SAFE_ADMIN_ORDERS_STATE_PATTERN,
            diagnostic_orders_state,
        ):
            print(f"ORDENOWA_ADMIN_ORDERS_STATE={diagnostic_orders_state}", file=sys.stderr)
        if isinstance(diagnostic_orders_link_state, str) and re.fullmatch(
            SAFE_ADMIN_ORDERS_LINK_PATTERN,
            diagnostic_orders_link_state,
        ):
            print(f"ORDENOWA_ADMIN_ORDERS_LINKS={diagnostic_orders_link_state}", file=sys.stderr)
        if safe_response:
            print(f"ORDENOWA_ADMIN_SECURITY_RESPONSE={diagnostic_response}", file=sys.stderr)
        print(
            f"::error title=ORDENOWA admin security browser QA::stage={stage}; exception={error_type}{safe_diagnostic}",
            file=sys.stderr,
        )
    finally:
        cleanup_ok = close_browser_drivers(
            (("admin", admin_driver), ("restricted", restricted_driver)),
            primary_failure,
        )

    if completed and cleanup_ok and not primary_failure:
        print(
            "PASS: Back Office rejects missing and invalid admin tokens and a view-only employee cannot save settings"
        )
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
