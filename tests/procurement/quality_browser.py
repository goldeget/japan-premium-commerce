#!/usr/bin/env python3
"""Read-only procurement quality acceptance. Only bounded, sanitized evidence persists.

Private routes must be no-store/noindex; their SEO score is intentionally not
applicable. The published anonymous policy retains SEO >=95. Event Timing below
is a controlled lab interaction measurement, never a field INP claim.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlencode, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
WIDTHS = (320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920)
PRIVATE_LABELS = ('assignments', 'assignment_detail', 'requests', 'request_detail', 'points', 'support')
LABELS = PRIVATE_LABELS + ('public_policy',)
REPRESENTATIVE = {'mobile': (390, 844), 'desktop': (1440, 1000)}
STAGE = 'isolation_guard'


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = load_module('procurement_shared_quality', ROOT / 'tests/performance/run_quality_audit.py')


def require(value: bool, code: str) -> None:
    if not value:
        raise shared.AuditFailure(code)


def guards() -> tuple[str, dict]:
    base = os.environ.get('SHOP_BASE_URL', '').rstrip('/')
    if base == 'http://127.0.0.1:18081' and os.environ.get('PS_DOMAIN') == 'localhost:18081':
        base = 'http://localhost:18081'
    parsed = urlparse(base)
    require(parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1') and parsed.port == 18081
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment, 'loopback_target_guard')
    require(os.environ.get('CI') == 'true' and os.environ.get('KURANEA_ISOLATED_CI') == '1', 'isolated_ci_guard')
    run = os.environ.get('GITHUB_RUN_ID', '') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '')
    require(bool(re.fullmatch(r'[0-9]+-[0-9]+', run)), 'run_identity_guard')
    require(os.environ.get('CI_COMPOSE_PROJECT_NAME') == 'ordenowa-procurement-ci-' + run, 'project_identity_guard')
    identity = json.loads(Path(os.environ['PROCUREMENT_IDENTITY_FILE']).read_text())
    require(identity.get('run') == run, 'fixture_identity_guard')
    require(Path(os.environ['QA_ARTIFACT_DIR']).is_absolute(), 'artifact_directory_guard')
    return base, identity


def driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--lang=ja-JP', '--window-size=1440,1000'):
        options.add_argument(flag)
    if os.environ.get('CHROME_BIN'):
        options.binary_location = os.environ['CHROME_BIN']
    driver_path = shutil.which('chromedriver')
    browser = webdriver.Chrome(options=options, service=Service(driver_path)) if driver_path else webdriver.Chrome(options=options)
    browser.set_script_timeout(30)
    return browser


def viewport(browser, width: int, height: int = 1000, color: str = 'light') -> None:
    browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width < 768,
    })
    browser.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': color}]})
    require(browser.execute_script('return window.innerWidth') == width, 'viewport_width_mismatch')


def settled(browser) -> None:
    WebDriverWait(browser, 30).until(lambda b: b.execute_script('return document.readyState') == 'complete')
    browser.execute_async_script('const done=arguments[0];document.fonts.ready.then(()=>requestAnimationFrame(()=>requestAnimationFrame(done)));')


def privacy_check(browser, label: str, route: str) -> dict:
    browser.get(route)
    settled(browser)
    language = browser.execute_script('return document.documentElement.lang')
    require(isinstance(language, str) and language.lower().split('-')[0] == 'ja', 'native_route_locale_mismatch')
    expected = {
        'assignments': '[data-testid="assignment-card"]', 'assignment_detail': '[data-testid="assignment-detail"]',
        'requests': '[data-testid="request-row"]', 'request_detail': '[data-testid="request-detail"]',
        'points': '[data-testid="points-balance"]', 'support': '[data-testid="support-message"]',
        'public_policy': '[data-testid="procurement-public-policy"]',
    }[label]
    require(bool(browser.find_elements(By.CSS_SELECTOR, expected)), 'expected_route_surface_missing')
    require(not browser.find_elements(By.CSS_SELECTOR, '#login-form,[data-testid="error"],[data-testid="support-error"]'), 'authentication_or_route_error')
    status = browser.execute_async_script('''
      const done=arguments[0];fetch(location.href,{credentials:'same-origin',cache:'no-store'})
      .then(r=>done({status:r.status,no_store:/(?:^|,)\\s*no-store\\b/i.test(r.headers.get('cache-control')||''),
        noindex:/noindex/i.test(r.headers.get('x-robots-tag')||'')||
          [...document.querySelectorAll('meta[name="robots"]')].some(m=>/noindex/i.test(m.content))}))
      .catch(()=>done({status:0,no_store:false,noindex:false}));
    ''')
    private = label in PRIVATE_LABELS
    require(status['status'] == 200, 'route_http_status_mismatch')
    require((status['no_store'] and status['noindex']) if private else not status['noindex'], 'route_indexability_security_mismatch')
    return {'route': label, 'locale': 'ja', 'document_locale_verified': True, 'status': 200,
            'no_store': status['no_store'], 'noindex': status['noindex'],
            'seo_applicability': 'not_applicable_private_noindex' if private else 'published_public_policy', 'passed': True}


def axe(browser, source: str, label: str, width: int, color: str) -> dict:
    browser.execute_script(source)
    scan = browser.execute_async_script('''
      const [tags,done]=arguments;
      axe.run(document,{runOnly:{type:'tag',values:tags}}).then(data=>{
        const safe=rows=>rows.map(r=>({id:r.id,impact:r.impact,nodes:r.nodes.map(()=>null)}));
        done({violations:safe(data.violations),incomplete:safe(data.incomplete)});
      }).catch(()=>done({error:true}));
    ''', list(shared.WCAG_TAGS))
    require(isinstance(scan, dict) and not scan.get('error'), 'axe_scan_failed')
    violations = shared.sanitized_rule_ids(scan['violations'])
    incomplete = shared.sanitized_rule_ids(scan['incomplete'])
    return {'route': label, 'width': width, 'color': color, 'wcag_tags': list(shared.WCAG_TAGS),
            'violation_rules': violations, 'incomplete_rules': incomplete, 'manual_review_required': bool(incomplete), 'passed': not violations}


def geometry(browser, label: str, width: int, color: str) -> dict:
    measured = browser.execute_script('''
      const images=[...document.querySelectorAll('[data-testid="product-photo"] img')].filter(i=>i.getClientRects().length);
      return {viewport:innerWidth,fit:Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)<=innerWidth+1,
        visible_image_count:images.length,images_bounded:images.every(i=>i.getBoundingClientRect().width<=innerWidth+1)};
    ''')
    return {'route': label, 'width': width, 'color': color, 'horizontal_fit': measured['fit'],
            'visible_public_image_count': measured['visible_image_count'], 'images_bounded': measured['images_bounded'],
            'passed': measured['viewport'] == width and measured['fit'] and measured['images_bounded']}


def interaction(browser, label: str, viewport_name: str) -> dict:
    # Native disclosure toggling is read-only and has a visible state change.
    # Product detail uses its actual gallery; other routes use the installation
    # instructions rendered by the same platform shell.
    controls = browser.find_elements(By.CSS_SELECTOR, '[data-testid="product-gallery"] > summary')
    kind = 'product_gallery_disclosure'
    if not controls:
        controls = browser.find_elements(By.CSS_SELECTOR, '[data-ordenowa-install] summary')
        kind = 'install_instructions_disclosure'
    require(bool(controls), 'readonly_interaction_control_missing')
    control = controls[0]
    # Browser theme enables smooth scrolling. A benchmark must position the
    # actual target before starting Event Timing rather than click midway
    # through that animation underneath the fixed navigation.
    browser.execute_script('arguments[0].scrollIntoView({block:"center",behavior:"instant"});', control)
    browser.execute_async_script('const done=arguments[0];requestAnimationFrame(()=>requestAnimationFrame(done));')
    require(browser.execute_script('''
      const e=arguments[0],r=e.getBoundingClientRect();
      const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
      return r.width>0&&r.height>0&&!!hit&&(hit===e||e.contains(hit));
    ''', control) is True, 'readonly_interaction_target_obscured')
    supported = browser.execute_script('''
      if(!PerformanceObserver.supportedEntryTypes.includes('event')||!performance.eventCounts)return false;
      const target=arguments[0];window.__owaQualityInteraction={trusted:false,entries:[],before:performance.eventCounts.get('click')||0,initial:target.parentElement.open};
      window.__owaQualityObserver=new PerformanceObserver(list=>{
        for(const e of list.getEntries())if(e.interactionId>0)window.__owaQualityInteraction.entries.push(e.duration);
      });window.__owaQualityObserver.observe({type:'event',durationThreshold:16});
      target.addEventListener('click',e=>{window.__owaQualityInteraction.trusted=e.isTrusted;},{once:true});return true;
    ''', control)
    require(supported is True, 'event_timing_api_unavailable')
    control.click()
    measured = browser.execute_async_script('''
      const [target,done]=arguments;
      requestAnimationFrame(()=>requestAnimationFrame(()=>setTimeout(()=>{
        const state=window.__owaQualityInteraction;
        const pending=window.__owaQualityObserver.takeRecords();
        for(const e of pending)if(e.interactionId>0)state.entries.push(e.duration);
        window.__owaQualityObserver.disconnect();
        done({trusted:state.trusted,changed:target.parentElement.open!==state.initial,
          clicks:(performance.eventCounts.get('click')||0)-state.before,durations:state.entries});
      },120)));
    ''', control)
    require(measured['trusted'] is True and measured['changed'] is True and measured['clicks'] >= 1, 'trusted_interaction_not_observed')
    durations = [float(value) for value in measured['durations'] if isinstance(value, (int, float)) and math.isfinite(value)]
    duration = max(durations) if durations else None
    # The browser reports event durations >=16ms. A verified trusted click with
    # no emitted entry is recorded as a bound, never fabricated as a zero.
    upper_bound = duration if duration is not None else 16.0
    return {'route': label, 'viewport': viewport_name, 'control': kind, 'metric': 'browser_event_timing_duration_ms',
            'duration_ms': duration, 'upper_bound_ms': upper_bound, 'reporting_threshold_ms': 16,
            'sample_kind': 'reported_event_timing' if duration is not None else 'below_reporting_threshold',
            'trusted_click': True, 'visible_state_changed': True, 'field_inp_measurement': False,
            'cpu_throttle_rate': 4 if viewport_name == 'mobile' else 1,
            'passed': upper_bound <= shared.TARGETS['scripted_interaction_next_paint_ms_lab_proxy_max']}


def lighthouse(browser, route: str, label: str, viewport_name: str) -> dict:
    address = browser.capabilities.get('goog:chromeOptions', {}).get('debuggerAddress', '')
    debug = urlparse('http://' + address)
    require(debug.hostname in ('localhost', '127.0.0.1') and isinstance(debug.port, int), 'local_debugger_guard')
    private = label in PRIVATE_LABELS
    # Keep native authentication while avoiding progressively warmed HTTP
    # caches across routes. Service-worker assets also use network-first reads.
    browser.execute_cdp_cmd('Network.clearBrowserCache', {})
    with tempfile.TemporaryDirectory(prefix='ordenowa-procurement-lighthouse-') as directory:
        report_path = Path(directory) / 'report.json'
        command = shared.lighthouse_command(route, viewport_name, report_path)
        if private:
            command = ['--only-categories=performance,accessibility' if arg.startswith('--only-categories=') else arg for arg in command]
        command += [f'--port={debug.port}', '--hostname=127.0.0.1', '--disable-storage-reset']
        completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        require(completed.returncode == 0 and report_path.is_file(), 'lighthouse_process_failed')
        report = json.loads(report_path.read_text())
        final = urlparse(report.get('finalDisplayedUrl') or report.get('finalUrl') or '')
        expected = urlparse(route)
        require((final.scheme, final.netloc, final.path.rstrip('/')) == (expected.scheme, expected.netloc, expected.path.rstrip('/'))
                and 'authentication' not in final.path
                and parse_qs(final.query).get('controller') != ['authentication'], 'lighthouse_authentication_redirect')
        for key in ('view', 'id_assignment', 'id_request', 'section'):
            if key in parse_qs(expected.query):
                require(parse_qs(final.query).get(key) == parse_qs(expected.query)[key], 'lighthouse_wrong_route')
        require(not report.get('runtimeError'), 'lighthouse_runtime_error')
        performance = shared.category_score(report, 'performance')
        accessibility = shared.category_score(report, 'accessibility')
        seo = None if private else shared.category_score(report, 'seo')
        lcp = shared.numeric_metric(report, 'metrics/largest-contentful-paint', 'largest-contentful-paint')
        cls = shared.numeric_metric(report, 'metrics/cumulative-layout-shift', 'cumulative-layout-shift')
        require(None not in (performance, accessibility, lcp, cls) and (private or seo is not None), 'lighthouse_required_metric_missing')
        floor = shared.TARGETS['performance_mobile_min' if viewport_name == 'mobile' else 'performance_desktop_min']
        failed_ids = [key for key, value in report.get('audits', {}).items() if shared.SAFE_RULE_ID.fullmatch(key)
                      and value.get('score') == 0 and value.get('scoreDisplayMode') not in ('notApplicable', 'manual')]
        return {'route': label, 'viewport': viewport_name, 'performance_score': performance, 'accessibility_score': accessibility,
                'seo_score': seo, 'seo_applicability': 'not_applicable_private_noindex' if private else 'published_public_policy',
                'lcp_ms': round(lcp, 1), 'cls': round(cls, 4), 'failed_audit_ids': sorted(failed_ids),
                'cache_state': 'http_cache_cleared_authentication_preserved',
                'throttling_method': report.get('configSettings', {}).get('throttlingMethod') if report.get('configSettings', {}).get('throttlingMethod') in ('simulate', 'devtools', 'provided') else 'unknown',
                'passed': performance >= floor and accessibility >= shared.TARGETS['accessibility_min']
                    and (private or seo >= shared.TARGETS['seo_min']) and lcp <= shared.TARGETS['lcp_ms_max'] and cls <= shared.TARGETS['cls_max']}


def main() -> int:
    global STAGE
    result = {'passed': False, 'scope': 'read_only_authenticated_procurement_and_anonymous_public_policy',
              'measured_locale': 'ja', 'other_locale_visual_review': 'separate_browser_acceptance',
              'targets': shared.TARGETS, 'required_widths': list(WIDTHS),
              'tool_versions': {'node': shared.EXPECTED_NODE_VERSION, 'lighthouse': shared.EXPECTED_LIGHTHOUSE_VERSION, 'axe': shared.EXPECTED_AXE_VERSION},
              'field_inp_status': 'NOT_TESTED_requires_field_observation',
              'wcag_scope': 'automated_WCAG_2_2_AA_tags_with_manual_incomplete_review',
              'privacy': [], 'layout': [], 'axe': [], 'interactions': [], 'lighthouse': [], 'failures': []}
    browsers = []
    destination = None
    try:
        base, identity = guards()
        destination = Path(os.environ['QA_ARTIFACT_DIR']) / 'procurement-quality-outcome.json'
        STAGE = 'locked_tool_versions'
        for package, version in (('lighthouse', shared.EXPECTED_LIGHTHOUSE_VERSION), ('axe-core', shared.EXPECTED_AXE_VERSION)):
            package_file = shared.PERFORMANCE_ROOT / 'node_modules' / package / 'package.json'
            require(package_file.is_file() and json.loads(package_file.read_text()).get('version') == version, 'locked_tool_version_mismatch')
        shared.assert_supported_axe_tags()
        axe_source = shared.AXE_SCRIPT.read_text()
        require(subprocess.run([shutil.which('node'), '--version'], capture_output=True, text=True).stdout.strip() == shared.EXPECTED_NODE_VERSION, 'node_version_mismatch')
        STAGE = 'native_customer_login'
        auth = load_module('procurement_readonly_auth', ROOT / 'tests/procurement/ci_browser.py')
        customer = driver(); browsers.append(customer)
        browser_major = str(customer.capabilities.get('browserVersion', '')).split('.')[0]
        result['tool_versions']['chromium_major'] = int(browser_major) if browser_major.isdigit() else None
        auth.login_customer(customer, 'a')
        auth.workspace(customer)
        assignment_id = int(auth.visible(customer, '[data-testid="assignment-card"]').get_attribute('data-assignment-id'))
        auth.workspace(customer, '&view=requests')
        request_id = int(auth.visible(customer, '[data-testid="request-row"]').get_attribute('data-request-id'))
        # Native generated paths carry the selected language. A raw module
        # query with id_lang can be canonicalized back to the cookie locale.
        native_routes = identity.get('routes', {}).get('ja', {})
        require(all(isinstance(native_routes.get(name), str) for name in ('workspace', 'support', 'policy')),
                'native_generated_routes_missing')
        origin = urlparse(base)
        require(all((urlparse(route).scheme, urlparse(route).netloc) == (origin.scheme, origin.netloc)
                    and not urlparse(route).username and not urlparse(route).password and not urlparse(route).fragment
                    for route in native_routes.values()), 'native_generated_route_origin_mismatch')
        def query(route: str, **parameters) -> str:
            return route + ('&' if '?' in route else '?') + urlencode(parameters)
        routes = {
            'assignments': query(native_routes['workspace'], view='assignments'),
            'assignment_detail': query(native_routes['workspace'], view='assignment', id_assignment=assignment_id),
            'requests': query(native_routes['workspace'], view='requests'),
            'request_detail': query(native_routes['workspace'], view='request', id_request=request_id),
            'points': query(native_routes['workspace'], view='points'),
            'support': query(native_routes['support'], id_request=request_id),
            'public_policy': query(native_routes['policy'], section='terms'),
        }
        anonymous = driver(); browsers.append(anonymous)
        for label in LABELS:
            selected = customer if label in PRIVATE_LABELS else anonymous
            STAGE = 'privacy_' + label
            result['privacy'].append(privacy_check(selected, label, routes[label]))
            routes[label] = selected.current_url
            for width in WIDTHS:
                for color in (('light', 'dark') if width in (390, 1440) else ('light',)):
                    STAGE = 'dom_' + label
                    viewport(selected, width, color=color)
                    selected.get(routes[label]); settled(selected)
                    result['layout'].append(geometry(selected, label, width, color))
                    result['axe'].append(axe(selected, axe_source, label, width, color))
            for name, size in REPRESENTATIVE.items():
                STAGE = 'interaction_' + label
                viewport(selected, *size)
                selected.get(routes[label]); settled(selected)
                try:
                    selected.execute_cdp_cmd('Emulation.setCPUThrottlingRate', {'rate': 4 if name == 'mobile' else 1})
                    result['interactions'].append(interaction(selected, label, name))
                finally:
                    selected.execute_cdp_cmd('Emulation.setCPUThrottlingRate', {'rate': 1})
        # DOM scans and controlled interactions precede navigation benchmarks.
        # Lighthouse attaches to the existing native authenticated browser and
        # disables storage resets; no cookies or extra-header files are exported.
        for label in LABELS:
            selected = customer if label in PRIVATE_LABELS else anonymous
            for name in REPRESENTATIVE:
                STAGE = 'lighthouse_' + label
                result['lighthouse'].append(lighthouse(selected, routes[label], label, name))
        expected_dom = len(LABELS) * (len(WIDTHS) + 2)
        result['passed'] = (len(result['privacy']) == len(LABELS)
            and len(result['layout']) == expected_dom and len(result['axe']) == expected_dom
            and len(result['interactions']) == len(LABELS) * 2 and len(result['lighthouse']) == len(LABELS) * 2
            and all(row['passed'] for group in ('privacy', 'layout', 'axe', 'interactions', 'lighthouse') for row in result[group]))
    except Exception as error:
        # Do not print exception bodies, URLs, selectors, HTML, credentials or
        # browser/driver stderr. Only fixed stages and bounded codes survive.
        result['failures'].append({'stage': STAGE, 'code': error.code if isinstance(error, shared.AuditFailure) else shared.safe_failure_code(type(error).__name__)})
    finally:
        for browser in browsers:
            try: browser.quit()
            except Exception: pass
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
            temporary.chmod(0o600); temporary.replace(destination)
    print('PASS' if result['passed'] else 'FAIL', 'procurement quality stage=' + STAGE)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
