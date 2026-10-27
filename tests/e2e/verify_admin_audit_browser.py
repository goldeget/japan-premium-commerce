#!/usr/bin/env python3
"""Verify the native five-source admin audit page with isolated CI readers."""

from __future__ import annotations

import ipaddress
import json
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


SHOP_BASE_URL = os.environ.get("SHOP_BASE_URL", "").rstrip("/")
ADMIN_LOGIN_URL = os.environ.get("ADMIN_LOGIN_URL", "").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_MAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWD", "")
READER_EMAIL = os.environ.get("ADMIN_AUDIT_READER_EMAIL", "")
LIMITED_READER_EMAIL = os.environ.get("ADMIN_AUDIT_LIMITED_READER_EMAIL", "")
ARTIFACT_DIR = Path(os.environ.get("QA_ARTIFACT_DIR", "."))


def isolated_integer(name: str, minimum: int = 1) -> int:
    value = os.environ.get(name, "")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value):
        raise ValueError(f"{name} must be a positive isolated fixture ID")
    number = int(value)
    if number < minimum:
        raise ValueError(f"{name} is outside its supported range")
    return number


def validate_context() -> dict[str, int]:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or not re.fullmatch(r"[0-9]+", run_id)
        or not re.fullmatch(r"[0-9]+", attempt)
        or os.environ.get("CI_COMPOSE_PROJECT_NAME") != expected_project
        or os.environ.get("KURANEA_CI_PROJECT_NAME") != expected_project
    ):
        raise ValueError("admin audit browser QA requires the exact disposable Actions project")
    if not re.fullmatch(r"ci-ordenowa@example\.invalid", ADMIN_EMAIL):
        raise ValueError("admin audit browser QA requires the CI administrator account")
    if not ADMIN_PASSWORD or not ADMIN_PASSWORD.isprintable():
        raise ValueError("admin audit browser QA requires the isolated administrator password")
    reader_pattern = re.compile(
        rf"ordenowa-admin-audit-{re.escape(run_id)}-{re.escape(attempt)}-[a-f0-9]{{8}}@example\.invalid"
    )
    limited_pattern = re.compile(
        rf"ordenowa-admin-audit-limited-{re.escape(run_id)}-{re.escape(attempt)}-[a-f0-9]{{8}}@example\.invalid"
    )
    if not reader_pattern.fullmatch(READER_EMAIL) or not limited_pattern.fullmatch(LIMITED_READER_EMAIL):
        raise ValueError("admin audit reader email did not match this isolated run")
    if READER_EMAIL == LIMITED_READER_EMAIL:
        raise ValueError("admin audit readers must use separate employee accounts")

    try:
        shop = urlparse(SHOP_BASE_URL)
        admin = urlparse(ADMIN_LOGIN_URL)
        shop_port = shop.port
        admin_port = admin.port
    except ValueError:
        raise ValueError("admin audit browser endpoints are malformed") from None
    host = shop.hostname or ""
    if host.lower() == "localhost":
        loopback = True
    else:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    expected_admin_path = "/admin-kuranea"
    if (
        shop.scheme != "http"
        or not loopback
        or shop_port != 18080
        or shop.path not in ("", "/")
        or (admin.scheme, admin.hostname, admin_port, admin.path.rstrip("/"))
        != (shop.scheme, shop.hostname, shop_port, expected_admin_path)
        or shop.username is not None
        or shop.password is not None
        or admin.username is not None
        or admin.password is not None
        or shop.query
        or shop.fragment
        or admin.query
        or admin.fragment
    ):
        raise ValueError("admin audit browser endpoints must stay on the isolated loopback shop")

    if not os.environ.get("QA_ARTIFACT_DIR", "").strip():
        raise ValueError("admin audit screenshot path is required")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "target_employee_id": isolated_integer("ADMIN_AUDIT_TARGET_EMPLOYEE_ID"),
        "limited_employee_id": isolated_integer("ADMIN_AUDIT_LIMITED_EMPLOYEE_ID"),
        "support_thread_id": isolated_integer("ADMIN_AUDIT_SUPPORT_THREAD_ID"),
        "order_id": isolated_integer("ADMIN_AUDIT_ORDER_ID"),
    }


def new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    return webdriver.Chrome(options=options)


def login(driver: webdriver.Chrome, email: str) -> None:
    driver.get(ADMIN_LOGIN_URL + "/login")
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#login_form input[name="email"]')))
    driver.find_element(By.CSS_SELECTOR, '#login_form input[name="email"]').send_keys(email)
    driver.find_element(By.CSS_SELECTOR, '#login_form input[name="passwd"]').send_keys(ADMIN_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "#login_form button[type='submit'], #login_form input[type='submit']").click()
    WebDriverWait(driver, 30).until(
        lambda browser: not any(
            form.is_displayed()
            for form in browser.find_elements(By.CSS_SELECTOR, "#login_form")
        )
    )


def audit_url(driver: webdriver.Chrome) -> str:
    candidates = [link.get_attribute("href") or "" for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminKuraneaEmployeeProfileAudit"]')]
    current = driver.current_url
    if parse_qs(urlparse(current).query).get("controller") == ["AdminKuraneaEmployeeProfileAudit"]:
        candidates.insert(0, current)
    expected = urlparse(SHOP_BASE_URL)
    admin_path = urlparse(ADMIN_LOGIN_URL).path.rstrip("/")
    for href in candidates:
        parsed = urlparse(href)
        query = parse_qs(parsed.query, keep_blank_values=True)
        token = query.get("token", [])
        if query.get("controller") != ["AdminKuraneaEmployeeProfileAudit"] or len(token) != 1 or not token[0].strip():
            continue
        if (parsed.scheme, parsed.hostname, parsed.port) != (expected.scheme, expected.hostname, expected.port):
            continue
        if not parsed.path.startswith(admin_path + "/"):
            continue
        return href
    raise AssertionError("the authenticated audit reader has no own tokenized audit route")


def wait_for_audit_page(driver: webdriver.Chrome) -> None:
    WebDriverWait(driver, 30).until(
        lambda browser: any(
            heading.is_displayed() and "관리자 감사 기록" in heading.text
            for heading in browser.find_elements(By.CSS_SELECTOR, ".panel h3")
        )
    )


def table_rows(driver: webdriver.Chrome) -> list[tuple[str, str, str, str, str]]:
    wait_for_audit_page(driver)
    result: list[tuple[str, str, str, str, str]] = []
    for row in driver.find_elements(By.CSS_SELECTOR, ".panel table.table tbody tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) != 5:
            raise AssertionError("audit page row did not expose the five allowlisted columns")
        result.append(tuple(re.sub(r"\s+", " ", cell.text).strip() for cell in cells))
    return result


def require_row(
    rows: list[tuple[str, str, str, str, str]],
    source: str,
    action: str,
    target: str,
) -> None:
    if not any(row[1] == source and row[2] == action and row[4] == target for row in rows):
        raise AssertionError(f"the expected {source} row was not rendered for its isolated target")


def verify_full_reader(values: dict[str, int]) -> None:
    driver = new_driver()
    try:
        login(driver, READER_EMAIL)
        driver.get(audit_url(driver))
        rows = table_rows(driver)
        expected = (
            ("관리자 프로필", "관리자 프로필 변경", f"관리자 #{values['target_employee_id']}"),
            ("주문 상태", "주문 상태 변경", f"주문 #{values['order_id']}"),
            ("상담 배정", "담당자 지정", f"문의 #{values['support_thread_id']}"),
            ("입금 안내", "입금 안내 발급", f"주문 #{values['order_id']}"),
            ("입금 확인", "입금 확인 기록", f"주문 #{values['order_id']}"),
        )
        for source, action, target in expected:
            require_row(rows, source, action, target)
        if not any(row[0].endswith("(UTC)") or row[0].endswith("(저장값)") for row in rows):
            raise AssertionError("the audit page did not render a bounded event time basis")
        driver.save_screenshot(str(ARTIFACT_DIR / "admin-audit-authorized.png"))

        driver.refresh()
        refreshed_rows = table_rows(driver)
        for source, action, target in expected:
            require_row(refreshed_rows, source, action, target)
        if rows != refreshed_rows:
            raise AssertionError("a fresh audit-page request did not reproduce the stored allowlisted rows")
    finally:
        driver.quit()


def verify_source_limited_reader(values: dict[str, int]) -> None:
    driver = new_driver()
    try:
        login(driver, LIMITED_READER_EMAIL)
        driver.get(audit_url(driver))
        rows = table_rows(driver)
        require_row(
            rows,
            "관리자 프로필",
            "관리자 프로필 변경",
            f"관리자 #{values['target_employee_id']}",
        )
        if any(row[1] != "관리자 프로필" for row in rows):
            raise AssertionError("the source-limited reader saw a source without native READ permission")
        forbidden_targets = {
            f"주문 #{values['order_id']}",
            f"문의 #{values['support_thread_id']}",
        }
        if any(row[4] in forbidden_targets for row in rows):
            raise AssertionError("the source-limited reader saw an order or support target")
        if any(row[2] in {"주문 상태 변경", "담당자 지정", "담당자 변경", "입금 안내 발급", "입금 확인 기록"} for row in rows):
            raise AssertionError("the source-limited reader saw a protected order, support, or transfer action")
        driver.save_screenshot(str(ARTIFACT_DIR / "admin-audit-source-limited.png"))

        driver.refresh()
        refreshed_rows = table_rows(driver)
        if rows != refreshed_rows or any(row[1] != "관리자 프로필" for row in refreshed_rows):
            raise AssertionError("fresh source-limited readback exposed a protected audit source")
    finally:
        driver.quit()


def main() -> int:
    stage = "isolated_ci_guard"
    try:
        values = validate_context()
        stage = "full_source_reader"
        verify_full_reader(values)
        stage = "source_limited_reader"
        verify_source_limited_reader(values)
        print(
            "ORDENOWA_ADMIN_AUDIT_RESULT="
            + json.dumps(
                {
                    "status": "passed",
                    "full_source_rows": 5,
                    "fresh_readback": True,
                    "source_limited_profile_only": True,
                    "screenshots": 2,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception as error:
        error_type = type(error).__name__
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", error_type):
            error_type = "Error"
        print(f"FAIL: admin audit browser acceptance at {stage} ({error_type})", file=sys.stderr)
        print(f"ORDENOWA_ADMIN_AUDIT_STAGE={stage}", file=sys.stderr)
        print(
            "ORDENOWA_ADMIN_AUDIT_RESULT="
            + json.dumps(
                {"status": "failed", "stage": stage, "exception_type": error_type},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
