#!/usr/bin/env python3
"""Verify native account and order-confirmation mail for the isolated JA/EN/KO checkouts."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ci_mailpit_acceptance import assert_native_mail_locale, parse_raw_mime_parts


LANGUAGES = ("ja", "en", "ko")
MAILPIT_PORT = 8025
MAX_MAILPIT_JSON_BYTES = 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]
PHP_VERIFIER = ROOT / "tests" / "postcode" / "verify_ci_customer_mail_locale_order.php"


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        # A local Mailpit response must never redirect a test request elsewhere.
        return None


_MAILPIT_OPENER = build_opener(_RejectRedirects())


def _mailpit_open(request: Request, timeout: int):
    return _MAILPIT_OPENER.open(request, timeout=timeout)


def validate_isolated_context() -> tuple[str, str, str]:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    project = os.environ.get("CI_COMPOSE_PROJECT_NAME", "")
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or not run_id.isascii()
        or not run_id.isdecimal()
        or not attempt.isascii()
        or not attempt.isdecimal()
        or project != f"kuranea-ci-{run_id}-{attempt}"
    ):
        raise RuntimeError("isolated customer mail acceptance requires its exact GitHub Actions project")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", os.environ.get("CI_TEST_PRODUCT_ID", "")):
        raise RuntimeError("isolated customer mail acceptance requires its run-scoped product")

    shop = os.environ.get("SHOP_BASE_URL", "")
    try:
        shop_url = urlparse(shop)
        shop_port = shop_url.port
    except ValueError:
        raise RuntimeError("isolated customer mail acceptance requires its loopback shop") from None
    if (
        shop_url.scheme != "http"
        or shop_url.hostname not in {"localhost", "127.0.0.1"}
        or shop_port != 18080
        or shop_url.username is not None
        or shop_url.password is not None
        or shop_url.path not in {"", "/"}
        or shop_url.query
        or shop_url.fragment
    ):
        raise RuntimeError("isolated customer mail acceptance requires its loopback shop")

    mailpit = os.environ.get("MAILPIT_API_URL", "")
    try:
        mailpit_url = urlparse(mailpit)
        mailpit_port = mailpit_url.port
        mailpit_host = mailpit_url.hostname or ""
        loopback = mailpit_host.lower() == "localhost" or ipaddress.ip_address(mailpit_host).is_loopback
    except ValueError:
        loopback = False
        mailpit_port = None
        mailpit_url = urlparse("")
    if (
        mailpit_url.scheme != "http"
        or not loopback
        or mailpit_port != MAILPIT_PORT
        or mailpit_url.username is not None
        or mailpit_url.password is not None
        or mailpit_url.path not in {"", "/"}
        or mailpit_url.query
        or mailpit_url.fragment
    ):
        raise RuntimeError("isolated customer mail acceptance requires the configured loopback Mailpit")
    return run_id, attempt, project


def _request_json(url: str) -> dict:
    with _mailpit_open(Request(url, headers={"Accept": "application/json"}), timeout=10) as response:
        payload = response.read(MAX_MAILPIT_JSON_BYTES + 1)
    if len(payload) > MAX_MAILPIT_JSON_BYTES:
        raise RuntimeError("isolated Mailpit response exceeded its size limit")
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise RuntimeError("isolated Mailpit returned an unexpected response")
    return decoded


def _message_id(message: dict) -> str | None:
    value = message.get("ID") or message.get("Id")
    return value if isinstance(value, str) and value and len(value) <= 256 else None


def _is_recipient(message: dict, expected: str) -> bool:
    recipients = message.get("To", [])
    return isinstance(recipients, list) and any(
        isinstance(item, dict)
        and isinstance(item.get("Address"), str)
        and item["Address"].casefold() == expected.casefold()
        for item in recipients
    )


def recipient_message_ids(api: str, recipient: str) -> set[str]:
    listing = _request_json(api + "/api/v1/messages?start=0&limit=100")
    messages = listing.get("messages", [])
    if not isinstance(messages, list):
        raise RuntimeError("isolated Mailpit returned an unexpected message list")
    return {
        identifier
        for message in messages
        if isinstance(message, dict)
        and _is_recipient(message, recipient)
        and (identifier := _message_id(message)) is not None
    }


def wait_new_recipient_message(api: str, recipient: str, previous_ids: set[str]) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        listing = _request_json(api + "/api/v1/messages?start=0&limit=100")
        messages = listing.get("messages", [])
        if not isinstance(messages, list):
            raise RuntimeError("isolated Mailpit returned an unexpected message list")
        new_ids = {
            identifier
            for message in messages
            if isinstance(message, dict)
            and _is_recipient(message, recipient)
            and (identifier := _message_id(message)) is not None
            and identifier not in previous_ids
        }
        if len(new_ids) > 1:
            raise RuntimeError("isolated native email delivery was ambiguous")
        if len(new_ids) == 1:
            identifier = next(iter(new_ids))
            return _request_json(api + "/api/v1/message/" + quote(identifier, safe=""))
        time.sleep(0.5)
    raise TimeoutError("isolated native email did not arrive in Mailpit")


def verify_raw_native_message(
    api: str,
    message: dict,
    recipient: str,
    language: str,
    template: str,
    order_reference: str | None = None,
) -> None:
    if not _is_recipient(message, recipient):
        raise RuntimeError("isolated native email recipient did not match the run-scoped customer")
    identifier = _message_id(message)
    if identifier is None:
        raise RuntimeError("isolated Mailpit message ID was unavailable")
    request = Request(
        api + "/api/v1/message/" + quote(identifier, safe="") + "/raw",
        headers={"Accept": "text/plain"},
    )
    with _mailpit_open(request, timeout=10) as response:
        source = response.read(512 * 1024 + 1)
    html_body, text_body = parse_raw_mime_parts(source)
    assert_native_mail_locale(language, template, html_body, text_body, order_reference)


def _install_php_verifier(project: str) -> None:
    try:
        subprocess.run(
            [
                "docker", "compose", "-p", project, "exec", "-T", "prestashop",
                "sh", "-c", "cat > /tmp/verify_ci_customer_mail_locale_order.php",
            ],
            input=PHP_VERIFIER.read_bytes(),
            check=True,
            capture_output=True,
            timeout=20,
            cwd=ROOT,
        )
    except Exception:
        raise RuntimeError("isolated customer mail persistence verifier could not be installed") from None


def verify_persisted_order(run_id: str, attempt: str, project: str, order: dict, language: str) -> None:
    label = f"mail-{language}"
    values = {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "KURANEA_ISOLATED_CI": "1",
        "GITHUB_RUN_ID": run_id,
        "GITHUB_RUN_ATTEMPT": attempt,
        "KURANEA_CI_PROJECT_NAME": project,
        "KURANEA_CI_VIEWPORT": label,
        "KURANEA_CI_ORDER_ID": str(order["order_id"]),
        "KURANEA_CI_PRODUCT_ID": str(order["product_id"]),
        "KURANEA_CI_EXPECTED_LANG_ISO": language,
        "KURANEA_CI_EXPECTED_ORDER_REFERENCE": str(order["reference"]),
    }
    command = ["docker", "compose", "-p", project, "exec", "-T"]
    for key, value in values.items():
        command.extend(("-e", f"{key}={value}"))
    command.extend((
        "prestashop", "runuser", "-g", "www-data", "-u", "www-data", "--",
        "php", "/tmp/verify_ci_customer_mail_locale_order.php",
    ))
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=30, cwd=ROOT
        )
        result = json.loads(completed.stdout)
    except Exception:
        raise RuntimeError("native unpaid order and customer locale did not persist and read back") from None
    expected = {
        "language_iso": language,
        "customer_persisted": True,
        "order_persisted": True,
        "unpaid": True,
        "payment_module": "ps_checkpayment",
        "product_quantity": 1,
    }
    if not isinstance(result, dict) or result != expected:
        raise RuntimeError("native unpaid order and customer locale did not persist and read back")


def suppress_checkout_screenshots(driver) -> None:
    """Prevent shared checkout helpers from publishing account/address screenshots."""
    setattr(driver, "save_screenshot", lambda _filename: False)


def _run_locale(language: str, run_id: str, attempt: str, project: str, api: str) -> None:
    from verify_ci_checkout_admin_browser import (
        DEST,
        PRODUCT_ID,
        RUN_ATTEMPT,
        RUN_ID,
        add_product_and_open_checkout,
        browser_options,
        checkout_registration_email,
        choose_delivery_and_offline_payment,
        place_unpaid_order,
        register_checkout_account,
        search_for_product,
        select_japan_address,
    )
    from selenium import webdriver

    label = f"mail-{language}"
    if RUN_ID != run_id or RUN_ATTEMPT != attempt:
        raise RuntimeError("native customer email run metadata changed during acceptance")
    email = checkout_registration_email(label, run_id, attempt)
    driver = webdriver.Chrome(options=browser_options(1440, 960))
    stage = "product_search"
    try:
        suppress_checkout_screenshots(driver)
        driver.set_window_size(1440, 960)
        search_for_product(
            driver,
            label,
            os.environ.get("CI_TEST_PRODUCT_SEARCH_TERM", "free"),
            language_iso=language,
        )
        stage = "cart"
        add_product_and_open_checkout(driver, label)

        account_before_ids = recipient_message_ids(api, email)
        stage = "native_registration"
        registered_email = register_checkout_account(driver, label)
        if registered_email.casefold() != email.casefold():
            raise RuntimeError("native account used an unexpected isolated recipient")
        if (driver.find_element("tag name", "html").get_attribute("lang") or "").lower().split("-")[0] != language:
            raise RuntimeError("native checkout registration changed the requested language")
        stage = "account_creation_raw_mime"
        account_message = wait_new_recipient_message(api, email, account_before_ids)
        verify_raw_native_message(api, account_message, email, language, "account")

        stage = "japan_address"
        select_japan_address(driver, label)
        stage = "offline_payment"
        choose_delivery_and_offline_payment(driver, label)
        order_before_ids = recipient_message_ids(api, email)
        stage = "native_order_confirmation"
        order = place_unpaid_order(driver, label, email, language_iso=language)
        stage = "order_confirmation_raw_mime"
        order_message = wait_new_recipient_message(api, email, order_before_ids)
        verify_raw_native_message(
            api,
            order_message,
            email,
            language,
            "order_conf",
            order_reference=str(order["reference"]),
        )
        stage = "customer_order_locale_readback"
        verify_persisted_order(run_id, attempt, project, order, language)

        result_path = DEST / f"ci-checkout-{label}.json"
        result = {
            "viewport": label,
            "order_id": int(order["order_id"]),
            "reference": str(order["reference"]),
            "product_id": PRODUCT_ID,
            "payment_module": "ps_checkpayment",
            "locale": language,
            "account_creation_raw_mime_locale_verified": True,
            "order_confirmation_raw_mime_locale_verified": True,
            "customer_and_order_locale_persisted": True,
        }
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"PASS: {language} native account and order-confirmation raw MIME, exact recipient, "
            "unpaid order, and persisted customer/order locale readback"
        )
    except Exception as error:
        safe_stage = stage if stage in {
            "product_search", "cart", "native_registration", "account_creation_raw_mime",
            "japan_address", "offline_payment", "native_order_confirmation",
            "order_confirmation_raw_mime", "customer_order_locale_readback",
        } else "unknown"
        exception_type = type(error).__name__
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", exception_type):
            exception_type = "Exception"
        print(
            f"FAIL: isolated native customer mail acceptance for {language} at "
            f"{safe_stage} ({exception_type})",
            file=sys.stderr,
        )
        raise SystemExit(f"isolated native customer mail acceptance failed for {language}") from None
    finally:
        driver.quit()


def run_acceptance() -> None:
    run_id, attempt, project = validate_isolated_context()
    api = os.environ["MAILPIT_API_URL"].rstrip("/")
    _install_php_verifier(project)
    for language in LANGUAGES:
        _run_locale(language, run_id, attempt, project, api)


if __name__ == "__main__":
    run_acceptance()
