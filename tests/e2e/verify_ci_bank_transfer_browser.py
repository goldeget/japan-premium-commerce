#!/usr/bin/env python3
"""Issue and confirm one synthetic bank transfer in the isolated PrestaShop shop."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


SAFE_STAGES = {
    "context", "admin_login", "transfer_menu", "instruction_issue", "instruction_readback",
    "customer_login", "customer_order_readback", "customer_order_product_line", "foreign_customer_denial", "receipt_confirmation",
    "csrf_rejected", "wrong_amount_rejected", "limited_staff_denial", "customer_paid_readback",
    "receipt_replay", "native_readback", "complete",
}
SAFE_SUBSTAGES = {
    "none", "native_unpaid_order_readback", "transfer_link_scan", "orders_toggle_scan",
    "orders_menu_expand", "orders_menu_link_wait", "expanded_transfer_link_readback",
    "unique_transfer_link", "menu_link_token", "transfer_route_navigation",
    "transfer_order_row_readback", "csrf_form_missing", "csrf_form_ambiguous", "csrf_control_validation",
    "csrf_invalid_token_submit", "csrf_rejection_readback", "csrf_unissued_db_readback",
    "instruction_issue_navigation", "instruction_issue_order_row_readback", "instruction_issue_action_controls",
    "instruction_issue_submit", "instruction_issue_notice_readback", "instruction_issue_db_readback",
    "instruction_issue_profile_gate_evidence",
    "instruction_issue_notice_unpaid_present_success", "instruction_issue_notice_unpaid_missing_success",
    "instruction_issue_notice_unpaid_present_danger", "instruction_issue_notice_unpaid_missing_danger",
    "instruction_issue_notice_unpaid_present_missing", "instruction_issue_notice_unpaid_missing_missing",
    "instruction_issue_notice_unpaid_present_other", "instruction_issue_notice_unpaid_missing_other",
    "limited_staff_login", "limited_route_fixture_readback", "limited_route_helper_copy",
    "limited_route_helper_execution", "limited_route_helper_json_parse", "limited_route_helper_json_shape",
    "limited_route_helper_result_contract", "limited_route_scope_validation",
    "limited_route_bootstrap", "limited_route_employee_lookup", "limited_route_employee_active",
    "limited_route_transfer_tab_acl", "limited_route_admin_link_generation",
    "limited_route_route_validation", "limited_route_contract_readback",
    "limited_route_identity_validation", "limited_order_row_readback", "limited_issue_post",
    "limited_issue_denial_readback", "limited_issue_unpaid_db_readback", "limited_confirmation_post",
    "limited_confirmation_denial_readback", "limited_confirmation_unpaid_db_readback",
}
SAFE_EXCEPTION_TYPES = {
    "AssertionError", "TimeoutException", "ValueError", "RuntimeError", "OSError",
    "WebDriverException", "StaleElementReferenceException", "ElementClickInterceptedException",
    "NoSuchElementException", "OtherError",
}
SAFE_RESULT_KEYS = {
    "status", "stage", "exception_type", "failure_substage", "fixture_bound", "instruction_issued",
    "issue_persistence_diagnostic", "issue_failure_category", "issue_form_csrf_consistent",
    "issue_server_csrf_evidence_present", "issue_post_value_present", "issue_post_matches_controller",
    "issue_query_matches_controller", "issue_post_matches_query", "issue_controller_matches_admin_link",
    "issue_post_native_csrf_valid",
    "issue_server_profile_evidence_present", "issue_profile_readback_succeeded", "issue_published_profile_present",
    "issue_bank_transfer_enabled", "issue_selected_active_account_present", "issue_isolated_ci_gate_enabled",
    "issue_seller_commerce_gate_enabled", "issue_effective_commerce_gate_enabled",
    "issue_left_order_unpaid", "instruction_immutable", "customer_instruction_visible",
    "order_identity_match", "order_product_line_match", "amount_match", "account_match", "foreign_customer_denied",
    "limited_staff_denied", "view_only_issue_denied", "view_only_issue_order_unpaid",
    "view_only_confirmation_denied", "view_only_confirmation_order_unpaid",
    "limited_route_ci_scope_valid", "limited_route_identity_shape_valid",
    "limited_route_employee_found", "limited_route_employee_active",
    "limited_route_transfer_tab_present", "limited_route_view_allowed",
    "limited_route_issue_denied", "limited_route_confirm_denied",
    "limited_route_admin_link_generated", "limited_route_path_valid",
    "limited_route_controller_valid", "limited_route_credential_present",
    "limited_route_credential_bounded", "limited_route_credential_whitespace_free",
    "issue_csrf_rejected", "csrf_rejected", "wrong_amount_rejected", "receipt_confirmed",
    "idempotent_replay", "customer_paid_state_changed", "instruction_hidden_after_payment",
    "native_readback",
}
SAFE_ISSUE_PERSISTENCE_DIAGNOSTICS = {
    "not_run", "unpaid_instruction_absent", "unpaid_instruction_persisted", "unexpected_state", "unavailable",
}
SAFE_ISSUE_FAILURE_CATEGORIES = {
    "not_run", "csrf_rejected", "csrf_field_missing", "csrf_field_mismatch",
    "invalid_http_method", "issue_permission_denied", "order_scope_rejected",
    "wrong_payment_module", "invalid_unpaid_order", "profile_account_gate",
    "employee_missing", "issuer_validation_error", "instruction_persistence_error",
    "existing_instruction_mismatch", "unclassified_notice",
}
LIMITED_ROUTE_CHECK_KEYS = {
    "ci_scope_valid": "limited_route_ci_scope_valid",
    "identity_shape_valid": "limited_route_identity_shape_valid",
    "employee_found": "limited_route_employee_found",
    "employee_active": "limited_route_employee_active",
    "transfer_tab_present": "limited_route_transfer_tab_present",
    "view_allowed": "limited_route_view_allowed",
    "issue_denied": "limited_route_issue_denied",
    "confirm_denied": "limited_route_confirm_denied",
    "admin_link_generated": "limited_route_admin_link_generated",
    "route_path_valid": "limited_route_path_valid",
    "route_controller_valid": "limited_route_controller_valid",
    "route_credential_present": "limited_route_credential_present",
    "route_credential_bounded": "limited_route_credential_bounded",
    "route_credential_whitespace_free": "limited_route_credential_whitespace_free",
}
LIMITED_ROUTE_FAILURE_SUBSTAGES = {
    "scope_validation": "limited_route_scope_validation",
    "bootstrap": "limited_route_bootstrap",
    "employee_lookup": "limited_route_employee_lookup",
    "employee_active": "limited_route_employee_active",
    "transfer_tab_acl": "limited_route_transfer_tab_acl",
    "admin_link_generation": "limited_route_admin_link_generation",
    "route_validation": "limited_route_route_validation",
}
RESULT_BOOLEAN_KEYS = SAFE_RESULT_KEYS - {
    "status", "stage", "exception_type", "failure_substage", "issue_persistence_diagnostic",
    "issue_failure_category",
}
CSRF_DIAGNOSTIC_BOOLEAN_KEYS = {
    "issue_post_matches_controller", "issue_query_matches_controller", "issue_controller_matches_admin_link",
}
OPTIONAL_SUCCESS_DIAGNOSTIC_BOOLEAN_KEYS = CSRF_DIAGNOSTIC_BOOLEAN_KEYS | {
    # The seller authorization gate can remain closed while the exact run-scoped
    # isolated checkout gate authorizes this synthetic acceptance.
    "issue_seller_commerce_gate_enabled",
}
SUCCESS_REQUIRED_BOOLEAN_KEYS = RESULT_BOOLEAN_KEYS - OPTIONAL_SUCCESS_DIAGNOSTIC_BOOLEAN_KEYS


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_loopback_endpoint(value: str, port: int, label: str) -> str:
    parsed = urlparse(value)
    try:
        loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = False
    if (parsed.scheme != "http" or not loopback or parsed.port != port
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError(f"{label} must use the isolated loopback port {port}")
    return value.rstrip("/")


def same_origin(first: str, second: str) -> bool:
    a, b = urlparse(first), urlparse(second)
    return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def safe_admin_path(value: str, admin_root: str) -> bool:
    candidate, expected = urlparse(urljoin(admin_root.rstrip("/") + "/", value)), urlparse(admin_root)
    root = expected.path.rstrip("/")
    return ((candidate.scheme, candidate.hostname, candidate.port)
            == (expected.scheme, expected.hostname, expected.port)
            and (candidate.path == root or candidate.path.startswith(root + "/"))
            and candidate.username is None and candidate.password is None and not candidate.fragment)


def load_order(artifact_dir: Path, viewport: str, run_id: str, attempt: str) -> dict[str, object]:
    browser_order = json.loads((artifact_dir / f"ci-checkout-{viewport}.json").read_text(encoding="utf-8"))
    verified_order = json.loads((artifact_dir / f"ci-checkout-{viewport}-verified.json").read_text(encoding="utf-8"))
    expected_email = f"qa-ordenowa-checkout-{run_id}-{attempt}-{viewport}@example.invalid"
    order_id = browser_order.get("order_id")
    reference = browser_order.get("reference")
    if (browser_order.get("viewport") != viewport
            or type(order_id) is not int or order_id < 1
            or browser_order.get("email") != expected_email
            or type(browser_order.get("product_id")) is not int or browser_order["product_id"] < 1
            or not isinstance(reference, str) or re.fullmatch(r"[A-Z0-9]{8,16}", reference) is None
            or verified_order.get("order_id") != order_id
            or verified_order.get("reference") != reference
            or verified_order.get("email") != expected_email
            or verified_order.get("product_id") != browser_order["product_id"]
            or verified_order.get("product_quantity") != 1
            or verified_order.get("payment_module") != "ps_checkpayment"
            or verified_order.get("currency") != "JPY"
            or verified_order.get("total_paid_real") != 0
            or verified_order.get("state_iso_code") != "JP-13"):
        raise ValueError("the run-scoped unpaid JPY bank-transfer order fixture is missing or invalid")
    return {
        "order_id": order_id, "reference": reference, "email": expected_email,
        "product_id": browser_order["product_id"], "viewport": viewport,
    }


def load_context() -> dict[str, object]:
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    project = os.environ.get("CI_COMPOSE_PROJECT_NAME", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (os.environ.get("CI") != "true" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("KURANEA_ISOLATED_CI") != "1"
            or not re.fullmatch(r"[0-9]+", run_id) or not re.fullmatch(r"[0-9]+", attempt)
            or project != expected_project or os.environ.get("KURANEA_CI_PROJECT_NAME") != expected_project):
        raise ValueError("exact isolated GitHub Actions project required")
    shop = validate_loopback_endpoint(os.environ.get("SHOP_BASE_URL", ""), 18080, "SHOP_BASE_URL")
    admin = os.environ.get("ADMIN_LOGIN_URL", "").rstrip("/")
    expected_admin = urlparse(shop + "/admin-kuranea")
    parsed_admin = urlparse(admin)
    if ((parsed_admin.scheme, parsed_admin.hostname, parsed_admin.port, parsed_admin.path)
            != (expected_admin.scheme, expected_admin.hostname, expected_admin.port, expected_admin.path)
            or parsed_admin.username is not None or parsed_admin.password is not None
            or parsed_admin.query or parsed_admin.fragment):
        raise ValueError("ADMIN_LOGIN_URL must be the exact isolated Back Office login route")
    artifact_dir_value = os.environ.get("QA_ARTIFACT_DIR", "").strip()
    runner_temp_value = os.environ.get("RUNNER_TEMP", "").strip()
    if not artifact_dir_value or not runner_temp_value:
        raise ValueError("isolated bank-transfer artifact paths are required")
    artifact_dir = Path(artifact_dir_value).resolve()
    runner_temp = Path(runner_temp_value).resolve()
    try:
        artifact_dir.relative_to(runner_temp)
    except ValueError:
        raise ValueError("bank-transfer artifacts must remain inside RUNNER_TEMP") from None
    if artifact_dir == runner_temp:
        raise ValueError("bank-transfer evidence requires a run-specific child artifact directory")
    for key in ("ADMIN_PASSWD", "ADMIN_MAIL", "VIEW_ONLY_EMAIL"):
        if not os.environ.get(key):
            raise ValueError("isolated administrator and limited employee fixtures are required")
    desktop = load_order(artifact_dir, "desktop", run_id, attempt)
    mobile = load_order(artifact_dir, "mobile", run_id, attempt)
    bank = load_order(artifact_dir, "bank", run_id, attempt)
    if (len({desktop["order_id"], mobile["order_id"], bank["order_id"]}) != 3
            or len({desktop["email"], mobile["email"], bank["email"]}) != 3):
        raise ValueError("isolated bank-transfer ownership fixtures must be distinct")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": run_id, "attempt": attempt, "project": project, "shop": shop, "admin": admin,
        "password": os.environ["ADMIN_PASSWD"], "admin_email": os.environ["ADMIN_MAIL"].lower(),
        "view_email": os.environ["VIEW_ONLY_EMAIL"].lower(), "artifact_dir": artifact_dir,
        "runner_temp": runner_temp, "desktop": desktop, "mobile": mobile, "bank": bank,
        "customer_password": f"ORDENOWA-CI-{run_id}-{attempt}-Aa1!",
    }


def new_driver(width: int, height: int) -> webdriver.Chrome:
    options = Options()
    for flag in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--lang=ja-JP"):
        options.add_argument(flag)
    options.add_argument(f"--window-size={width},{height}")
    return webdriver.Chrome(options=options)


def wait_document(driver: webdriver.Chrome) -> None:
    WebDriverWait(driver, 35).until(lambda browser: browser.execute_script("return document.readyState") == "complete")


def visit(driver: webdriver.Chrome, url: str, base: str) -> None:
    assert_true(same_origin(url, base), "navigation left the isolated shop origin")
    driver.get(url)
    wait_document(driver)


def visible(driver: webdriver.Chrome, selector: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def clear_passwords(driver: webdriver.Chrome) -> None:
    cleared = driver.execute_script("""
      const fields = Array.from(document.querySelectorAll('input[type="password"]'));
      for (const field of fields) field.value = '';
      return fields.every(field => field.value === '');
    """)
    assert_true(bool(cleared), "password fields remained in the browser DOM")


def customer_login(driver: webdriver.Chrome, ctx: dict[str, object], email: str) -> None:
    visit(driver, str(ctx["shop"]) + "/index.php?controller=authentication", str(ctx["shop"]))
    visible(driver, "#login-form input[name='email']").send_keys(email)
    visible(driver, "#login-form input[name='password']").send_keys(str(ctx["customer_password"]))
    visible(driver, "#submit-login").click()
    WebDriverWait(driver, 35).until(lambda browser: bool(browser.find_elements(By.ID, "userMenuButton")))
    clear_passwords(driver)


def docker_php_json(
    ctx: dict[str, object], source_path: Path, container_path: str, values: dict[str, str], set_substage=None
) -> dict[str, object]:
    def mark(name: str) -> None:
        if set_substage is not None:
            set_substage(name)

    project = str(ctx["project"])
    mark("limited_route_helper_copy")
    copy = subprocess.run(
        ["docker", "compose", "-p", project, "exec", "-T", "prestashop", "sh", "-c", f"cat > {container_path}"],
        input=source_path.read_text(encoding="utf-8"), capture_output=True, text=True, timeout=30, check=False,
    )
    if copy.returncode != 0:
        raise RuntimeError("could not stage a bounded transfer acceptance helper in the disposable shop")
    mark("limited_route_helper_execution")
    command = ["docker", "compose", "-p", project, "exec", "-T", "--user", "www-data"]
    defaults = {
        "CI": "true", "GITHUB_ACTIONS": "true", "KURANEA_ISOLATED_CI": "1",
        "GITHUB_RUN_ID": str(ctx["run_id"]), "GITHUB_RUN_ATTEMPT": str(ctx["attempt"]),
        "CI_COMPOSE_PROJECT_NAME": project, "KURANEA_CI_PROJECT_NAME": project,
    }
    defaults.update(values)
    for key, value in defaults.items():
        if not re.fullmatch(r"[A-Z0-9_]+", key) or not isinstance(value, str) or "\x00" in value:
            raise ValueError("transfer helper inputs did not match the bounded environment contract")
        command += ["--env", f"{key}={value}"]
    command += ["prestashop", "php", container_path]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    if completed.returncode != 0:
        raise RuntimeError("the isolated native transfer acceptance readback did not pass")
    lines = completed.stdout.splitlines()
    mark("limited_route_helper_json_parse")
    try:
        payload = json.loads(lines[-1])
    except (IndexError, TypeError, ValueError):
        raise RuntimeError("the isolated native transfer helper did not return bounded JSON") from None
    mark("limited_route_helper_json_shape")
    if not isinstance(payload, dict):
        raise RuntimeError("the isolated native transfer helper returned an invalid result shape")
    return payload


def verify_unpaid_native_order(ctx: dict[str, object], order: dict[str, object], expectation: str) -> None:
    source_path = Path(__file__).resolve().parents[1] / "business_profile" / "verify_ci_bank_transfer_unpaid_order.php"
    payload = docker_php_json(
        ctx,
        source_path,
        "/tmp/verify_ci_bank_transfer_unpaid_order.php",
        {
            "KURANEA_CI_ORDER_ID": str(order["order_id"]),
            "KURANEA_CI_ORDER_REFERENCE": str(order["reference"]),
            "KURANEA_CI_PRODUCT_ID": str(order["product_id"]),
            "KURANEA_CI_VIEWPORT": str(order["viewport"]),
            "KURANEA_CI_TRANSFER_EXPECTATION": expectation,
        },
    )
    expected_keys = {
        "status", "order_id", "product_id", "product_name", "product_quantity", "product_total",
        "reference_match", "owner_matches", "amount", "unpaid",
        "currency_jpy", "offline_method", "instruction_count", "receipt_count", "payment_count",
    }
    expected_instruction_count = 1 if expectation == "issued" else 0
    if (set(payload) != expected_keys or payload.get("status") != "success"
            or payload.get("order_id") != order["order_id"]
            or payload.get("product_id") != order["product_id"]
            or not isinstance(payload.get("product_name"), str)
            or "[CI ONLY]" not in payload["product_name"]
            or payload.get("product_quantity") != 1
            or not isinstance(payload.get("product_total"), str)
            or re.fullmatch(r"[1-9][0-9]{0,13}", payload["product_total"]) is None
            or any(payload.get(key) is not True for key in (
                "reference_match", "owner_matches", "unpaid", "currency_jpy", "offline_method",
            ))
            or not isinstance(payload.get("amount"), str)
            or re.fullmatch(r"[1-9][0-9]{0,13}", str(payload.get("amount"))) is None
            or payload.get("instruction_count") != expected_instruction_count
            or payload.get("receipt_count") != 0
            or payload.get("payment_count") != 0):
        raise RuntimeError("the same isolated order did not retain its expected unpaid transfer state")
    order["amount"] = payload["amount"]
    order["product_name"] = payload["product_name"]
    order["product_quantity"] = payload["product_quantity"]
    order["product_total"] = payload["product_total"]
    if expectation == "unissued":
        artifact = {
            "order_id": payload["order_id"],
            "product_id": payload["product_id"],
            "product_name": payload["product_name"],
            "product_quantity": payload["product_quantity"],
            "product_total": payload["product_total"],
            "unpaid": True,
            "currency_jpy": True,
            "offline_method": True,
            "amount": payload["amount"],
        }
        name = f"bank-transfer-{order['viewport']}-unpaid-readback.json"
        (Path(ctx["artifact_dir"]) / name).write_text(
            json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )


def diagnose_unpaid_issue_persistence(ctx: dict[str, object], order: dict[str, object]) -> str:
    source_path = Path(__file__).resolve().parents[1] / "business_profile" / "verify_ci_bank_transfer_unpaid_order.php"
    payload = docker_php_json(
        ctx,
        source_path,
        "/tmp/verify_ci_bank_transfer_unpaid_order.php",
        {
            "KURANEA_CI_ORDER_ID": str(order["order_id"]),
            "KURANEA_CI_ORDER_REFERENCE": str(order["reference"]),
            "KURANEA_CI_PRODUCT_ID": str(order["product_id"]),
            "KURANEA_CI_VIEWPORT": str(order["viewport"]),
            "KURANEA_CI_TRANSFER_EXPECTATION": "diagnostic",
        },
    )
    expected_keys = {
        "status", "db_readback_available", "native_order_unpaid", "instruction_persisted", "instruction_matches_order",
        "receipt_absent", "native_payment_absent",
    }
    if (set(payload) != expected_keys or payload.get("status") != "success"
            or any(type(payload.get(key)) is not bool for key in expected_keys - {"status"})):
        return "unexpected_state"
    if payload["db_readback_available"] is not True:
        return "unavailable"
    if (payload["native_order_unpaid"] is not True or payload["receipt_absent"] is not True
            or payload["native_payment_absent"] is not True or payload["instruction_matches_order"] is not True):
        return "unexpected_state"
    return "unpaid_instruction_persisted" if payload["instruction_persisted"] else "unpaid_instruction_absent"


def limited_transfer_route(
    ctx: dict[str, object], set_substage=None, diagnostics: dict[str, object] | None = None
) -> tuple[str, str]:
    source_path = Path(__file__).resolve().parents[1] / "business_profile" / "resolve_ci_limited_transfer_route.php"
    if set_substage is not None:
        set_substage("limited_route_fixture_readback")
    payload = docker_php_json(
        ctx,
        source_path,
        "/tmp/resolve_ci_limited_transfer_route.php",
        {"VIEW_ONLY_EMAIL": str(ctx["view_email"])},
        set_substage=set_substage,
    )
    if set_substage is not None:
        set_substage("limited_route_contract_readback")
    expected_check_keys = set(LIMITED_ROUTE_CHECK_KEYS)
    checks = payload.get("checks")
    valid_checks = (
        isinstance(checks, dict)
        and set(checks) == expected_check_keys
        and all(type(value) is bool for value in checks.values())
    )
    if valid_checks and diagnostics is not None:
        diagnostics.update({result_key: checks[check_key] for check_key, result_key in LIMITED_ROUTE_CHECK_KEYS.items()})

    helper_stage = payload.get("failure_stage")
    if (payload.get("status") == "failure"
            and isinstance(helper_stage, str)
            and helper_stage in LIMITED_ROUTE_FAILURE_SUBSTAGES
            and valid_checks):
        if set_substage is not None:
            set_substage(LIMITED_ROUTE_FAILURE_SUBSTAGES[helper_stage])
        raise RuntimeError("the isolated limited employee route helper failed a bounded acceptance check")

    if (set(payload) != {"status", "failure_stage", "checks", "route"}
            or payload.get("status") != "success"
            or helper_stage != "none"
            or not valid_checks
            or any(value is not True for value in checks.values())
            or not isinstance(payload.get("route"), str)):
        if set_substage is not None:
            set_substage("limited_route_helper_result_contract")
        raise RuntimeError("the isolated limited employee permission fixture was not read back safely")
    if set_substage is not None:
        set_substage("limited_route_identity_validation")
    internal = urlparse("http://localhost:18080" + str(payload["route"]))
    query = parse_qs(internal.query, keep_blank_values=True)
    token_values = query.get("token", [])
    if (internal.path != "/admin-kuranea/index.php"
            or query.get("controller") != ["AdminBusinessProfileTransfers"]
            or len(token_values) != 1
            or not token_values[0].strip()
            or len(token_values[0]) > 256
            or re.search(r"\s", token_values[0])):
        raise RuntimeError("the limited employee controller link was not the exact expected Back Office route")
    admin_origin = urlparse(str(ctx["admin"]))
    external = admin_origin._replace(path=internal.path, params="", query=internal.query, fragment="")
    url = external.geturl()
    if not safe_admin_path(url, str(ctx["admin"])):
        raise RuntimeError("the limited employee controller link left the isolated admin folder")
    return url, token_values[0]


def admin_login(driver: webdriver.Chrome, ctx: dict[str, object], email: str | None = None) -> None:
    visit(driver, str(ctx["admin"]) + "/login", str(ctx["shop"]))
    visible(driver, '#login_form input[name="email"], input[type="email"]').send_keys(email or str(ctx["admin_email"]))
    visible(driver, '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]').send_keys(str(ctx["password"]))
    visible(driver, '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]').click()
    WebDriverWait(driver, 35).until(lambda browser: "/login" not in urlparse(browser.current_url).path)
    clear_passwords(driver)


def find_transfer_menu_link(driver: webdriver.Chrome, admin_root: str, set_substage=None) -> str:
    def mark(name: str) -> None:
        if set_substage is not None:
            set_substage(name)

    def visible_transfer_links() -> set[str]:
        matches = set()
        for link in driver.find_elements(
            By.CSS_SELECTOR,
            "#nav-sidebar #subtab-AdminBusinessProfileTransfers > a[href]",
        ):
            if not link.is_displayed() or not link.is_enabled():
                continue
            href = link.get_attribute("href") or ""
            if not safe_admin_path(href, admin_root):
                raise AssertionError("the generated transfer menu link left the authenticated Back Office")
            parsed = urlparse(href)
            query = parse_qs(parsed.query, keep_blank_values=True)
            if query.get("controller") == ["AdminBusinessProfileTransfers"]:
                matches.add(href)
        return matches

    mark("transfer_link_scan")
    candidates = visible_transfer_links()
    if not candidates:
        mark("orders_toggle_scan")
        orders_toggles = [
            item for item in driver.find_elements(
                By.CSS_SELECTOR,
                "#nav-sidebar #subtab-AdminParentOrders > a.link",
            ) if item.is_displayed() and item.is_enabled()
        ]
        if len(orders_toggles) != 1:
            raise AssertionError("the authenticated Orders sidebar did not expose one native menu toggle")
        orders_toggle = orders_toggles[0]
        if orders_toggle.get_attribute("aria-expanded") != "true":
            mark("orders_menu_expand")
            orders_toggle.click()
        mark("orders_menu_link_wait")
        WebDriverWait(driver, 10).until(lambda _browser: bool(visible_transfer_links()))
        mark("expanded_transfer_link_readback")
        candidates = visible_transfer_links()
    mark("unique_transfer_link")
    if len(candidates) != 1:
        raise AssertionError("the authenticated Orders menu did not expose one native bank-transfer route")
    return next(iter(candidates))


def order_row(driver: webdriver.Chrome, order: dict[str, object]):
    matches = []
    for row in driver.find_elements(By.CSS_SELECTOR, ".table tbody tr"):
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        if len(cells) >= 2 and cells[0].text.strip() == str(order["reference"]) and cells[1].text.strip() == str(order["order_id"]):
            matches.append(row)
    if len(matches) != 1:
        raise AssertionError("the transfer screen did not identify the exact isolated order row")
    cells = matches[0].find_elements(By.CSS_SELECTOR, "td")
    if "amount" in order:
        shown_amount = cells[2].text if len(cells) > 2 else ""
        if "JPY" not in shown_amount or not displayed_jpy_amount_matches(shown_amount, str(order["amount"])):
            raise AssertionError("the staff order row did not show the exact native JPY amount")
    return matches[0]


def issue_form_token_matches_action(row, admin_root: str) -> bool:
    forms = row.find_elements(By.CSS_SELECTOR, "form")
    if len(forms) != 1:
        return False
    form = forms[0]
    tokens = form.find_elements(By.CSS_SELECTOR, 'input[name="token"]')
    action = form.get_attribute("action") or ""
    action_tokens = parse_qs(urlparse(action).query, keep_blank_values=True).get("token", [])
    form_token = tokens[0].get_attribute("value") if len(tokens) == 1 else ""
    return bool(
        safe_admin_path(action, admin_root)
        and len(action_tokens) == 1
        and action_tokens[0].strip()
        and form_token
        and form_token == action_tokens[0]
    )


def read_issue_csrf_server_evidence(driver) -> dict[str, bool]:
    elements = driver.find_elements(By.ID, "ordenowa-ci-transfer-csrf-evidence")
    evidence = {
        "issue_server_csrf_evidence_present": len(elements) == 1,
        "issue_post_value_present": False,
        "issue_post_matches_controller": False,
        "issue_query_matches_controller": False,
        "issue_post_matches_query": False,
        "issue_controller_matches_admin_link": False,
        "issue_post_native_csrf_valid": False,
    }
    if len(elements) != 1:
        return evidence
    element = elements[0]
    for key, attribute in (
        ("issue_post_value_present", "data-post-value-present"),
        ("issue_post_matches_controller", "data-post-matches-controller"),
        ("issue_query_matches_controller", "data-query-matches-controller"),
        ("issue_post_matches_query", "data-post-matches-query"),
        ("issue_controller_matches_admin_link", "data-controller-matches-admin-link"),
        ("issue_post_native_csrf_valid", "data-post-native-csrf-valid"),
    ):
        evidence[key] = element.get_attribute(attribute) == "true"
    return evidence


def read_issue_profile_server_evidence(driver) -> dict[str, bool]:
    elements = driver.find_elements(By.ID, "ordenowa-ci-transfer-profile-evidence")
    evidence = {
        "issue_server_profile_evidence_present": len(elements) == 1,
        "issue_profile_readback_succeeded": False,
        "issue_published_profile_present": False,
        "issue_bank_transfer_enabled": False,
        "issue_selected_active_account_present": False,
        "issue_isolated_ci_gate_enabled": False,
        "issue_seller_commerce_gate_enabled": False,
        "issue_effective_commerce_gate_enabled": False,
    }
    if len(elements) != 1:
        return evidence
    element = elements[0]
    for key, attribute in (
        ("issue_profile_readback_succeeded", "data-profile-readback-succeeded"),
        ("issue_published_profile_present", "data-published-profile-present"),
        ("issue_bank_transfer_enabled", "data-bank-transfer-enabled"),
        ("issue_selected_active_account_present", "data-selected-active-account-present"),
        ("issue_isolated_ci_gate_enabled", "data-isolated-commerce-gate-enabled"),
        ("issue_seller_commerce_gate_enabled", "data-seller-commerce-gate-enabled"),
        ("issue_effective_commerce_gate_enabled", "data-effective-commerce-gate-enabled"),
    ):
        evidence[key] = element.get_attribute(attribute) == "true"
    return evidence


def read_visible_notice(driver: webdriver.Chrome):
    return WebDriverWait(driver, 35).until(lambda browser: next((
        notice for notice in browser.find_elements(By.CSS_SELECTOR, ".alert.alert-success, .alert.alert-danger")
        if notice.is_displayed()
    ), None))


def read_visible_notice_snapshot(driver: webdriver.Chrome) -> tuple[str, str]:
    def read_snapshot(browser):
        for notice in browser.find_elements(By.CSS_SELECTOR, ".alert.alert-success, .alert.alert-danger"):
            try:
                if not notice.is_displayed():
                    continue
                text = notice.text
                class_name = notice.get_attribute("class") or ""
                if notice.is_displayed():
                    return text, class_name
            except StaleElementReferenceException:
                continue
        return False

    return WebDriverWait(driver, 35).until(read_snapshot)


def issue_notice_failure_substage(notice_text: str, notice_class: str) -> str:
    unpaid_state = "unpaid_present" if "미결제" in notice_text else "unpaid_missing"
    classes = set(notice_class.split())
    if "alert-success" in classes:
        class_state = "success"
    elif "alert-danger" in classes:
        class_state = "danger"
    elif not classes:
        class_state = "missing"
    else:
        class_state = "other"
    return f"instruction_issue_notice_{unpaid_state}_{class_state}"


def issue_notice_failure_category(notice_text: str) -> str:
    """Map exact known feedback to a fixed category without logging message content."""
    normalized = " ".join(notice_text.split())
    known_feedback = {
        "요청에 관리자 보안 토큰이 누락되었습니다. 페이지를 새로고침한 후 다시 시도해 주세요.": "csrf_field_missing",
        "관리자 보안 토큰이 현재 관리자 세션과 다릅니다. 페이지를 새로고침한 후 다시 시도해 주세요.": "csrf_field_mismatch",
        "입금 안내 발급 요청 방식이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.": "invalid_http_method",
        "주문 입금 안내를 발급할 권한이 없습니다.": "issue_permission_denied",
        "선택한 쇼핑몰의 주문을 찾을 수 없습니다.": "order_scope_rejected",
        "입금 안내는 미결제 계좌이체 주문에만 발급할 수 있습니다.": "wrong_payment_module",
        "미결제 상태의 유효한 엔화 주문만 안내할 수 있습니다.": "invalid_unpaid_order",
        "판매자 승인과 게시된 계좌 안내를 먼저 확인해 주세요.": "profile_account_gate",
        "관리자 계정을 확인할 수 없습니다.": "employee_missing",
        "게시된 은행 계좌 설정을 찾을 수 없습니다.": "profile_account_gate",
        "엔화 주문에만 입금 안내를 발급할 수 있습니다.": "invalid_unpaid_order",
        "게시된 은행 계좌가 비활성 상태이거나 선택되지 않았습니다.": "profile_account_gate",
        "주문 입금 안내를 저장하지 못했습니다.": "instruction_persistence_error",
        "이미 발급된 입금 안내와 현재 주문 정보가 다릅니다.": "existing_instruction_mismatch",
        "주문 계좌 안내의 연결 정보가 올바르지 않습니다.": "issuer_validation_error",
        "주문 번호 형식이 올바르지 않습니다.": "issuer_validation_error",
        "주문 금액 형식이 올바르지 않습니다.": "issuer_validation_error",
        "통화 형식이 올바르지 않습니다.": "issuer_validation_error",
        "은행 계좌 연결 정보가 올바르지 않습니다.": "issuer_validation_error",
        "발급 시각 형식이 올바르지 않습니다.": "issuer_validation_error",
    }
    return known_feedback.get(normalized, "unclassified_notice")


def reject_issue_with_invalid_csrf(driver: webdriver.Chrome, row, admin_root: str, set_substage) -> None:
    forms = row.find_elements(By.CSS_SELECTOR, "form")
    if len(forms) != 1:
        set_substage("csrf_form_missing" if not forms else "csrf_form_ambiguous")
        raise AssertionError("the unpaid order did not expose one instruction form for the CSRF rejection check")
    form = forms[0]
    set_substage("csrf_control_validation")
    tokens = form.find_elements(By.CSS_SELECTOR, 'input[name="token"]')
    buttons = form.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaIssueTransfer"]')
    action = form.get_attribute("action") or ""
    if len(tokens) != 1 or len(buttons) != 1 or not safe_admin_path(action, admin_root):
        raise AssertionError("the native instruction form omitted its same-admin token or submit control")
    set_substage("csrf_invalid_token_submit")
    driver.execute_script("arguments[0].value = 'invalid';", tokens[0])
    buttons[0].click()
    set_substage("csrf_rejection_readback")
    notice_text, notice_class = read_visible_notice_snapshot(driver)
    if (notice_text.strip() != "관리자 보안 토큰이 현재 관리자 세션과 다릅니다. 페이지를 새로고침한 후 다시 시도해 주세요."
            or "alert-danger" not in notice_class.split()):
        raise AssertionError("an invalid instruction CSRF token was not rejected by the native controller")


def confirmation_form(row, admin_root: str):
    forms = row.find_elements(By.CSS_SELECTOR, "form")
    if len(forms) != 1:
        raise AssertionError("the issued order did not expose one separate staff receipt-confirmation form")
    form = forms[0]
    fields = {
        "amount": form.find_elements(By.CSS_SELECTOR, 'input[name="received_amount"]'),
        "reference": form.find_elements(By.CSS_SELECTOR, 'input[name="bank_statement_reference"]'),
        "attestation": form.find_elements(By.CSS_SELECTOR, 'input[name="verified_transfer"][value="1"]'),
        "token": form.find_elements(By.CSS_SELECTOR, 'input[name="token"]'),
        "submit": form.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaConfirmBankTransfer"]'),
    }
    if any(len(fields[key]) != 1 for key in fields):
        raise AssertionError("the staff confirmation form omitted an amount, reference, CSRF token, attestation, or submit control")
    action = form.get_attribute("action") or ""
    if not safe_admin_path(action, admin_root):
        raise AssertionError("the staff confirmation POST action left the authenticated Back Office")
    return form, fields, action


def fill_and_submit_confirmation(
    driver: webdriver.Chrome,
    row,
    order: dict[str, object],
    amount: str,
    statement_reference: str,
    admin_root: str,
    tamper_token: bool = False,
) -> tuple[object, str, str]:
    form, fields, action = confirmation_form(row, admin_root)
    token = fields["token"][0].get_attribute("value") or ""
    if not token.strip() or len(token) > 256 or re.search(r"\s", token):
        raise AssertionError("the native staff form did not expose one valid bounded CSRF token")
    fields["amount"][0].clear()
    fields["amount"][0].send_keys(amount)
    fields["reference"][0].send_keys(statement_reference)
    fields["attestation"][0].click()
    if tamper_token:
        # Deliberately mutate only the hidden field to exercise server-side CSRF rejection;
        # the actual confirmation button remains a normal Selenium click.
        driver.execute_script("arguments[0].value = 'invalid';", fields["token"][0])
    fields["submit"][0].click()
    return read_visible_notice(driver), action, token


def submit_hidden_admin_post(
    driver: webdriver.Chrome,
    action_url: str,
    token: str,
    fields: dict[str, str],
    admin_root: str,
) -> str:
    if (not safe_admin_path(action_url, admin_root) or not token.strip()
            or len(token) > 256 or re.search(r"\s", token)):
        raise AssertionError("the controlled negative/replay POST did not use a same-admin tokenized action")
    old_document = driver.find_element(By.TAG_NAME, "body")
    payload = {"token": token, **fields}
    # This creates a deliberately repeated or forbidden form POST; all normal actions above use native UI controls.
    driver.execute_script(
        """
        const [action, values] = arguments;
        const form = document.createElement('form');
        form.method = 'post';
        form.action = action;
        for (const [name, value] of Object.entries(values)) {
          const field = document.createElement('input');
          field.type = 'hidden';
          field.name = name;
          field.value = value;
          form.appendChild(field);
        }
        document.body.appendChild(form);
        form.submit();
        """,
        action_url,
        payload,
    )
    WebDriverWait(driver, 35).until(EC.staleness_of(old_document))
    wait_document(driver)
    return driver.find_element(By.TAG_NAME, "body").text


def customer_order_detail(driver: webdriver.Chrome, ctx: dict[str, object], order: dict[str, object]) -> str:
    visit(driver, str(ctx["shop"]) + "/index.php?controller=history", str(ctx["shop"]))
    rows = WebDriverWait(driver, 35).until(lambda browser: browser.find_elements(By.CSS_SELECTOR, ".order-history__row"))
    matches = [row for row in rows if row.find_element(By.CSS_SELECTOR, ".order-history__cell--reference").text.strip() == str(order["reference"])]
    if len(matches) != 1:
        raise AssertionError("the signed-in customer order history did not contain exactly the matching order")
    href = matches[0].find_element(By.CSS_SELECTOR, 'a[data-link-action="view-order-details"]').get_attribute("href") or ""
    parsed = urlparse(href)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (not same_origin(href, str(ctx["shop"]))
            or query.get("id_order") != [str(order["order_id"])]
            or query.get("controller") not in (["order-detail"], ["order_detail"], ["orderdetail"])):
        raise AssertionError("the native customer details link did not retain this order identity")
    visit(driver, href, str(ctx["shop"]))
    return href


def number_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def displayed_jpy_amount_matches(value: str, expected: str) -> bool:
    normalized = value.replace(",", "")
    matches = re.findall(r"(?<!\d)[0-9]+(?:\.[0-9]+)?", normalized)
    if len(matches) != 1:
        return False
    try:
        return Decimal(matches[0]) == Decimal(expected)
    except Exception:
        return False


def assert_customer_instruction(driver: webdriver.Chrome, order: dict[str, object], account_number: str) -> None:
    sections = driver.find_elements(By.CSS_SELECTOR, "section.ordenowa-bank-transfer-instructions")
    if len(sections) != 1 or not sections[0].is_displayed():
        raise AssertionError("the owning customer order detail did not show one bank-transfer instruction section")
    section = sections[0]
    text = " ".join(section.text.split())
    if str(order["reference"]) not in text or "ORDENOWA CI synthetic bank" not in text or account_number not in text:
        raise AssertionError("the customer instruction did not match its bound seller, bank, account, and order")
    amount_values = []
    for row in section.find_elements(By.CSS_SELECTOR, "dl > div"):
        labels = row.find_elements(By.CSS_SELECTOR, "dt")
        values = row.find_elements(By.CSS_SELECTOR, "dd")
        if len(labels) == 1 and len(values) == 1 and "振込金額" in labels[0].text:
            amount_values.append(values[0].text)
    expected_amount = str(int(Decimal(str(order["amount"]))))
    if len(amount_values) != 1 or number_digits(amount_values[0]) != expected_amount:
        raise AssertionError("the displayed transfer amount did not match the native order total")


def assert_customer_order_product(driver: webdriver.Chrome, order: dict[str, object]) -> None:
    rows = driver.find_elements(By.CSS_SELECTOR, ".order-products .grid-table__inner:first-child .grid-table__row")
    product_rows = [row for row in rows if row.find_elements(By.CSS_SELECTOR, "a.order-product__name")]
    if len(product_rows) != 1:
        raise AssertionError("the same customer order detail did not show exactly one native product line")

    row = product_rows[0]
    names = row.find_elements(By.CSS_SELECTOR, "a.order-product__name")
    quantities = row.find_elements(By.CSS_SELECTOR, ".grid-table__cell--center")
    totals = row.find_elements(By.CSS_SELECTOR, ".grid-table__cell--right")
    if (len(names) != 1
            or " ".join(names[0].text.split()) != order.get("product_name")
            or len(quantities) < 1
            or quantities[0].text.strip() != str(order.get("product_quantity"))
            or len(totals) != 1
            or not displayed_jpy_amount_matches(totals[0].text, str(order.get("product_total")))):
        raise AssertionError("the visible customer product line did not match the same native order readback")


def verify_native_readback(ctx: dict[str, object], order: dict[str, object]) -> dict[str, object]:
    source_path = Path(__file__).resolve().parents[1] / "business_profile" / "verify_ci_bank_transfer_persistence.php"
    payload = docker_php_json(
        ctx,
        source_path,
        "/tmp/verify_ci_bank_transfer_persistence.php",
        {"KURANEA_CI_ORDER_ID": str(order["order_id"])},
    )
    expected_keys = {"status", "order_id", "order_reference_match", "instruction_count", "receipt_count", "payment_count", "paid_history_count", "history_match", "paid", "currency_jpy", "synthetic"}
    if (not isinstance(payload, dict) or set(payload) != expected_keys or payload.get("status") != "success"
            or payload.get("order_id") != order["order_id"]
            or any(payload.get(key) is not True for key in ("order_reference_match", "history_match", "paid", "currency_jpy", "synthetic"))
            or any(payload.get(key) != 1 for key in ("instruction_count", "receipt_count", "payment_count", "paid_history_count"))):
        raise RuntimeError("native bank-transfer readback did not match the same order")
    (Path(ctx["artifact_dir"]) / "bank-transfer-readback.json").write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def write_result(path: Path, result: dict[str, object]) -> None:
    if (set(result) != SAFE_RESULT_KEYS
            or result.get("status") not in ("success", "failure")
            or result.get("stage") not in SAFE_STAGES
            or result.get("failure_substage") not in SAFE_SUBSTAGES
            or result.get("issue_persistence_diagnostic") not in SAFE_ISSUE_PERSISTENCE_DIAGNOSTICS
            or result.get("issue_failure_category") not in SAFE_ISSUE_FAILURE_CATEGORIES
            or (result.get("exception_type") is not None and result.get("exception_type") not in SAFE_EXCEPTION_TYPES)
            or any(type(result.get(key)) is not bool for key in RESULT_BOOLEAN_KEYS)
            or (result.get("status") == "success" and (
                result.get("exception_type") is not None
                or any(result.get(key) is not True for key in SUCCESS_REQUIRED_BOOLEAN_KEYS)
            ))):
        raise ValueError("bank-transfer browser result does not match its allowlisted schema")
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def token_from_url(url: str) -> str:
    values = parse_qs(urlparse(url).query, keep_blank_values=True).get("token", [])
    if len(values) != 1 or not values[0].strip() or len(values[0]) > 256 or re.search(r"\s", values[0]):
        raise AssertionError("the generated staff route did not retain one bounded controller token")
    return values[0]


def assert_restricted_denial(driver: webdriver.Chrome, body_text: str) -> None:
    lowered = body_text.casefold()
    denied = any(term in lowered for term in (
        "권한", "접근이 거부", "access denied", "forbidden", "permission", "not authorized", "not allowed", "403",
    ))
    issue_controls = driver.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaIssueTransfer"]')
    confirm_controls = driver.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaConfirmBankTransfer"]')
    if not denied or issue_controls or confirm_controls or driver.find_elements(By.CSS_SELECTOR, "#login_form"):
        raise AssertionError("the limited employee was not clearly denied without losing its authenticated session")


def clear_sensitive_evidence_fields(driver: webdriver.Chrome) -> None:
    driver.execute_script("""
      for (const field of document.querySelectorAll(
        'input[type="password"], input[type="email"], input[name="token"], input[name="bank_statement_reference"]'
      )) field.value = '';
    """)


def run() -> None:
    ctx = load_context()
    order = ctx["bank"]
    desktop_order = ctx["desktop"]
    stage = "context"
    result: dict[str, object] = {
        "status": "failure", "stage": stage, "exception_type": None,
        "failure_substage": "none",
        "issue_persistence_diagnostic": "not_run",
        "issue_failure_category": "not_run",
        "issue_form_csrf_consistent": False,
        "issue_server_csrf_evidence_present": False, "issue_post_value_present": False,
        "issue_post_matches_controller": False, "issue_query_matches_controller": False,
        "issue_post_matches_query": False, "issue_controller_matches_admin_link": False,
        "issue_post_native_csrf_valid": False,
        "issue_server_profile_evidence_present": False, "issue_profile_readback_succeeded": False,
        "issue_published_profile_present": False,
        "issue_bank_transfer_enabled": False, "issue_selected_active_account_present": False,
        "issue_isolated_ci_gate_enabled": False, "issue_seller_commerce_gate_enabled": False,
        "issue_effective_commerce_gate_enabled": False,
        "fixture_bound": False, "instruction_issued": False, "issue_left_order_unpaid": False,
        "instruction_immutable": False, "customer_instruction_visible": False,
        "order_identity_match": False, "order_product_line_match": False, "amount_match": False, "account_match": False,
        "foreign_customer_denied": False, "limited_staff_denied": False,
        "view_only_issue_denied": False, "view_only_issue_order_unpaid": False,
        "view_only_confirmation_denied": False, "view_only_confirmation_order_unpaid": False,
        **{result_key: False for result_key in LIMITED_ROUTE_CHECK_KEYS.values()},
        "issue_csrf_rejected": False, "csrf_rejected": False, "wrong_amount_rejected": False, "receipt_confirmed": False,
        "idempotent_replay": False, "customer_paid_state_changed": False,
        "instruction_hidden_after_payment": False, "native_readback": False,
    }
    admin = customer = foreign = limited = None
    transfer_url = ""
    mobile_detail_url = ""
    account_number = "00001234"
    synthetic_statement = f"ORDENOWA-CI-RECEIPT-{ctx['run_id']}-{ctx['attempt']}"
    substage = "native_unpaid_order_readback"

    def set_substage(name: str) -> None:
        nonlocal substage
        if name not in SAFE_SUBSTAGES - {"none"}:
            raise ValueError("bank-transfer substage is outside the safe diagnostic allowlist")
        substage = name

    try:
        stage = result["stage"] = "context"
        # The desktop checkout order is intentionally canceled by the preceding
        # native admin-order QA. Its verified run-scoped identity is used only
        # for the foreign-customer denial; all transfer assertions use the dedicated bank order.
        verify_unpaid_native_order(ctx, order, "unissued")
        result["fixture_bound"] = True
        amount = Decimal(str(order["amount"]))
        if amount != amount.to_integral_value() or amount <= 0:
            raise AssertionError("synthetic bank-transfer order total is not an exact positive JPY amount")

        stage = result["stage"] = "admin_login"
        admin = new_driver(1440, 960)
        admin_login(admin, ctx)

        stage = result["stage"] = "transfer_menu"
        transfer_url = find_transfer_menu_link(admin, str(ctx["admin"]), set_substage)
        substage = "menu_link_token"
        admin_token = token_from_url(transfer_url)
        substage = "transfer_route_navigation"
        visit(admin, transfer_url, str(ctx["shop"]))
        substage = "transfer_order_row_readback"
        row = order_row(admin, order)

        stage = result["stage"] = "csrf_rejected"
        reject_issue_with_invalid_csrf(admin, row, str(ctx["admin"]), set_substage)
        substage = "csrf_unissued_db_readback"
        result["failure_substage"] = substage
        verify_unpaid_native_order(ctx, order, "unissued")
        result["failure_substage"] = "none"
        result["issue_csrf_rejected"] = True
        substage = "none"

        stage = result["stage"] = "instruction_issue"
        set_substage("instruction_issue_navigation")
        visit(admin, transfer_url, str(ctx["shop"]))
        set_substage("instruction_issue_order_row_readback")
        row = order_row(admin, order)
        set_substage("instruction_issue_action_controls")
        result["issue_form_csrf_consistent"] = issue_form_token_matches_action(
            row, str(ctx["admin"])
        )
        issue_buttons = row.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaIssueTransfer"]')
        if len(issue_buttons) != 1 or not issue_buttons[0].is_displayed() or not issue_buttons[0].is_enabled():
            raise AssertionError("the exact unpaid order did not expose one enabled instruction-issue action")
        set_substage("instruction_issue_submit")
        issue_buttons[0].click()
        set_substage("instruction_issue_notice_readback")
        notice_text, notice_class = read_visible_notice_snapshot(admin)
        result.update(read_issue_csrf_server_evidence(admin))
        result.update(read_issue_profile_server_evidence(admin))
        if ("미결제" not in notice_text or "alert-success" not in notice_class.split()):
            set_substage(issue_notice_failure_substage(notice_text, notice_class))
            result["issue_failure_category"] = issue_notice_failure_category(notice_text)
            try:
                result["issue_persistence_diagnostic"] = diagnose_unpaid_issue_persistence(ctx, order)
            except Exception:
                result["issue_persistence_diagnostic"] = "unavailable"
            raise AssertionError("issuing bank instructions did not preserve the unpaid-order notice")
        if not all(result[key] for key in (
            "issue_server_profile_evidence_present",
            "issue_profile_readback_succeeded",
            "issue_published_profile_present",
            "issue_bank_transfer_enabled",
            "issue_selected_active_account_present",
            "issue_isolated_ci_gate_enabled",
            "issue_effective_commerce_gate_enabled",
        )):
            set_substage("instruction_issue_profile_gate_evidence")
            raise AssertionError("fresh run-scoped profile and effective checkout-gate evidence did not pass")
        result["instruction_issued"] = True
        result["issue_left_order_unpaid"] = True
        set_substage("instruction_issue_db_readback")
        verify_unpaid_native_order(ctx, order, "issued")
        result["failure_substage"] = "none"
        substage = "none"

        stage = result["stage"] = "instruction_readback"
        visit(admin, transfer_url, str(ctx["shop"]))
        row = order_row(admin, order)
        if "입금 안내 발급" not in row.text or row.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaIssueTransfer"]'):
            raise AssertionError("fresh transfer-admin GET did not retain one immutable order instruction")
        issued_body = submit_hidden_admin_post(
            admin, transfer_url, admin_token,
            {"id_order": str(order["order_id"]), "submitOrdenowaIssueTransfer": "1"},
            str(ctx["admin"]),
        )
        if "이미 발급된 주문 안내를 유지했습니다." not in issued_body:
            raise AssertionError("replaying instruction issuance did not preserve the original immutable notice")
        verify_unpaid_native_order(ctx, order, "issued")
        result["instruction_immutable"] = True

        stage = result["stage"] = "customer_login"
        customer = new_driver(390, 844)
        customer_login(customer, ctx, str(order["email"]))
        stage = result["stage"] = "customer_order_readback"
        before_url = customer_order_detail(customer, ctx, order)
        mobile_detail_url = before_url
        stage = result["stage"] = "customer_order_product_line"
        assert_customer_order_product(customer, order)
        result["order_product_line_match"] = True
        stage = result["stage"] = "customer_order_readback"
        section = customer.find_element(By.CSS_SELECTOR, "section.ordenowa-bank-transfer-instructions")
        assert_customer_instruction(customer, order, account_number)
        status_before = " ".join(customer.find_element(By.CSS_SELECTOR, ".order-status__table").text.split())
        if not status_before:
            raise AssertionError("the unpaid customer order detail had no native status history")
        result["customer_instruction_visible"] = True
        result["order_identity_match"] = str(order["reference"]) in section.text
        result["amount_match"] = True
        result["account_match"] = account_number in section.text
        if not result["order_identity_match"] or not result["amount_match"] or not result["account_match"]:
            raise AssertionError("the customer instruction was not bound to the same account, order, and total")
        customer.save_screenshot(str(Path(ctx["artifact_dir"]) / "bank-transfer-customer-instructions-mobile.png"))

        stage = result["stage"] = "foreign_customer_denial"
        foreign = new_driver(1440, 960)
        customer_login(foreign, ctx, str(desktop_order["email"]))
        visit(foreign, mobile_detail_url, str(ctx["shop"]))
        protected_sections = foreign.find_elements(By.CSS_SELECTOR, "section.ordenowa-bank-transfer-instructions")
        body_text = foreign.find_element(By.TAG_NAME, "body").text
        if (protected_sections or account_number in body_text or str(order["reference"]) in body_text
                or not foreign.find_elements(By.ID, "userMenuButton")):
            raise AssertionError("a different signed-in customer could view this order's transfer instruction")
        result["foreign_customer_denied"] = True

        stage = result["stage"] = "limited_staff_denial"
        limited = new_driver(1440, 960)
        set_substage("limited_staff_login")
        admin_login(limited, ctx, str(ctx["view_email"]))
        limited_url, limited_token = limited_transfer_route(ctx, set_substage, result)
        set_substage("limited_order_row_readback")
        visit(limited, limited_url, str(ctx["shop"]))
        limited_row = order_row(limited, order)
        if (limited_row.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaIssueTransfer"]')
                or limited_row.find_elements(By.CSS_SELECTOR, 'button[name="submitOrdenowaConfirmBankTransfer"]')):
            raise AssertionError("the native view-only employee received a transfer mutation control")
        for submit_name, fields in (
            ("submitOrdenowaIssueTransfer", {"id_order": str(order["order_id"])}),
            ("submitOrdenowaConfirmBankTransfer", {
                "id_order": str(order["order_id"]), "received_amount": str(order["amount"]),
                "bank_statement_reference": synthetic_statement, "verified_transfer": "1",
            }),
        ):
            set_substage("limited_issue_post" if submit_name == "submitOrdenowaIssueTransfer" else "limited_confirmation_post")
            body = submit_hidden_admin_post(
                limited, limited_url, limited_token, {**fields, submit_name: "1"}, str(ctx["admin"])
            )
            if submit_name == "submitOrdenowaConfirmBankTransfer":
                set_substage("limited_confirmation_denial_readback")
                if "주문 입금 확인 권한이 없습니다." not in body:
                    raise AssertionError("a view-only employee's valid-token receipt confirmation was not denied explicitly")
                result["view_only_confirmation_denied"] = True
                set_substage("limited_confirmation_unpaid_db_readback")
                verify_unpaid_native_order(ctx, order, "issued")
                result["view_only_confirmation_order_unpaid"] = True
            elif "주문 입금 안내를 발급할 권한이 없습니다." not in body:
                set_substage("limited_issue_denial_readback")
                raise AssertionError("a view-only employee's valid-token instruction issue was not denied explicitly")
            else:
                set_substage("limited_issue_denial_readback")
                result["view_only_issue_denied"] = True
                set_substage("limited_issue_unpaid_db_readback")
                verify_unpaid_native_order(ctx, order, "issued")
                result["view_only_issue_order_unpaid"] = True
        result["limited_staff_denied"] = True
        limited.save_screenshot(str(Path(ctx["artifact_dir"]) / "bank-transfer-limited-denied-desktop.png"))

        stage = result["stage"] = "csrf_rejected"
        visit(admin, transfer_url, str(ctx["shop"]))
        row = order_row(admin, order)
        notice, confirmation_action, confirmation_token = fill_and_submit_confirmation(
            admin, row, order, str(order["amount"]), synthetic_statement, str(ctx["admin"]), tamper_token=True
        )
        if ("관리자 보안 토큰이 현재 관리자 세션과 다릅니다." not in notice.text
                or "alert-danger" not in (notice.get_attribute("class") or "")):
            raise AssertionError("an invalid confirmation CSRF token was not rejected by the native controller")
        verify_unpaid_native_order(ctx, order, "issued")
        result["csrf_rejected"] = True

        stage = result["stage"] = "wrong_amount_rejected"
        visit(admin, transfer_url, str(ctx["shop"]))
        row = order_row(admin, order)
        wrong_amount = str(int(amount) + 1)
        notice, confirmation_action, confirmation_token = fill_and_submit_confirmation(
            admin, row, order, wrong_amount, synthetic_statement, str(ctx["admin"])
        )
        if ("실제 입금액이 주문 금액과 다릅니다." not in notice.text
                or "alert-danger" not in (notice.get_attribute("class") or "")):
            raise AssertionError("a mismatched deposit amount was not rejected by the native controller")
        verify_unpaid_native_order(ctx, order, "issued")
        result["wrong_amount_rejected"] = True

        stage = result["stage"] = "receipt_confirmation"
        visit(admin, transfer_url, str(ctx["shop"]))
        row = order_row(admin, order)
        notice, confirmation_action, confirmation_token = fill_and_submit_confirmation(
            admin, row, order, str(order["amount"]), synthetic_statement, str(ctx["admin"])
        )
        if ("격리 QA용 합성 입금 확인" not in notice.text or "주문 상태" not in notice.text
                or "alert-success" not in (notice.get_attribute("class") or "")):
            raise AssertionError("the synthetic receipt confirmation did not update the native order state")
        paid_order_still_listed = any(
            len(cells := row.find_elements(By.CSS_SELECTOR, "td")) >= 2
            and cells[0].text.strip() == str(order["reference"])
            and cells[1].text.strip() == str(order["order_id"])
            for row in admin.find_elements(By.CSS_SELECTOR, ".table tbody tr")
        )
        if paid_order_still_listed:
            raise AssertionError("unpaid transfer queue still listed the paid order")
        result["receipt_confirmed"] = True
        admin.save_screenshot(str(Path(ctx["artifact_dir"]) / "bank-transfer-admin-confirmed-desktop.png"))

        stage = result["stage"] = "receipt_replay"
        replay_body = submit_hidden_admin_post(
            admin,
            confirmation_action,
            confirmation_token,
            {
                "id_order": str(order["order_id"]), "received_amount": str(order["amount"]),
                "bank_statement_reference": synthetic_statement, "verified_transfer": "1",
                "submitOrdenowaConfirmBankTransfer": "1",
            },
            str(ctx["admin"]),
        )
        if "이미 확인된 동일 입금 기록을 유지했습니다." not in replay_body:
            raise AssertionError("the identical receipt retry did not return the existing confirmation")
        verify_native_readback(ctx, order)
        result["idempotent_replay"] = True

        stage = result["stage"] = "customer_paid_readback"
        customer.refresh()
        wait_document(customer)
        status_table = customer.find_elements(By.CSS_SELECTOR, ".order-status__table")
        if len(status_table) != 1:
            customer_order_detail(customer, ctx, order)
            status_table = customer.find_elements(By.CSS_SELECTOR, ".order-status__table")
        if len(status_table) != 1:
            raise AssertionError("customer order detail did not expose its native order-status history")
        status_after = " ".join(status_table[0].text.split())
        if not status_after or status_after == status_before:
            raise AssertionError("a fresh customer order-detail GET did not show a changed paid status")
        if customer.find_elements(By.CSS_SELECTOR, "section.ordenowa-bank-transfer-instructions"):
            raise AssertionError("paid order detail still exposed the unpaid bank-transfer instruction")
        result["customer_paid_state_changed"] = True
        result["instruction_hidden_after_payment"] = True
        customer.save_screenshot(str(Path(ctx["artifact_dir"]) / "bank-transfer-customer-paid-mobile.png"))

        stage = result["stage"] = "native_readback"
        verify_native_readback(ctx, order)
        result["native_readback"] = True
        result["status"] = "success"
        result["stage"] = "complete"
        print("PASS: synthetic order-bound instructions, negative ACL/CSRF/amount cases, and one native receipt/payment/history");
    except Exception as error:
        error_type = type(error).__name__
        result["exception_type"] = error_type if error_type in SAFE_EXCEPTION_TYPES else "OtherError"
        result["stage"] = stage if stage in SAFE_STAGES else "context"
        result["failure_substage"] = substage if substage in SAFE_SUBSTAGES else "none"
        print(
            f"FAIL: isolated bank-transfer browser QA; stage={result['stage']}; "
            f"substage={substage}; exception={result['exception_type']}; "
            f"issue_failure_category={result['issue_failure_category']}; "
            f"issue_persistence_diagnostic={result['issue_persistence_diagnostic']}; "
            f"issue_form_csrf_consistent={str(result['issue_form_csrf_consistent']).lower()}; "
            f"issue_server_csrf_evidence_present={str(result['issue_server_csrf_evidence_present']).lower()}; "
            f"issue_post_value_present={str(result['issue_post_value_present']).lower()}; "
            f"issue_post_matches_controller={str(result['issue_post_matches_controller']).lower()}; "
            f"issue_query_matches_controller={str(result['issue_query_matches_controller']).lower()}; "
            f"issue_post_matches_query={str(result['issue_post_matches_query']).lower()}; "
            f"issue_controller_matches_admin_link={str(result['issue_controller_matches_admin_link']).lower()}; "
            f"issue_post_native_csrf_valid={str(result['issue_post_native_csrf_valid']).lower()}; "
            f"view_only_issue_denied={str(result['view_only_issue_denied']).lower()}; "
            f"view_only_issue_order_unpaid={str(result['view_only_issue_order_unpaid']).lower()}; "
            f"view_only_confirmation_denied={str(result['view_only_confirmation_denied']).lower()}; "
            f"view_only_confirmation_order_unpaid={str(result['view_only_confirmation_order_unpaid']).lower()}; "
            f"issue_profile_readback_succeeded={str(result['issue_profile_readback_succeeded']).lower()}; "
            f"issue_published_profile_present={str(result['issue_published_profile_present']).lower()}; "
            f"issue_bank_transfer_enabled={str(result['issue_bank_transfer_enabled']).lower()}; "
            f"issue_selected_active_account_present={str(result['issue_selected_active_account_present']).lower()}; "
            f"issue_isolated_ci_gate_enabled={str(result['issue_isolated_ci_gate_enabled']).lower()}; "
            f"issue_seller_commerce_gate_enabled={str(result['issue_seller_commerce_gate_enabled']).lower()}; "
            f"issue_effective_commerce_gate_enabled={str(result['issue_effective_commerce_gate_enabled']).lower()}; "
            f"limited_route_ci_scope_valid={str(result['limited_route_ci_scope_valid']).lower()}; "
            f"limited_route_identity_shape_valid={str(result['limited_route_identity_shape_valid']).lower()}; "
            f"limited_route_employee_found={str(result['limited_route_employee_found']).lower()}; "
            f"limited_route_employee_active={str(result['limited_route_employee_active']).lower()}; "
            f"limited_route_transfer_tab_present={str(result['limited_route_transfer_tab_present']).lower()}; "
            f"limited_route_view_allowed={str(result['limited_route_view_allowed']).lower()}; "
            f"limited_route_issue_denied={str(result['limited_route_issue_denied']).lower()}; "
            f"limited_route_confirm_denied={str(result['limited_route_confirm_denied']).lower()}; "
            f"limited_route_admin_link_generated={str(result['limited_route_admin_link_generated']).lower()}; "
            f"limited_route_path_valid={str(result['limited_route_path_valid']).lower()}; "
            f"limited_route_controller_valid={str(result['limited_route_controller_valid']).lower()}; "
            f"limited_route_credential_present={str(result['limited_route_credential_present']).lower()}; "
            f"limited_route_credential_bounded={str(result['limited_route_credential_bounded']).lower()}; "
            f"limited_route_credential_whitespace_free={str(result['limited_route_credential_whitespace_free']).lower()}",
            file=sys.stderr,
        )
        for browser, filename in (
            (limited, "bank-transfer-limited-failure.png"),
            (foreign, "bank-transfer-foreign-failure.png"),
            (customer, "bank-transfer-customer-failure.png"),
            (admin, "bank-transfer-admin-failure.png"),
        ):
            if browser is None:
                continue
            try:
                clear_sensitive_evidence_fields(browser)
                browser.save_screenshot(str(Path(ctx["artifact_dir"]) / filename))
            except Exception:
                pass
        write_result(Path(ctx["artifact_dir"]) / "bank-transfer-browser-result.json", result)
        raise SystemExit(1) from None
    finally:
        for browser in (limited, foreign, customer, admin):
            if browser is not None:
                try:
                    browser.quit()
                except Exception:
                    pass
        if result.get("status") == "success":
            write_result(Path(ctx["artifact_dir"]) / "bank-transfer-browser-result.json", result)


if __name__ == "__main__":
    run()
