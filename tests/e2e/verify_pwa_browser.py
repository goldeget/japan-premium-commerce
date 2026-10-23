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
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # Pure manifest contract helpers remain importable without Selenium.
    webdriver = None
    TimeoutException = Exception
    Options = None
    By = None
    EC = None
    WebDriverWait = None

EXPECTED_SHOP_PORT = 18080


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


def response_has_private_cache_policy(headers: dict[str, object]) -> bool:
    cache_control = next(
        (value for key, value in headers.items() if key.lower() == "cache-control"),
        "",
    )
    if not isinstance(cache_control, str):
        return False
    directives = {part.split("=", 1)[0].strip().lower() for part in cache_control.split(",")}
    return bool({"private", "no-store"} & directives)


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


def wait_for_service_worker(driver: webdriver.Chrome) -> dict[str, object]:
    result = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        (async () => {
          if (!('serviceWorker' in navigator)) throw new Error('service workers unavailable');
          const registration = await navigator.serviceWorker.ready;
          if (!registration.active) throw new Error('no active service worker');
          if (!navigator.serviceWorker.controller) {
            await new Promise((resolve, reject) => {
              const timeout = setTimeout(() => reject(new Error('controller timeout')), 12000);
              navigator.serviceWorker.addEventListener('controllerchange', () => {
                clearTimeout(timeout); resolve();
              }, {once: true});
            });
          }
          const controller = navigator.serviceWorker.controller;
          if (!controller) throw new Error('page is not controlled');
          return {
            scope: registration.scope,
            activeState: registration.active.state,
            controllerScript: controller.scriptURL,
          };
        })().then(done).catch(error => done({error: String(error)}));
        """
    )
    if not isinstance(result, dict) or result.get("error"):
        raise AssertionError("service worker did not become active and control the page")
    return result


def matching_document_responses(
    driver: webdriver.Chrome, requested_url: str, shop_url: str
) -> list[dict[str, object]] | None:
    try:
        entries = driver.get_log("performance")
    except Exception:
        return None
    requested = urlparse(requested_url)
    requested_query = parse_qs(requested.query, keep_blank_values=True)
    responses: list[dict[str, object]] = []
    for entry in entries:
        try:
            event = json.loads(entry.get("message", "" )).get("message", {})
            method = event.get("method")
            params = event.get("params", {})
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
    driver: webdriver.Chrome, requested_url: str, shop_url: str, route_label: str
) -> dict[str, object]:
    responses = matching_document_responses(driver, requested_url, shop_url)
    if not responses:
        message = f"UNVERIFIED: document cache headers could not be observed for {route_label}."
        print(message, file=sys.stderr)
        raise AssertionError(message)

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
        "from_disk_cache": response.get("fromDiskCache") is True,
        "from_service_worker": response.get("fromServiceWorker") is True,
    }
    if not response_has_private_cache_policy(headers):
        directives = ",".join(
            sorted({part.split("=", 1)[0].strip().lower() for part in observed["cache_control"].split(",") if part.strip()})
        ) or "missing"
        message = (
            f"FAIL: {route_label} response lacks Cache-Control private/no-store semantics "
            f"(observed directives={directives}, pragma={observed['pragma_present']}, "
            f"expires={observed['expires_present']})."
        )
        print(message, file=sys.stderr)
        raise AssertionError(message)
    policy = "no-store" if "no-store" in observed["cache_control"].lower() else "private"
    print(f"PASS: {route_label} response uses Cache-Control {policy}.")
    return observed


def navigate_private_document(
    driver: webdriver.Chrome, requested_url: str, shop_url: str, route_label: str
) -> dict[str, object]:
    if not same_origin(shop_url, requested_url):
        raise AssertionError(f"{route_label} link left the isolated shop origin")
    try:
        driver.get_log("performance")
    except Exception:
        message = f"UNVERIFIED: Chrome performance response logging is unavailable for {route_label}."
        print(message, file=sys.stderr)
        raise AssertionError(message)
    driver.get(requested_url)
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    return assert_private_document_cache_headers(driver, requested_url, shop_url, route_label)


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
    except Exception:
        raise ChromeBrowserCdpError(f"Chrome rejected or did not answer {method}") from None
    finally:
        connection.session_id = previous_session

    if not isinstance(result, dict):
        raise ChromeBrowserCdpError(f"Chrome returned an invalid response for {method}")
    return result


class ChromeBrowserCdp:
    """Use Selenium's pinned websocket connection for response-checked CDP calls."""

    def __init__(self, connection) -> None:
        self.connection = connection
        self.closed = False

    @classmethod
    def connect(cls, driver: webdriver.Chrome) -> "ChromeBrowserCdp":
        try:
            _devtools, connection = driver.start_devtools()
        except Exception:
            raise ChromeBrowserCdpError("Chrome DevTools websocket could not be opened") from None
        return cls(connection)

    def execute(
        self,
        method: str,
        parameters: dict[str, object] | None = None,
        session_id: str | None = None,
    ) -> dict[str, object]:
        if self.closed:
            raise ChromeBrowserCdpError("Chrome DevTools websocket is closed")
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
            raise ChromeBrowserCdpError("Chrome DevTools websocket could not be closed") from None


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
        worker_cdp = connect_browser_cdp(driver)
        targets = worker_cdp.execute("Target.getTargets")["targetInfos"]
        worker_url = base_url.rstrip("/") + "/sw.js"
        worker = next(
            (target for target in targets
             if target["type"] == "service_worker" and target["url"] == worker_url),
            None,
        )
        if worker is None:
            raise AssertionError("the storefront service-worker target is unavailable")
        worker_session = worker_cdp.execute(
            "Target.attachToTarget", {"targetId": worker["targetId"], "flatten": True}
        ).get("sessionId")
        if not isinstance(worker_session, str) or not worker_session:
            raise ChromeBrowserCdpError("Chrome did not attach to the storefront worker")
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
        body = driver.find_element(By.TAG_NAME, "body").text
        if not any(text in body for text in (
            "インターネットに接続できません",
            "You are offline",
            "연결을 확인해 주세요",
        )):
            raise AssertionError("offline navigation did not show the localized fallback")
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


def create_session_customer(driver: webdriver.Chrome, base_url: str, email: str, password: str) -> str:
    driver.get(base_url + "/")
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
    driver.get(signin_url)
    registration = wait_visible(driver, 'a[data-link-action="display-register-form"]')
    registration_url = urljoin(driver.current_url, registration.get_attribute("href") or "")
    if not same_origin(base_url, registration_url):
        raise AssertionError("customer registration link escaped the isolated shop")
    driver.get(registration_url)
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
            label.click()
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
    submit = wait_visible(driver, "#customer-form button.form-control-submit")
    submit.click()
    WebDriverWait(driver, 30).until(
        lambda browser: browser.find_elements(By.ID, "identity_main_link")
        or browser.find_elements(By.ID, "userMenuButton")
    )
    account_url = authenticated_account_url(driver, base_url)
    navigate_private_document(driver, account_url, base_url, "authenticated account")
    wait_visible(driver, "#identity_main_link")
    page_text = driver.find_element(By.TAG_NAME, "body").text
    if "Pwa" not in page_text or "Session" not in page_text:
        raise AssertionError("authenticated account page did not show the synthetic customer")
    assert_empty_cache_storage(driver, "authenticated customer account")
    return account_url


def verify_logout_protection(
    driver: webdriver.Chrome,
    account_url: str,
    shop_url: str,
    first_name: str,
    last_name: str,
    email: str,
    screenshot: Path,
) -> None:
    signout = WebDriverWait(driver, 30).until(
        lambda browser: next(
            (link for link in browser.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
             if link.is_displayed() and link.is_enabled()),
            False,
        )
    )
    signout.click()
    WebDriverWait(driver, 30).until(
        lambda browser: not any(
            link.is_displayed()
            for link in browser.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
        )
    )
    navigate_private_document(driver, account_url, shop_url, "logged-out account")
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    if any(
        element.is_displayed() for element in driver.find_elements(By.ID, "identity_main_link")
    ):
        raise AssertionError("logged-out browser can still open the protected account page")
    if any(
        element.is_displayed() for element in driver.find_elements(By.ID, "userMenuButton")
    ):
        raise AssertionError("logged-out browser still shows an authenticated user menu")
    wait_visible(driver, "#login-form input[name='email']")
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if exposes_test_identity(body_text, first_name, last_name, email):
        raise AssertionError("protected account page exposed the synthetic customer's name after logout")
    driver.save_screenshot(str(screenshot))
    assert_empty_cache_storage(driver, "logged-out protected account route")

    for _ in range(2):
        driver.back()
        WebDriverWait(driver, 15).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if exposes_test_identity(body_text, first_name, last_name, email):
            raise AssertionError("browser history exposed the synthetic customer's name after logout")
    driver.get(account_url)
    wait_visible(driver, "#login-form input[name='email']")
    assert_empty_cache_storage(driver, "account route after browser back")


def run_viewport(base_url: str, artifact_dir: Path, width: int, height: int, label: str) -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = None
    stage = "chrome_start"
    primary_failure = False

    def update_offline_stage(next_stage: str) -> None:
        nonlocal stage
        stage = next_stage

    try:
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(width, height)
        stage = "network_enable"
        driver.execute_cdp_cmd("Network.enable", {})
        stage = "storefront_navigation"
        driver.get(base_url + "/")
        stage = "storefront_ready"
        WebDriverWait(driver, 40).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        stage = "manifest"
        manifest = verify_manifest(driver, base_url)
        driver.save_screenshot(str(artifact_dir / f"pwa-{label}-installability.png"))
        stage = "service_worker_registration"
        registration = wait_for_service_worker(driver)
        expected_scope = (urlparse(base_url).path.rstrip("/") or "") + "/"
        if registration.get("scope") != urljoin(base_url + "/", expected_scope):
            raise AssertionError("service worker registration escaped the storefront scope")
        if not same_origin(base_url, str(registration.get("controllerScript", ""))):
            raise AssertionError("service worker controller script left the isolated shop origin")
        expected_worker_path = (urlparse(base_url).path.rstrip("/") or "") + "/sw.js"
        if urlparse(str(registration.get("controllerScript", ""))).path != expected_worker_path:
            raise AssertionError("service worker controller is not the storefront worker")
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
        wait_for_service_worker(driver)
        assert_empty_cache_storage(driver, "after online refresh")

        stage = "offline_fallback"
        verify_offline_fallback(
            driver,
            base_url,
            artifact_dir / f"pwa-{label}-offline-fallback.png",
            update_offline_stage,
        )

        if label == "desktop":
            stage = "customer_account_setup"
            run_id = re.sub(r"[^0-9]", "", os.environ.get("GITHUB_RUN_ID", ""))
            attempt = re.sub(r"[^0-9]", "", os.environ.get("GITHUB_RUN_ATTEMPT", ""))
            unique = (run_id + attempt)[:20] or uuid.uuid4().hex[:16]
            email = f"qa-ordenowa-pwa-{unique}@example.invalid"
            password = f"Pwa-CI-{uuid.uuid4().hex[:20]}!"
            account_url = create_session_customer(driver, base_url, email, password)
            stage = "customer_private_routes"
            for route_stage, route_label, route_url in (
                ("customer_account_route", "authenticated account", account_url),
                (
                    "customer_cart_route",
                    "authenticated cart",
                    urljoin(base_url + "/", "index.php?controller=cart&action=show"),
                ),
                (
                    "customer_order_route",
                    "authenticated order",
                    urljoin(base_url + "/", "index.php?controller=order"),
                ),
            ):
                stage = route_stage
                navigate_private_document(driver, route_url, base_url, route_label)
                assert_empty_cache_storage(driver, route_label)
            stage = "customer_account_before_logout"
            navigate_private_document(driver, account_url, base_url, "authenticated account before logout")
            wait_visible(driver, "#identity_main_link")
            stage = "customer_logout"
            verify_logout_protection(
                driver,
                account_url,
                base_url,
                "Pwa",
                "Session",
                email,
                artifact_dir / "pwa-desktop-logged-out-account.png",
            )
        else:
            for route_stage, route in (
                ("guest_authentication_route", "index.php?controller=authentication"),
                ("guest_account_route", "index.php?controller=my-account"),
                ("guest_cart_route", "index.php?controller=cart&action=show"),
                ("guest_order_route", "index.php?controller=order"),
            ):
                stage = route_stage
                driver.get(urljoin(base_url + "/", route))
                WebDriverWait(driver, 30).until(
                    lambda browser: browser.execute_script("return document.readyState") == "complete"
                )
                assert_empty_cache_storage(driver, f"guest {route.split('?', 1)[-1].split('&', 1)[0]}")

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
        print(
            f"FAIL: {label} PWA browser QA at stage={stage} ({error_type}); path={safe_path}.",
            file=sys.stderr,
        )
        print(
            f"::error title=ORDENOWA PWA browser QA::{label}; stage={stage}; "
            f"exception={error_type}; path={safe_path}",
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
    failed = []
    for width, height, label in ((1440, 960, "desktop"), (390, 844, "mobile")):
        try:
            run_viewport(base_url, artifact_dir, width, height, label)
        except Exception as error:
            print(f"FAIL: {label} PWA browser QA ({type(error).__name__}).", file=sys.stderr)
            failed.append(label)
    print("INFO: real iOS and Android device installation was not tested.")
    print("INFO: Chromium headless installability prerequisites passed; native install prompt was not opened.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
