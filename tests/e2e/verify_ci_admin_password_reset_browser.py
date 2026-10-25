#!/usr/bin/env python3
"""Verify native PrestaShop Back Office employee recovery in isolated CI."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


EXPECTED_SHOP_PORT = 18080
EXPECTED_MAILPIT_PORT = 8025
FIXTURE_MARKER = "ORDENOWA_ADMIN_RECOVERY_FIXTURE="


class ResetLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = {name.lower(): value or "" for name, value in attrs}
        if attributes.get("href"):
            self.hrefs.append(attributes["href"])


def validate_loopback_endpoint(value: str, expected_port: int, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} is not a valid isolated loopback URL") from None
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
        or port != expected_port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use its isolated loopback service on port {expected_port}")
    return parsed.scheme, host.lower(), port


def validate_isolated_environment(environ: dict[str, str]) -> dict[str, str]:
    run_id = environ.get("GITHUB_RUN_ID", "")
    attempt = environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        environ.get("CI") != "true"
        or environ.get("GITHUB_ACTIONS") != "true"
        or environ.get("KURANEA_ISOLATED_CI") != "1"
        or not re.fullmatch(r"[0-9]+", run_id)
        or not re.fullmatch(r"[0-9]+", attempt)
        or environ.get("CI_COMPOSE_PROJECT_NAME") != expected_project
    ):
        raise ValueError("employee password recovery requires its exact isolated Actions Compose project")

    base_url = environ.get("SHOP_BASE_URL", "").rstrip("/")
    mailpit_url = environ.get("MAILPIT_API_URL", "").rstrip("/")
    admin_url = environ.get("ADMIN_LOGIN_URL", "").rstrip("/")
    validate_loopback_endpoint(base_url, EXPECTED_SHOP_PORT, "SHOP_BASE_URL")
    validate_loopback_endpoint(mailpit_url, EXPECTED_MAILPIT_PORT, "MAILPIT_API_URL")
    try:
        base = urlparse(base_url)
        admin = urlparse(admin_url)
    except ValueError:
        raise ValueError("ADMIN_LOGIN_URL is not valid for the isolated Back Office") from None
    if (
        (admin.scheme, admin.hostname, admin.port) != (base.scheme, base.hostname, base.port)
        or admin.path != "/admin-kuranea"
        or admin.query
        or admin.fragment
        or admin.username is not None
        or admin.password is not None
    ):
        raise ValueError("ADMIN_LOGIN_URL must name the isolated Back Office path on the shop origin")

    employee_email = environ.get("ADMIN_RECOVERY_EMAIL", "").strip().lower()
    expected_email = rf"ordenowa-admin-recovery-{re.escape(run_id)}-{re.escape(attempt)}-[a-f0-9]{{8}}@example\.invalid"
    if not re.fullmatch(expected_email, employee_email):
        raise ValueError("ADMIN_RECOVERY_EMAIL must be the run-scoped synthetic employee fixture")
    admin_email = environ.get("ADMIN_MAIL", "").strip().lower()
    if admin_email != "ci-ordenowa@example.invalid" or admin_email == employee_email:
        raise ValueError("ADMIN_MAIL must identify only the isolated primary administrator")
    if not environ.get("ADMIN_PASSWD"):
        raise ValueError("ADMIN_PASSWD is required for the isolated employee password check")

    return {
        "run_id": run_id,
        "run_attempt": attempt,
        "compose_project": expected_project,
        "shop_base_url": base_url,
        "admin_login_url": admin_url,
        "mailpit_api_url": mailpit_url,
        "admin_email": admin_email,
        "employee_email": employee_email,
    }


def validate_artifact_directory(value: str, runner_temp: str) -> Path:
    if not value or not runner_temp:
        raise ValueError("browser artifacts require an explicit Actions runner temporary directory")
    candidate = Path(value)
    root = Path(runner_temp)
    if not candidate.is_absolute() or not root.is_absolute():
        raise ValueError("browser artifacts must use absolute runner-local paths")
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        relative = resolved_candidate.relative_to(resolved_root)
    except ValueError:
        raise ValueError("browser artifacts must remain inside RUNNER_TEMP") from None
    if not relative.parts:
        raise ValueError("browser artifacts require a run-specific child directory")
    return resolved_candidate


def parse_fixture_result(output: str, expected_email: str, run_id: str, attempt: str) -> dict[str, object]:
    rows = [line[len(FIXTURE_MARKER) :] for line in output.splitlines() if line.startswith(FIXTURE_MARKER)]
    if len(rows) != 1:
        raise ValueError("the isolated fixture did not return exactly one employee result")
    try:
        result = json.loads(rows[0])
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("the isolated fixture returned invalid JSON") from None
    if not isinstance(result, dict) or set(result) != {"employee_id", "email"}:
        raise ValueError("the isolated fixture output must contain only employee_id and email")
    employee_id = result.get("employee_id")
    email = result.get("email")
    expected_pattern = rf"ordenowa-admin-recovery-{re.escape(run_id)}-{re.escape(attempt)}-[a-f0-9]{{8}}@example\.invalid"
    if (
        isinstance(employee_id, bool)
        or not isinstance(employee_id, int)
        or employee_id <= 1
        or not isinstance(email, str)
        or email != expected_email
        or not re.fullmatch(expected_pattern, email)
    ):
        raise ValueError("the isolated fixture returned an unexpected employee identity")
    return {"employee_id": employee_id, "email": email}


def recipient_addresses(message: dict[str, object]) -> set[str]:
    values = message.get("To", [])
    if isinstance(values, (str, dict)):
        values = [values]
    found: set[str] = set()
    if isinstance(values, list):
        for item in values:
            address = item.get("Address", "") if isinstance(item, dict) else item
            if isinstance(address, str):
                found.add(address.strip().lower())
    return found


def validate_employee_reset_url(candidate: str, admin_login_url: str) -> str:
    try:
        destination = urljoin(admin_login_url.rstrip("/") + "/", candidate)
        parsed = urlparse(destination)
        expected = urlparse(admin_login_url)
        route_prefix = expected.path.rstrip("/") + "/index.php/reset-password/"
        path = unquote(parsed.path, errors="strict")
    except (TypeError, ValueError):
        raise ValueError("the captured employee reset link is malformed") from None
    token = path[len(route_prefix) :] if path.startswith(route_prefix) else ""
    if (
        (parsed.scheme, parsed.hostname, parsed.port) != (expected.scheme, expected.hostname, expected.port)
        or not re.fullmatch(r"[a-f0-9]{40}", token)
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("the captured employee reset link is outside the native isolated admin route")
    return destination


def reset_url_from_mailpit_message(
    message: dict[str, object], expected_email: str, admin_login_url: str
) -> str | None:
    if recipient_addresses(message) != {expected_email.strip().lower()}:
        return None
    parser = ResetLinks()
    html = message.get("HTML")
    if isinstance(html, str):
        parser.feed(html)
    candidates = list(parser.hrefs)
    text_body = message.get("Text")
    if isinstance(text_body, str):
        candidates.extend(re.findall(r"https?://[^\s<>\"']+", text_body))
    for candidate in candidates:
        candidate = candidate.strip().rstrip(".,);]")
        try:
            parsed = urlparse(urljoin(admin_login_url.rstrip("/") + "/", candidate))
        except ValueError:
            continue
        if "/reset-password/" not in unquote(parsed.path):
            continue
        return validate_employee_reset_url(candidate, admin_login_url)
    return None


def request_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Mailpit returned an unexpected response")
    return result


def wait_for_employee_reset_url(
    mailpit_url: str, employee_email: str, admin_login_url: str, timeout_seconds: int = 90
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            listing = request_json(
                f"{mailpit_url.rstrip('/')}/api/v1/messages?"
                f"{urlencode({'start': 0, 'limit': 100})}"
            )
            for message in listing.get("messages", []):
                if not isinstance(message, dict) or recipient_addresses(message) != {employee_email.lower()}:
                    continue
                message_id = message.get("ID") or message.get("Id")
                if not isinstance(message_id, str) or not message_id:
                    continue
                detail = request_json(
                    f"{mailpit_url.rstrip('/')}/api/v1/message/{quote(message_id, safe='')}"
                )
                reset_url = reset_url_from_mailpit_message(detail, employee_email, admin_login_url)
                if reset_url:
                    return reset_url
        except (OSError, URLError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise TimeoutError("the isolated employee password reset email did not arrive with its native link")


def visible(driver, selector: str, timeout: int = 30):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def login_controller(url: str, admin_login_url: str) -> str:
    try:
        actual = urlparse(url)
        admin = urlparse(admin_login_url)
        admin_path = admin.path.rstrip("/")
        if (
            (actual.scheme, actual.hostname, actual.port) != (admin.scheme, admin.hostname, admin.port)
            or not actual.path.startswith(admin_path + "/")
        ):
            return "other"
        controllers = parse_qs(actual.query).get("controller", [])
        if controllers != ["AdminDashboard"]:
            return "other"
        allowed_paths = {
            admin_path + "/",
            admin_path + "/index.php",
            admin_path + "/index.php/sell/dashboard",
            admin_path + "/sell/dashboard",
        }
        return "AdminDashboard" if actual.path in allowed_paths else "other"
    except (TypeError, ValueError):
        return "other"


def new_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--lang=en-US")
    return webdriver.Chrome(options=options)


def visible_login_form(driver) -> bool:
    from selenium.webdriver.common.by import By

    try:
        forms = driver.find_elements(By.CSS_SELECTOR, "#login_form")
        return any(form.is_displayed() for form in forms)
    except Exception:
        return False


def fill_login(driver, admin_login_url: str, email: str, password: str) -> None:
    from selenium.webdriver.common.by import By

    driver.get(admin_login_url.rstrip("/") + "/login")
    email_input = visible(driver, '#login_form input[name="email"]')
    password_input = visible(driver, '#login_form input[name="passwd"]')
    email_input.clear()
    email_input.send_keys(email)
    password_input.clear()
    password_input.send_keys(password)
    visible(driver, "#login_form button[type='submit'], #login_form input[type='submit']").click()


def write_safe_log(log_path: Path, stage: str, result: str) -> None:
    if not re.fullmatch(r"[a-z0-9_]+", stage) or result not in {"started", "passed", "failed"}:
        raise ValueError("the browser QA log marker is not safe")
    line = f"ORDENOWA_ADMIN_PASSWORD_RESET stage={stage} result={result}\n"
    with log_path.open("a", encoding="utf-8") as log:
        log.write(line)
    sys.stdout.write(line)
    sys.stdout.flush()


def run() -> bool:
    try:
        config = validate_isolated_environment(dict(os.environ))
        dest = validate_artifact_directory(
            os.environ.get("QA_ARTIFACT_DIR", ""),
            os.environ.get("RUNNER_TEMP", ""),
        )
    except Exception as error:
        error_type = type(error).__name__
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", error_type):
            error_type = "Exception"
        sys.stderr.write(
            f"FAIL: isolated Back Office employee password recovery; stage=environment; exception={error_type}\n"
        )
        return False

    dest.mkdir(parents=True, exist_ok=True)
    log_path = dest / "admin-password-reset-e2e.log"
    log_path.write_text("", encoding="utf-8")
    driver = None
    stage = "browser_start"
    succeeded = False
    try:
        admin_password = os.environ["ADMIN_PASSWD"]
        admin_login_url = config["admin_login_url"]
        employee_email = config["employee_email"]
        mailpit_url = config["mailpit_api_url"]
        stage = "browser_start"
        write_safe_log(log_path, stage, "started")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        driver = new_driver()

        stage = "request_password_reset"
        driver.get(admin_login_url + "/login")
        visible(driver, "#login_form")
        visible(driver, "#forgot-password-link").click()
        email_field = visible(driver, "form#forgot_password_form input[type='email']")
        email_field.send_keys(employee_email)
        visible(
            driver,
            "form#forgot_password_form button[type='submit'], "
            "form#forgot_password_form input[type='submit']",
        ).click()
        WebDriverWait(driver, 30).until(lambda browser: visible_login_form(browser))
        if urlparse(driver.current_url).path != urlparse(admin_login_url).path + "/login":
            raise AssertionError("the employee reset request did not return to the Back Office login")
        if not driver.save_screenshot(str(dest / "admin-password-reset-request.png")):
            raise AssertionError("the reset request screenshot could not be saved")
        write_safe_log(log_path, stage, "passed")

        stage = "mailpit_delivery"
        reset_url = wait_for_employee_reset_url(mailpit_url, employee_email, admin_login_url)
        write_safe_log(log_path, stage, "passed")

        stage = "native_reset_form"
        driver.get(reset_url)
        validate_employee_reset_url(driver.current_url, admin_login_url)
        reset_passwords = WebDriverWait(driver, 30).until(
            lambda browser: (
                fields
                if len(fields := browser.find_elements(By.CSS_SELECTOR, "form#reset_password_form input[type='password']")) == 2
                and all(field.is_displayed() for field in fields)
                else False
            )
        )
        new_password = secrets.token_urlsafe(16) + "Az7!"
        reset_passwords[0].send_keys(new_password)
        reset_passwords[1].send_keys(new_password)
        visible(driver, "form#reset_password_form button[type='submit'], form#reset_password_form input[type='submit']").click()
        WebDriverWait(driver, 30).until(lambda browser: visible_login_form(browser))
        if urlparse(driver.current_url).path != urlparse(admin_login_url).path + "/login":
            raise AssertionError("the native employee reset form did not return to the Back Office login")
        write_safe_log(log_path, stage, "passed")

        stage = "old_password_rejected"
        fill_login(driver, admin_login_url, employee_email, admin_password)
        WebDriverWait(driver, 30).until(lambda browser: visible_login_form(browser))
        danger_alerts = driver.find_elements(By.CSS_SELECTOR, ".alert.alert-danger")
        if not any(alert.is_displayed() for alert in danger_alerts):
            raise AssertionError("the old employee password was not rejected with a login error")
        write_safe_log(log_path, stage, "passed")

        stage = "new_password_login"
        fill_login(driver, admin_login_url, employee_email, new_password)
        WebDriverWait(driver, 30).until(
            lambda browser: login_controller(browser.current_url, admin_login_url) == "AdminDashboard"
            and not visible_login_form(browser)
        )
        if not driver.save_screenshot(str(dest / "admin-password-reset-login.png")):
            raise AssertionError("the successful employee login screenshot could not be saved")
        write_safe_log(log_path, stage, "passed")
        succeeded = True
    except Exception as error:
        error_type = type(error).__name__
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", error_type):
            error_type = "Exception"
        try:
            write_safe_log(log_path, stage, "failed")
        except Exception:
            pass
        sys.stderr.write(
            f"FAIL: isolated Back Office employee password recovery; stage={stage}; exception={error_type}\n"
        )
        return False
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                succeeded = False
                try:
                    write_safe_log(log_path, "browser_cleanup", "failed")
                except Exception:
                    pass

    if succeeded:
        sys.stdout.write("PASS: native Back Office employee password recovery and login verified\n")
    return succeeded


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
