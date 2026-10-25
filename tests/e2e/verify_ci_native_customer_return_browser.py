#!/usr/bin/env python3
"""Submit one CI-only customer return through PrestaShop's native storefront form."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service


RETURN_NOTE = "[CI ONLY] Synthetic return request; no physical package or payment is involved."
ORDER_EMAIL_PATTERN = re.compile(r"^qa-ordenowa-checkout-[0-9]+-[0-9]+-mobile@example\.invalid$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def read_isolated_shop_url() -> str:
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
    ):
        raise AssertionError("native return browser QA requires its isolated Actions project")

    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if re.fullmatch(r"[0-9]+", run_id) is None or re.fullmatch(r"[0-9]+", run_attempt) is None:
        raise AssertionError("native return browser QA requires run-scoped Actions metadata")
    expected_project_name = f"kuranea-ci-{run_id}-{run_attempt}"
    if os.environ.get("KURANEA_CI_PROJECT_NAME") != expected_project_name:
        raise AssertionError("native return browser QA requires the matching disposable project")

    raw_url = os.environ.get("SHOP_BASE_URL", "")
    parsed = urlparse(raw_url)
    if (
        parsed.scheme != "http"
        or (parsed.hostname or "").lower() not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise AssertionError("native return browser QA requires its loopback shop target")
    try:
        port = parsed.port or 80
    except ValueError as error:
        raise AssertionError("native return browser QA requires a valid loopback port") from error
    if port != 18080:
        raise AssertionError("native return browser QA requires its exact disposable shop port")

    return f"{parsed.scheme}://{parsed.netloc}"


def write_redacted_result(
    output_path: Path,
    *,
    status: str,
    order_id: int | None,
    return_form_submitted: bool,
    return_list_verified: bool,
    return_rows: int,
    screenshot: str | None,
    stage: str,
    exception_type: str | None,
    click_intercept_target: dict[str, str] | None,
    failure_screenshot: str | None,
) -> None:
    result = {
        "status": status,
        "paid_like_order_id": order_id,
        "return_form_submitted": return_form_submitted,
        "return_list_verified": return_list_verified,
        "return_rows": return_rows,
        "provider_call": False,
        "cash_refund": "not_requested",
        "screenshot": screenshot,
        "stage": stage,
        "exception_type": exception_type,
        "click_intercept_target": click_intercept_target,
        "failure_screenshot": failure_screenshot,
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=390,844")
    return webdriver.Chrome(options=options, service=Service(log_output=os.devnull))


def detail_order_id(detail_url: str) -> int:
    parsed = urlparse(detail_url)
    query_ids = parse_qs(parsed.query).get("id_order", [])
    candidates = query_ids
    if not candidates:
        match = re.search(r"/([0-9]+)(?:/|$)", parsed.path)
        candidates = [match.group(1)] if match else []
    if not candidates or not candidates[0].isdigit() or int(candidates[0]) < 1:
        raise AssertionError("the order-history link did not identify a native order")
    return int(candidates[0])


def same_origin(base_url: str, target_url: str) -> bool:
    expected = urlparse(base_url)
    actual = urlparse(urljoin(base_url + "/", target_url))
    return (actual.scheme, actual.netloc) == (expected.scheme, expected.netloc)


def main() -> int:
    artifact_dir = Path(os.environ.get("QA_ARTIFACT_DIR", "/tmp"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result_path = artifact_dir / "customer-return-browser.json"
    screenshot_path = artifact_dir / "customer-return-mobile.png"
    driver = None
    status = "failed"
    stage = "fixture"
    exception_type = None
    order_id = None
    return_form_submitted = False
    return_list_verified = False
    return_rows = 0
    screenshot_name = None
    click_intercept_target = None
    failure_screenshot_name = None

    try:
        base_url = read_isolated_shop_url()
        run_id = os.environ["GITHUB_RUN_ID"]
        run_attempt = os.environ["GITHUB_RUN_ATTEMPT"]

        checkout_artifact = json.loads(
            (artifact_dir / "ci-checkout-mobile.json").read_text(encoding="utf-8")
        )
        order_id = int(os.environ["PAID_LIKE_ORDER_ID"])
        if order_id < 1 or int(checkout_artifact.get("order_id", 0)) != order_id:
            raise AssertionError("the paid-like order does not match the mobile checkout artifact")
        email = str(checkout_artifact.get("email", ""))
        expected_email = f"qa-ordenowa-checkout-{run_id}-{run_attempt}-mobile@example.invalid"
        if not ORDER_EMAIL_PATTERN.fullmatch(email) or email != expected_email:
            raise AssertionError("the mobile checkout account is not run-scoped")
        password = f"ORDENOWA-CI-{run_id}-{run_attempt}-Aa1!"

        stage = "webdriver.startup"
        driver = new_driver()
        driver.set_window_size(390, 844)

        stage = "customer_login"
        driver.get(base_url + "/index.php?controller=authentication")
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#login-form input[name='email']"))
        ).send_keys(email)
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#login-form input[name='password']"))
        ).send_keys(password)
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#submit-login"))
        ).click()
        WebDriverWait(driver, 35).until(
            EC.visibility_of_element_located((By.ID, "userMenuButton"))
        )

        stage = "order_history"
        driver.get(base_url + "/index.php?controller=history")
        history_rows = WebDriverWait(driver, 35).until(
            lambda browser: browser.find_elements(By.CSS_SELECTOR, ".order-history__row")
        )
        matching_detail_url = None
        order_reference = ""
        for history_row in history_rows:
            detail_link = history_row.find_elements(
                By.CSS_SELECTOR, "a[data-link-action='view-order-details']"
            )
            if not detail_link:
                continue
            candidate_url = detail_link[0].get_attribute("href") or ""
            if not same_origin(base_url, candidate_url):
                continue
            if detail_order_id(candidate_url) == order_id:
                matching_detail_url = candidate_url
                reference_node = history_row.find_elements(
                    By.CSS_SELECTOR, ".order-history__cell--reference"
                )
                order_reference = reference_node[0].text.strip() if reference_node else ""
                break
        if matching_detail_url is None or not order_reference:
            raise AssertionError("the mobile customer order was not available in native order history")

        stage = "order_detail"
        driver.get(matching_detail_url)
        return_form = WebDriverWait(driver, 35).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#order-return-form"))
        )
        if return_form.find_element(By.NAME, "id_order").get_attribute("value") != str(order_id):
            raise AssertionError("the native return form belongs to a different order")
        selected_products = return_form.find_elements(
            By.CSS_SELECTOR, "input[name^='ids_order_detail[']"
        )
        if len(selected_products) != 1 or not selected_products[0].is_enabled():
            raise AssertionError("the native return form did not expose one available product")
        checkbox_name = selected_products[0].get_attribute("name") or ""
        detail_match = re.fullmatch(r"ids_order_detail\[([0-9]+)\]", checkbox_name)
        if detail_match is None:
            raise AssertionError("the native return form did not identify its order-detail line")
        order_detail_id = detail_match.group(1)
        quantity = return_form.find_element(By.NAME, f"order_qte_input[{order_detail_id}]")
        stage = "return_quantity_select"
        Select(quantity).select_by_value("1")

        stage = "return_product_checkbox"
        checkbox = selected_products[0]
        driver.execute_script(
            'arguments[0].scrollIntoView({block: "center", inline: "nearest"});', checkbox
        )
        try:
            checkbox.click()
        except ElementClickInterceptedException:
            topmost = driver.execute_script(
                """
                const element = arguments[0];
                const rect = element.getBoundingClientRect();
                const target = document.elementFromPoint(
                  rect.left + rect.width / 2,
                  rect.top + rect.height / 2
                );
                if (!target) return null;
                return {
                  tag: target.tagName.toLowerCase(),
                  id: target.id,
                  class: typeof target.className === "string" ? target.className : ""
                };
                """,
                checkbox,
            )
            if isinstance(topmost, dict):
                click_intercept_target = {
                    key: re.sub(r"[^A-Za-z0-9_.: -]", "", str(topmost.get(key, "")))[:160]
                    for key in ("tag", "id", "class")
                }
            failure_screenshot = artifact_dir / "customer-return-click-intercepted.png"
            if driver.save_screenshot(str(failure_screenshot)):
                failure_screenshot_name = failure_screenshot.name
            raise
        return_form.find_element(By.NAME, "returnText").send_keys(RETURN_NOTE)

        stage = "return_form_submit"
        return_form.find_element(
            By.CSS_SELECTOR, "button[name='submitReturnMerchandise']"
        ).click()
        return_form_submitted = True

        stage = "return_list_readback"
        driver.get(base_url + "/index.php?controller=order-follow")
        matching_rows = WebDriverWait(driver, 35).until(
            lambda browser: [
                row
                for row in browser.find_elements(
                    By.CSS_SELECTOR, ".grid-table__inner--5 .grid-table__row"
                )
                if any(
                    same_origin(base_url, link.get_attribute("href") or "")
                    and detail_order_id(link.get_attribute("href") or "") == order_id
                    for link in row.find_elements(
                        By.CSS_SELECTOR, ".grid-table__cell[role='cell'] a[href]"
                    )[:1]
                )
            ]
        )
        return_rows = len(matching_rows)
        if return_rows != 1:
            raise AssertionError("the native merchandise-return list did not show exactly one request")
        return_list_verified = True

        stage = "screenshot"
        if not driver.save_screenshot(str(screenshot_path)):
            raise AssertionError("the native customer return screenshot could not be saved")
        screenshot_name = screenshot_path.name
        status = "passed"
    except Exception as error:
        exception_type = re.sub(r"[^A-Za-z0-9_]", "", type(error).__name__) or "Exception"
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                if exception_type is None:
                    exception_type = "WebDriverQuitError"
                    status = "failed"
                    stage = "webdriver.quit"
        write_redacted_result(
            result_path,
            status=status,
            order_id=order_id,
            return_form_submitted=return_form_submitted,
            return_list_verified=return_list_verified,
            return_rows=return_rows,
            screenshot=screenshot_name,
            stage=stage,
            exception_type=exception_type,
            click_intercept_target=click_intercept_target,
            failure_screenshot=failure_screenshot_name,
        )

    if status != "passed":
        safe_stage = stage if re.fullmatch(r"[a-z][a-z0-9_.]*", stage) else "unknown"
        safe_type = exception_type or "Exception"
        print(f"FAIL: mobile synthetic customer return QA at {safe_stage} ({safe_type})", file=sys.stderr)
        return 1

    print(
        "PASS: the mobile synthetic customer submitted one native merchandise return; "
        "no payment provider or cash refund was used."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
