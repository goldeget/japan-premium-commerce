#!/usr/bin/env python3
"""Exercise real Back Office authorization and CSRF rejection in isolated CI."""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
VIEW_ONLY_EMAIL = os.environ["VIEW_ONLY_EMPLOYEE_EMAIL"]
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
    r"response_controller=(?:AdminBusinessProfile|AdminDashboard|AdminLogin|none|other); "
    r"invalid_token_warning=(?:true|false); invalid_token_continue=(?:true|false); "
    r"invalid_token_cancel=(?:true|false); recovery_same_origin=(?:true|false); "
    r"recovery_same_path=(?:true|false); "
    r"recovery_controller=(?:AdminBusinessProfile|AdminDashboard|AdminLogin|none|other|unavailable); "
    r"recovery_token_present=(?:true|false); invalid_token_page=(?:true|false)"
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

function inspectNativeCompromisedPage(body, responseUrl, targetUrl) {
  const responseDocument = new DOMParser().parseFromString(body, 'text/html');
  const page = responseDocument.querySelector('#security-compromised-page');
  if (!page) return false;

  const warning = page.querySelector('.alert.alert-danger[role="alert"] .alert-text');
  const continueLink = page.querySelector('a.btn-outline-danger[href]');
  const dashboardLink = page.querySelector('a.btn-primary[href]');
  if (!warning || !warning.textContent.trim() || !continueLink || !dashboardLink) return false;

  try {
    const response = new URL(responseUrl);
    const target = new URL(targetUrl);
    const base = new URL(target.origin);
    const adminPath = target.pathname.split('/index.php')[0].replace(/\/$/, '');
    const continueUrl = new URL(continueLink.getAttribute('href'), responseUrl);
    const dashboardUrl = new URL(dashboardLink.getAttribute('href'), responseUrl);
    return response.origin === base.origin
      && continueUrl.origin === base.origin
      && dashboardUrl.origin === base.origin
      && continueUrl.pathname === adminPath + '/index.php'
      && dashboardUrl.pathname === adminPath + '/index.php'
      && continueUrl.searchParams.get('controller') === 'AdminBusinessProfile'
      && dashboardUrl.searchParams.get('controller') === 'AdminDashboard'
      && Boolean(dashboardUrl.searchParams.get('token'));
  } catch (_) {
    return false;
  }
}
"""


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def login(driver: webdriver.Chrome, email: str) -> None:
    driver.get(ADMIN_LOGIN + "/login")
    visible(driver, '#login_form input[name="email"]').send_keys(email)
    visible(driver, '#login_form input[name="passwd"]').send_keys(ADMIN_PASSWORD)
    visible(driver, "#login_form button[type='submit'], #login_form input[type='submit']").click()
    WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)


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
          const nativeCompromisedPage = inspectNativeCompromisedPage(responseBody, response.url, action.href);
          const responseDocument = new DOMParser().parseFromString(responseBody, 'text/html');
          const loginForm = responseDocument.querySelector('#login_form');
          done({
            formPresent: true,
            status: response.status,
            responseUrl: response.url,
            bodyHasSettingsForm: responseBody.includes('ordenowa-profile-settings'),
            bodyHasDangerAlert: responseBody.includes('alert-danger'),
            bodyHasNativeCompromisedPage: nativeCompromisedPage,
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
    action_url = ADMIN_LOGIN + "/index.php?controller=AdminBusinessProfile&token=fixture-token"
    response_url = ADMIN_LOGIN + "/security/compromised"
    variants = (
        ("native", markup, True),
        ("missing_page_marker", markup.replace("security-compromised-page", "other-page"), False),
        ("missing_warning", markup.replace('class="alert alert-danger"', 'class="alert"'), False),
        ("missing_continue", markup.replace("btn-outline-danger", "other-button"), False),
        ("missing_dashboard", markup.replace("btn-primary", "other-button"), False),
        (
            "missing_request_token",
            markup.replace(
                "/index.php?controller=AdminBusinessProfile&amp;token=fixture-token",
                "/index.php?controller=AdminBusinessProfile",
            ),
            True,
        ),
        ("external_continue", markup.replace("http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile", "http://outside.example/admin-kuranea/index.php?controller=AdminBusinessProfile"), False),
        (
            "missing_dashboard_token",
            markup.replace(
                "/index.php?controller=AdminDashboard&amp;token=fixture-token",
                "/index.php?controller=AdminDashboard",
            ),
            False,
        ),
    )
    for name, body, expected in variants:
        result = driver.execute_script(
            TOKEN_DOM_DETECTOR_JS + "return inspectNativeCompromisedPage(arguments[0], arguments[1], arguments[2]);",
            body,
            response_url,
            action_url,
        )
        if result is not expected:
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


def new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
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
        admin_driver = new_driver()
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

        stage = "view_only_employee_login"
        restricted_driver = new_driver()
        login(restricted_driver, VIEW_ONLY_EMAIL)
        stage = "view_only_employee_settings_load"
        restricted_settings_url = settings_url(restricted_driver)
        restricted_driver.get(restricted_settings_url)
        visible(restricted_driver, "form.ordenowa-profile-settings")
        restricted_original_value = current_setting(restricted_driver)
        restricted_draft_pointer = current_draft_pointer(restricted_driver)
        stage = "view_only_employee_valid_token_post"
        verify_security_attempt_without_mutation(
            restricted_driver,
            "view_only",
            restricted_original_value,
            restricted_draft_pointer,
            "view-only",
        )

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
        safe_fields = []
        safe_response = False
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
