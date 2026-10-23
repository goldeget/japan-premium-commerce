#!/usr/bin/env python3
"""Verify a published ORDENOWA password-reset logo through Mailpit and Chromium."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.parse import quote, unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
MAILPIT_API = os.environ["MAILPIT_API_URL"].rstrip("/")
CUSTOMER_EMAIL = os.environ["CUSTOMER_EMAIL"].strip().lower()
PUBLISHED_EMAIL_LOGO_PATH = os.environ["PUBLISHED_EMAIL_LOGO_PATH"].strip().lstrip("/")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)
EXPECTED_SHOP_PORT = 18080
EXPECTED_MAILPIT_PORT = 8025

if not re.fullmatch(
    r"ordenowa/versions/[a-fA-F0-9]{64}/(?:email-logo|official-email-logo)\.png",
    PUBLISHED_EMAIL_LOGO_PATH,
):
    raise ValueError("the published email logo path is not a versioned ORDENOWA PNG")
if not re.fullmatch(r"ordenowa-reset-logo-[0-9]+-[0-9]+-[a-f0-9]+@example\.invalid", CUSTOMER_EMAIL):
    raise ValueError("the email brand browser requires a disposable CI-only customer address")


def validate_isolated_ci_compose_project() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    expected_email = rf"ordenowa-reset-logo-{re.escape(run_id)}-{re.escape(attempt)}-[a-f0-9]+@example\.invalid"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or not run_id.isascii()
        or not run_id.isdecimal()
        or not attempt.isascii()
        or not attempt.isdecimal()
        or os.environ.get("CI_COMPOSE_PROJECT_NAME", "") != expected_project
        or not re.fullmatch(expected_email, CUSTOMER_EMAIL)
    ):
        raise ValueError("reset-email brand QA requires its exact isolated GitHub Actions Compose project")


def _validate_loopback_endpoint(value: str, expected_port: int, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must be a valid isolated loopback URL") from None
    if host.lower() == "localhost":
        is_loopback = True
    else:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if (
        parsed.scheme != "http"
        or not is_loopback
        or port != expected_port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use its isolated loopback service on port {expected_port}")
    return parsed.scheme, host.lower(), port


def validate_loopback_endpoints() -> None:
    _validate_loopback_endpoint(BASE, EXPECTED_SHOP_PORT, "SHOP_BASE_URL")
    _validate_loopback_endpoint(MAILPIT_API, EXPECTED_MAILPIT_PORT, "MAILPIT_API_URL")


class InlineLogoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.logo_attributes: list[dict[str, str]] = []
        self.content_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        attributes = {name.lower(): value or "" for name, value in attrs}
        source = attributes.get("src", "").strip()
        if source[:4].lower() == "cid:" and source[4:]:
            self.logo_attributes.append(attributes)
            self.content_ids.add(unquote(source[4:]).strip().strip("<>"))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def request_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("the isolated mail capture returned an unexpected response")
    return payload


def request_bytes(url: str) -> bytes:
    request = Request(url, headers={"Accept": "*/*"})
    with urlopen(request, timeout=10) as response:
        return response.read()


def shop_url_from_generated_link(driver: webdriver.Chrome, link, link_label: str) -> str:
    href = link.get_attribute("href") or ""
    if not href:
        raise AssertionError(f"the generated {link_label} link has no destination")
    destination = urljoin(driver.current_url, href)
    parsed = urlparse(destination)
    base = urlparse(BASE)
    if (
        parsed.scheme != base.scheme
        or parsed.hostname != base.hostname
        or parsed.port != base.port
    ):
        raise AssertionError(f"the generated {link_label} link left the isolated shop origin")
    return destination


def request_message_for_customer(timeout_seconds: int = 90) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            listing = request_json(
                f"{MAILPIT_API}/api/v1/messages?{urlencode({'start': 0, 'limit': 100})}"
            )
            for message in listing.get("messages", []):
                if not isinstance(message, dict):
                    continue
                recipients = message.get("To", [])
                if isinstance(recipients, (dict, str)):
                    recipients = [recipients]
                addresses: set[str] = set()
                if isinstance(recipients, list):
                    for recipient in recipients:
                        address = (
                            recipient.get("Address", "")
                            if isinstance(recipient, dict)
                            else recipient
                        )
                        if isinstance(address, str):
                            addresses.add(address.strip().lower())
                if CUSTOMER_EMAIL not in addresses:
                    continue
                message_id = message.get("ID") or message.get("Id")
                if not isinstance(message_id, str) or not message_id:
                    continue
                return request_json(
                    f"{MAILPIT_API}/api/v1/message/{quote(message_id, safe='')}"
                )
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise TimeoutError("the disposable customer password-reset email did not arrive in Mailpit")


def assert_published_inline_logo(
    message: dict,
    stage_callback: Callable[[str], None],
) -> bytes:
    stage_callback("mailpit_html_cid")
    message_html = message.get("HTML")
    parser = InlineLogoParser()
    if isinstance(message_html, str):
        parser.feed(message_html)
    if not parser.content_ids:
        raise AssertionError("the reset email HTML does not reference the published ORDENOWA logo")

    stage_callback("published_public_png")
    expected_logo = request_bytes(urljoin(BASE + "/", "img/" + PUBLISHED_EMAIL_LOGO_PATH))
    if not expected_logo.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("the published ORDENOWA email logo did not resolve to a PNG image")

    stage_callback("mailpit_inline_content_id")
    inline_logo = next(
        (
            attachment
            for attachment in (message.get("Inline") or [])
            if isinstance(attachment, dict)
            and str(attachment.get("ContentID", "")).strip().strip("<>") in parser.content_ids
        ),
        None,
    )
    if not isinstance(inline_logo, dict):
        raise AssertionError("Mailpit did not capture the ORDENOWA logo as an inline part")

    stage_callback("mailpit_inline_mime")
    if inline_logo.get("ContentType") != "image/png":
        raise AssertionError("Mailpit did not capture the ORDENOWA logo as an inline PNG")

    stage_callback("mailpit_inline_part_identifiers")
    message_id = message.get("ID") or message.get("Id")
    part_id = inline_logo.get("PartID")
    if not isinstance(message_id, str) or not message_id or not isinstance(part_id, str) or not part_id:
        raise AssertionError("Mailpit did not identify the captured inline ORDENOWA logo part")
    stage_callback("mailpit_inline_part_fetch")
    sent_logo = request_bytes(
        f"{MAILPIT_API}/api/v1/message/{quote(message_id, safe='')}"
        f"/part/{quote(part_id, safe='')}"
    )
    stage_callback("published_inline_hash_compare")
    published_sha256 = hashlib.sha256(expected_logo).hexdigest()
    inline_sha256 = hashlib.sha256(sent_logo).hexdigest()
    if inline_sha256 != published_sha256:
        print(
            "ORDENOWA_EMAIL_LOGO_HASH_MISMATCH="
            + json.dumps(
                {
                    "published_sha256": published_sha256,
                    "inline_sha256": inline_sha256,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise AssertionError("the email attachment differs from the current published ORDENOWA derivative")

    stage_callback("mailpit_html_img_element")
    if not parser.logo_attributes:
        raise AssertionError("the captured password-reset email has no inline shop logo image element")
    return sent_logo


def reset_email_logo_safe_state(message: dict) -> dict[str, bool | int]:
    """Expose only structural Mailpit facts when the email logo assertion fails."""
    message_html = message.get("HTML")
    parser = InlineLogoParser()
    if isinstance(message_html, str):
        parser.feed(message_html)
    inline_items = message.get("Inline")
    inline_parts = inline_items if isinstance(inline_items, list) else []
    shop_logo_parts = [
        item
        for item in inline_parts
        if isinstance(item, dict)
        and str(item.get("ContentID", "")).strip().strip("<>") in parser.content_ids
    ]
    return {
        "html_is_string": isinstance(message_html, str),
        "html_nonempty": isinstance(message_html, str) and bool(message_html.strip()),
        # Symfony rewrites the logical shop_logo CID; never expose the generated ID.
        "html_has_shop_logo_cid": bool(parser.content_ids),
        "inline_is_list": isinstance(inline_items, list),
        "inline_part_count": min(len(inline_parts), 20),
        "shop_logo_inline_part_present": bool(shop_logo_parts),
        "shop_logo_inline_part_is_png": any(
            item.get("ContentType") == "image/png" for item in shop_logo_parts
        ),
    }


def emit_reset_email_logo_safe_state(message: dict) -> None:
    """Write only the allowlisted structural state to the log and GitHub annotation."""
    safe_state = json.dumps(
        reset_email_logo_safe_state(message), sort_keys=True, separators=(",", ":")
    )
    print("ORDENOWA_RESET_EMAIL_SAFE_STATE=" + safe_state, file=sys.stderr, flush=True)
    annotation = safe_state.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(
        f"::error title=ORDENOWA reset-email logo state::{annotation}",
        file=sys.stderr,
        flush=True,
    )


def render_captured_logo(driver: webdriver.Chrome, logo_bytes: bytes) -> None:
    encoded_logo = base64.b64encode(logo_bytes).decode("ascii")
    preview_path = DEST / "password-reset-email-logo-preview.html"
    preview_path.write_text(
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        "<title>ORDENOWA password-reset email logo QA</title>"
        "<style>body{margin:32px;font:16px sans-serif;background:#f3f3f3}"
        ".email{max-width:720px;margin:auto;padding:32px;background:white}"
        "#shop-logo{display:block;max-width:100%;height:auto}</style></head>"
        "<body><main class=\"email\"><p>ORDENOWA password-reset email logo</p>"
        f'<img id="shop-logo" src="data:image/png;base64,{encoded_logo}" alt="ORDENOWA email logo">'
        "</main></body></html>",
        encoding="utf-8",
    )
    driver.get(preview_path.resolve().as_uri())
    logo = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.ID, "shop-logo"))
    )
    image_state = driver.execute_script(
        "return {complete: arguments[0].complete, naturalWidth: arguments[0].naturalWidth, "
        "naturalHeight: arguments[0].naturalHeight, visible: arguments[0].getClientRects().length > 0};",
        logo,
    )
    if (
        not isinstance(image_state, dict)
        or image_state.get("complete") is not True
        or image_state.get("naturalWidth", 0) < 1
        or image_state.get("naturalHeight", 0) < 1
        or image_state.get("visible") is not True
        or not logo.is_displayed()
    ):
        raise AssertionError("Chromium did not render the ORDENOWA email logo from the captured message")
    driver.save_screenshot(str(DEST / "password-reset-email-logo.png"))


def run() -> bool:
    validate_isolated_ci_compose_project()
    validate_loopback_endpoints()
    driver = None
    stage = "password_recovery_request"
    message: dict | None = None

    def set_logo_assertion_stage(stage_name: str) -> None:
        nonlocal stage
        stage = stage_name

    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,960")
        options.add_argument("--lang=ja-JP")
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(1440, 960)
        driver.get(f"{BASE}/")
        sign_in_link = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]",
                )
            )
        )
        login_url = shop_url_from_generated_link(driver, sign_in_link, "customer sign-in")
        driver.get(login_url)
        reset_link = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#login-form a[href]"))
        )
        password_reset_url = shop_url_from_generated_link(driver, reset_link, "password reset")
        driver.get(password_reset_url)
        email_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#email"))
        )
        email_field.send_keys(CUSTOMER_EMAIL)
        submit = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#send-reset-link"))
        )
        submit.click()
        driver.save_screenshot(str(DEST / "password-reset-email-requested.png"))

        stage = "mailpit_message_lookup"
        message = request_message_for_customer()
        logo_bytes = assert_published_inline_logo(message, set_logo_assertion_stage)

        stage = "chromium_inline_logo_render"
        render_captured_logo(driver, logo_bytes)
        print("PASS: isolated Mailpit password-reset email contains and Chromium renders the published ORDENOWA logo")
        return True
    except Exception as error:
        if driver is not None:
            try:
                driver.save_screenshot(str(DEST / "password-reset-email-brand-failure.png"))
            except Exception:
                pass
        if isinstance(message, dict):
            emit_reset_email_logo_safe_state(message)
        print(
            f"FAIL: password-reset email brand QA at {stage} ({type(error).__name__})",
            file=sys.stderr,
        )
        print(f"::error title=ORDENOWA reset-email brand QA::{stage} ({type(error).__name__})", file=sys.stderr)
        return False
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
