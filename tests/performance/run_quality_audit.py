#!/usr/bin/env python3
"""Measure a small synthetic storefront surface with Lighthouse and axe-core."""
from __future__ import annotations

import json
import http.client
import math
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
PERFORMANCE_ROOT = ROOT / "tests" / "performance"
LIGHTHOUSE = PERFORMANCE_ROOT / "node_modules" / ".bin" / "lighthouse"
AXE_SCRIPT = PERFORMANCE_ROOT / "node_modules" / "axe-core" / "axe.min.js"
EXPECTED_NODE_VERSION = "v24.19.0"
EXPECTED_LIGHTHOUSE_VERSION = "13.5.0"
EXPECTED_AXE_VERSION = "4.14.0"
WCAG_TAGS = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa")
SAFE_RULE_ID = re.compile(r"\A[a-z0-9][a-z0-9-]{0,79}\Z")
SAFE_FAILURE_CODE = re.compile(r"\A[a-z0-9][a-z0-9_]{0,79}\Z")

TARGETS = {
    "performance_mobile_min": 90.0,
    "performance_desktop_min": 95.0,
    "accessibility_min": 95.0,
    "seo_min": 95.0,
    "lcp_ms_max": 2500.0,
    "cls_max": 0.1,
    "scripted_interaction_next_paint_ms_lab_proxy_max": 200.0,
}
VIEWPORTS = {"mobile": (390, 844), "desktop": (1440, 1000)}
ROUTE_LABELS = ("home", "product", "contact_ja")


class AuditFailure(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def safe_summary_path() -> Path:
    artifact_dir = Path(os.environ.get("QA_ARTIFACT_DIR", "/tmp/ordenowa-quality-audit"))
    return artifact_dir / "performance-accessibility-summary.json"


def write_summary(result: dict) -> None:
    path = safe_summary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def safe_failure_code(value: object) -> str:
    candidate = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value))
    candidate = re.sub(r"[^A-Za-z0-9]+", "_", candidate).strip("_").lower()
    return candidate if SAFE_FAILURE_CODE.fullmatch(candidate) else "audit_failure"


def preflight_exception_category(error: BaseException) -> str:
    """Return a fixed category without exposing exception text or request data."""
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(error, ssl.SSLError):
        return "tls_error"
    if isinstance(error, socket.gaierror):
        return "dns_error"
    if isinstance(error, ConnectionError):
        return "connection_error"
    if isinstance(error, URLError):
        reason = error.reason
        if isinstance(reason, BaseException):
            return preflight_exception_category(reason)
        return "url_error"
    if isinstance(error, http.client.HTTPException):
        return "protocol_error"
    if isinstance(error, OSError):
        return "network_error"
    return "request_error"


def preflight_routes(routes: dict[str, str], result: dict) -> dict[str, bool]:
    """Record bounded status evidence and continue independently across routes."""
    route_ready: dict[str, bool] = {}
    for label in ROUTE_LABELS:
        route = routes.get(label)
        if not isinstance(route, str):
            result["route_preflight"].append({
                "route": label,
                "status": None,
                "exception_category": "route_unavailable",
                "passed": False,
            })
            result["safe_failure_codes"].append("route_unreachable")
            route_ready[label] = False
            continue

        try:
            with urlopen(route) as response:
                status = response.status
            passed = isinstance(status, int) and status == 200
            category = None
        except HTTPError as error:
            status = error.code if isinstance(error.code, int) else None
            passed = False
            category = None if status is not None else "http_error"
        except Exception as error:
            status = None
            passed = False
            category = preflight_exception_category(error)

        result["route_preflight"].append({
            "route": label,
            "status": status,
            "exception_category": category,
            "passed": passed,
        })
        if not passed:
            result["safe_failure_codes"].append(
                "route_status_mismatch" if status is not None else "route_unreachable"
            )
        route_ready[label] = passed
    return route_ready


def preflight_summary(result: dict) -> str:
    rows = {row.get("route"): row for row in result.get("route_preflight", []) if isinstance(row, dict)}
    summary = []
    for label in ROUTE_LABELS:
        row = rows.get(label, {})
        status = row.get("status")
        if isinstance(status, int):
            outcome = str(status)
        else:
            category = row.get("exception_category")
            outcome = category if category in {
                "route_unavailable", "timeout", "tls_error", "dns_error", "connection_error",
                "url_error", "protocol_error", "network_error", "request_error", "http_error",
            } else "unavailable"
        summary.append(f"{label}:{outcome}")
    return ",".join(summary)


def require_isolated_loopback() -> tuple[str, dict[str, str]]:
    if os.environ.get("CI") != "true" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise AuditFailure("ci_only_guard")
    if os.environ.get("KURANEA_ISOLATED_CI") != "1":
        raise AuditFailure("isolated_ci_guard")
    base_url = os.environ.get("SHOP_BASE_URL", "").strip()
    parsed = urlparse(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise AuditFailure("loopback_target_guard")
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    product_id = os.environ.get("CI_TEST_VARIANT_PRODUCT_ID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,8}", product_id):
        raise AuditFailure("synthetic_product_fixture_guard")
    fixture_path = Path(os.environ.get("CONTACT_ROUTE_FIXTURE", ""))
    if not fixture_path.is_file():
        raise AuditFailure("contact_fixture_missing")
    try:
        contact_fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        contact_url = contact_fixture["urls_by_iso"]["ja"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        raise AuditFailure("contact_fixture_invalid") from None
    if not isinstance(contact_url, str):
        raise AuditFailure("contact_fixture_invalid")
    routes = {
        "home": base_url.rstrip("/") + "/",
        "product": urljoin(base_url.rstrip("/") + "/", f"index.php?controller=product&id_product={product_id}"),
        "contact_ja": contact_url,
    }
    parsed_origin = (parsed.scheme, parsed.hostname, parsed.port)
    for url in routes.values():
        target = urlparse(url)
        if (target.scheme, target.hostname, target.port) != parsed_origin or target.username or target.password:
            raise AuditFailure("same_origin_route_guard")
        if target.query and any(secret in target.query.casefold() for secret in ("token=", "passwd=", "password=", "email=")):
            raise AuditFailure("sensitive_route_guard")
    return base_url, routes


def numeric_metric(report: dict, *audit_ids: str) -> float | None:
    audits = report.get("audits", {})
    for audit_id in audit_ids:
        audit = audits.get(audit_id)
        value = audit.get("numericValue") if isinstance(audit, dict) else None
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def category_score(report: dict, category_id: str) -> float | None:
    category = report.get("categories", {}).get(category_id)
    score = category.get("score") if isinstance(category, dict) else None
    if isinstance(score, (int, float)) and math.isfinite(float(score)):
        return round(float(score) * 100, 1)
    return None


def lighthouse_command(route: str, viewport: str, report_path: Path) -> list[str]:
    node = shutil.which("node")
    if not node or not LIGHTHOUSE.is_file():
        raise AuditFailure("lighthouse_tool_missing")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
    if version.returncode != 0 or version.stdout.strip() != EXPECTED_NODE_VERSION:
        raise AuditFailure("node_version_mismatch")
    command = [
        node,
        str(LIGHTHOUSE),
        route,
        "--output=json",
        f"--output-path={report_path}",
        "--only-categories=performance,accessibility,seo",
        "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
        "--quiet",
    ]
    if viewport == "desktop":
        command.append("--preset=desktop")
    return command


def measure_lighthouse(label: str, route: str, viewport: str, result: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="ordenowa-lighthouse-") as temporary_dir:
        report_path = Path(temporary_dir) / "report.json"
        completed = subprocess.run(
            lighthouse_command(route, viewport, report_path),
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0 or not report_path.is_file():
            raise AuditFailure("lighthouse_process_failed")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise AuditFailure("lighthouse_report_invalid") from None

    performance = category_score(report, "performance")
    accessibility = category_score(report, "accessibility")
    seo = category_score(report, "seo")
    lcp_ms = numeric_metric(report, "metrics/largest-contentful-paint", "largest-contentful-paint")
    cls = numeric_metric(report, "metrics/cumulative-layout-shift", "cumulative-layout-shift")
    inp_ms = numeric_metric(report, "metrics/interaction-to-next-paint", "interaction-to-next-paint")
    if None in (performance, accessibility, seo, lcp_ms, cls):
        raise AuditFailure("lighthouse_required_metric_missing")

    minimum_performance = TARGETS["performance_mobile_min"] if viewport == "mobile" else TARGETS["performance_desktop_min"]
    passed = (
        performance >= minimum_performance
        and accessibility >= TARGETS["accessibility_min"]
        and seo >= TARGETS["seo_min"]
        and lcp_ms <= TARGETS["lcp_ms_max"]
        and cls <= TARGETS["cls_max"]
        and (inp_ms is None or inp_ms <= TARGETS["scripted_interaction_next_paint_ms_lab_proxy_max"])
    )
    metric = {
        "route": label,
        "viewport": viewport,
        "performance_score": performance,
        "accessibility_score": accessibility,
        "seo_score": seo,
        "lcp_ms": round(lcp_ms, 1),
        "cls": round(cls, 4),
        "lighthouse_inp_ms": round(inp_ms, 1) if inp_ms is not None else None,
        "lighthouse_inp_available": inp_ms is not None,
        "passed": passed,
    }
    result["lighthouse"].append(metric)
    return metric


def assert_supported_axe_tags() -> None:
    node = shutil.which("node")
    axe_package = PERFORMANCE_ROOT / "node_modules" / "axe-core"
    if not node or not axe_package.is_dir():
        raise AuditFailure("axe_inventory_check_unavailable")
    checker = (
        "const axe = require(process.argv[1]); "
        "const required = JSON.parse(process.argv[2]); "
        "const supported = new Set(axe.getRules().flatMap(rule => rule.tags)); "
        "process.stdout.write(JSON.stringify({missing: required.filter(tag => !supported.has(tag))}));"
    )
    checked = subprocess.run(
        [node, "-e", checker, str(axe_package), json.dumps(list(WCAG_TAGS))],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if checked.returncode != 0:
        raise AuditFailure("axe_inventory_check_failed")
    try:
        missing = json.loads(checked.stdout).get("missing")
    except (json.JSONDecodeError, AttributeError):
        raise AuditFailure("axe_inventory_check_invalid") from None
    if not isinstance(missing, list):
        raise AuditFailure("axe_inventory_check_invalid")
    if missing:
        raise AuditFailure("axe_tag_unsupported")


def make_driver(width: int, height: int) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    for flag in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--lang=ja-JP"):
        options.add_argument(flag)
    options.add_argument(f"--window-size={width},{height}")
    return webdriver.Chrome(options=options)


def sanitized_rule_ids(violations: list[dict]) -> list[dict]:
    output = []
    for violation in violations:
        rule_id = violation.get("id")
        if not isinstance(rule_id, str) or not SAFE_RULE_ID.fullmatch(rule_id):
            continue
        impact = violation.get("impact")
        if impact not in {"critical", "serious", "moderate", "minor"}:
            impact = "unknown"
        nodes = violation.get("nodes")
        output.append({
            "rule_id": rule_id,
            "impact": impact,
            "node_count": len(nodes) if isinstance(nodes, list) else 0,
        })
    return sorted(output, key=lambda item: (item["impact"], item["rule_id"]))


def axe_scan(driver: webdriver.Chrome, route_label: str, route: str, viewport: str, axe_source: str, result: dict) -> None:
    driver.get(route)
    driver.execute_script(axe_source)
    scan = driver.execute_async_script(
        """const done = arguments[arguments.length - 1];
           if (!window.axe || typeof window.axe.run !== 'function') { done({error: 'axe_missing'}); return; }
           window.axe.run(document, {runOnly: {type: 'tag', values: arguments[0]}})
             .then((data) => done({violations: data.violations, incomplete: data.incomplete}))
             .catch(() => done({error: 'axe_run_failed'}));""",
        list(WCAG_TAGS),
    )
    if not isinstance(scan, dict) or scan.get("error"):
        raise AuditFailure("axe_scan_failed")
    violations = sanitized_rule_ids(scan.get("violations", []))
    incomplete = sanitized_rule_ids(scan.get("incomplete", []))
    result["axe"].append({
        "route": route_label,
        "viewport": viewport,
        "wcag_tags": list(WCAG_TAGS),
        "violation_rules": violations,
        "incomplete_rules": incomplete,
        "passed": not violations,
        "manual_review_required": bool(incomplete),
    })


def measure_scripted_interaction(driver: webdriver.Chrome, viewport: str, result: dict) -> None:
    driver.get(urljoin(os.environ["SHOP_BASE_URL"].rstrip("/") + "/", "/"))
    driver.execute_script(
        """window.__ordenowaInteractionResult = null;
           window.addEventListener('click', (event) => {
             const control = event.target && event.target.closest('[data-bs-target="#searchCanvas"]');
             if (!control) return;
             const start = event.timeStamp;
             requestAnimationFrame(() => requestAnimationFrame(() => {
               const panel = document.querySelector('#searchCanvas');
               window.__ordenowaInteractionResult = {
                 latency_ms: Math.max(0, performance.now() - start),
                 opened: Boolean(panel && panel.classList.contains('show'))
               };
             }));
           }, {capture: true, once: false});"""
    )
    try:
        control = driver.find_element(By.CSS_SELECTOR, '[data-bs-target="#searchCanvas"]')
    except Exception:
        raise AuditFailure("interaction_control_missing") from None
    if not control.is_displayed() or not control.is_enabled():
        raise AuditFailure("interaction_control_unavailable")
    control.click()
    try:
        measured = WebDriverWait(driver, 10).until(
            lambda browser: browser.execute_script("return window.__ordenowaInteractionResult")
        )
    except Exception:
        raise AuditFailure("interaction_measurement_missing") from None
    if (not isinstance(measured, dict) or measured.get("opened") is not True
            or not isinstance(measured.get("latency_ms"), (int, float))
            or not math.isfinite(float(measured["latency_ms"]))):
        raise AuditFailure("interaction_result_invalid")
    latency_ms = round(float(measured["latency_ms"]), 1)
    result["scripted_interaction_lab_proxy"].append({
        "route": "home",
        "viewport": viewport,
        "metric": "scripted_click_to_next_paint_ms_lab_proxy",
        "latency_ms": latency_ms,
        "target_opened": True,
        "inp_field_measurement": False,
        "passed_lab_proxy_budget": latency_ms <= TARGETS["scripted_interaction_next_paint_ms_lab_proxy_max"],
    })


def main() -> int:
    result = {
        "schema": 1,
        "source_sha": os.environ.get("GITHUB_SHA", "")[:40],
        "tool_versions": {"node": EXPECTED_NODE_VERSION, "lighthouse": EXPECTED_LIGHTHOUSE_VERSION, "axe_core": EXPECTED_AXE_VERSION},
        "targets": TARGETS,
        "route_preflight": [],
        "lighthouse": [],
        "axe": [],
        "scripted_interaction_lab_proxy": [],
        "overall": "pending",
        "safe_failure_codes": [],
    }
    write_summary(result)
    try:
        _, routes = require_isolated_loopback()
        lighthouse_package = json.loads((PERFORMANCE_ROOT / "node_modules" / "lighthouse" / "package.json").read_text(encoding="utf-8"))
        axe_package = json.loads((PERFORMANCE_ROOT / "node_modules" / "axe-core" / "package.json").read_text(encoding="utf-8"))
        if lighthouse_package.get("version") != EXPECTED_LIGHTHOUSE_VERSION or axe_package.get("version") != EXPECTED_AXE_VERSION:
            raise AuditFailure("audit_tool_version_mismatch")
        if not AXE_SCRIPT.is_file():
            raise AuditFailure("axe_tool_missing")
        assert_supported_axe_tags()
        axe_source = AXE_SCRIPT.read_text(encoding="utf-8")

        route_ready = preflight_routes(routes, result)
        write_summary(result)

        for label in ROUTE_LABELS:
            route = routes.get(label)
            if not route_ready.get(label) or not isinstance(route, str):
                continue
            for viewport in VIEWPORTS:
                try:
                    measure_lighthouse(label, route, viewport, result)
                except AuditFailure as error:
                    result["safe_failure_codes"].append(safe_failure_code(error.code))
                    write_summary(result)

        for viewport, size in VIEWPORTS.items():
            driver = None
            try:
                driver = make_driver(*size)
                if not result.get("browser_version"):
                    result["browser_version"] = str(driver.capabilities.get("browserVersion", "unknown"))[:40]
                for label in ROUTE_LABELS:
                    route = routes.get(label)
                    if not route_ready.get(label) or not isinstance(route, str):
                        continue
                    try:
                        axe_scan(driver, label, route, viewport, axe_source, result)
                    except AuditFailure as error:
                        result["safe_failure_codes"].append(safe_failure_code(error.code))
                    if label == "home":
                        try:
                            measure_scripted_interaction(driver, viewport, result)
                        except AuditFailure as error:
                            result["safe_failure_codes"].append(safe_failure_code(error.code))
            except Exception as error:
                result["safe_failure_codes"].append(safe_failure_code(type(error).__name__))
            finally:
                if driver:
                    driver.quit()

        all_routes_ready = len(result["route_preflight"]) == len(ROUTE_LABELS) and all(
            item["passed"] for item in result["route_preflight"]
        )
        lighthouse_passed = all_routes_ready and len(result["lighthouse"]) == len(ROUTE_LABELS) * len(VIEWPORTS) and all(item["passed"] for item in result["lighthouse"])
        axe_passed = all_routes_ready and len(result["axe"]) == len(ROUTE_LABELS) * len(VIEWPORTS) and all(item["passed"] for item in result["axe"])
        interaction_passed = len(result["scripted_interaction_lab_proxy"]) == len(VIEWPORTS) and all(
            item["passed_lab_proxy_budget"] for item in result["scripted_interaction_lab_proxy"]
        )
        result["overall"] = "success" if lighthouse_passed and axe_passed and interaction_passed and not result["safe_failure_codes"] else "failure"
    except AuditFailure as error:
        result["safe_failure_codes"].append(safe_failure_code(error.code))
        result["overall"] = "failure"
    except Exception as error:
        result["safe_failure_codes"].append(safe_failure_code(type(error).__name__))
        result["overall"] = "failure"
    finally:
        result["safe_failure_codes"] = sorted(set(result["safe_failure_codes"]))
        write_summary(result)

    print(
        "ORDENOWA_PERF_A11Y_OUTCOME: "
        f"{result['overall']} lighthouse={len(result['lighthouse'])}/{len(routes) * len(VIEWPORTS) if 'routes' in locals() else 0} "
        f"axe={len(result['axe'])}/{len(routes) * len(VIEWPORTS) if 'routes' in locals() else 0} "
        f"interaction_lab_proxy={len(result['scripted_interaction_lab_proxy'])}/{len(VIEWPORTS)} "
        f"route_preflight={preflight_summary(result)} "
        f"safe_failure_codes={','.join(result['safe_failure_codes']) if result['safe_failure_codes'] else 'none'}"
    )
    return 0 if result["overall"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
