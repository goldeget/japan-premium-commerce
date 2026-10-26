#!/usr/bin/env python3
"""Native JA/EN/KO reset email acceptance using the existing isolated Mailpit.

Requires the same CI project and loopback endpoints as reset-email brand QA.
Creates disposable locale-specific customers, requests reset through the native UI,
and inspects Mailpit in memory. No message bodies, addresses, URLs, tokens, or
credentials are logged or saved. Generic bank account labels are forbidden.
Native order confirmation and price/shipping fields are outside this acceptance:
the existing tax order fixture explicitly uses Mail::METHOD_DISABLE.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

LANGUAGES = ('ja', 'en', 'ko')
MARKERS = {'ja': 'パスワード', 'en': 'password', 'ko': '비밀번호'}
SAFE_STAGES = {
    'context', 'seed', 'native_request_document', 'native_request_email_field',
    'native_request_submit_control', 'native_request_submit', 'native_request_readback',
    'captured_message', 'native_link_document', 'native_link_password_field',
    'native_link_confirmation_field', 'complete',
}
SAFE_EXCEPTION_TYPES = {
    'AssertionError', 'TimeoutException', 'ValueError', 'RuntimeError', 'URLError',
    'OSError', 'WebDriverException', 'ElementClickInterceptedException',
    'ElementNotInteractableException', 'StaleElementReferenceException',
    'NoSuchElementException', 'OtherError',
}
SAFE_MESSAGE_CHECKS = {
    'none', 'parts_missing', 'locale_marker_missing', 'raw_password_disclosure',
    'password_hash_disclosure', 'customer_secure_key_outside_reset_link',
    'generic_bank_details', 'reset_credentials_invalid', 'reset_link_origin_mismatch',
    'reset_link_path_mismatch', 'parts_credentials_mismatch',
    'html_reset_link_missing', 'text_reset_link_missing',
}
MAX_LINK_DIAGNOSTIC_COUNT = 20
PART_EVIDENCE_KEYS = {'required_link_candidate_count', 'native_route_candidate_count',
                      'reset_credential_candidate_count', 'native_reset_link_shape'}


class MessageValidationError(AssertionError):
    """A reset email failed one named predicate without retaining message data."""

    def __init__(self, check: str, part_evidence: dict | None = None) -> None:
        if check not in SAFE_MESSAGE_CHECKS - {'none'}:
            raise ValueError('unknown reset message check')
        self.check = check
        self.part_evidence = part_evidence
        super().__init__('native reset message check failed')


def safe_link_candidate_evidence(required_candidates: list[str], base: str, reset_path: str) -> dict:
    """Return only bounded counts and route-shape booleans, never link data."""
    candidates = {candidate.rstrip('.,);]') for candidate in required_candidates}
    credential_keys = {'token', 'reset_token', 'id_customer'}
    native_route_candidate_count = 0
    credential_candidate_count = 0
    native_reset_link_shape = False
    for candidate in candidates:
        query = parse_qs(urlparse(candidate).query, keep_blank_values=True)
        destination = urljoin(base + '/', candidate)
        has_native_route = (
            same_origin(destination, base)
            and unquote(urlparse(destination).path) == unquote(reset_path)
        )
        if has_native_route:
            native_route_candidate_count += 1
        if not (credential_keys & query.keys()):
            continue
        credential_candidate_count += 1
        if ('token' not in query or not ({'reset_token', 'id_customer'} & query.keys())
                or any(len(query[key]) != 1 or not query[key][0].strip()
                       for key in credential_keys & query.keys())):
            continue
        if has_native_route:
            native_reset_link_shape = True
    return {
        'required_link_candidate_count': min(len(candidates), MAX_LINK_DIAGNOSTIC_COUNT),
        'native_route_candidate_count': min(native_route_candidate_count, MAX_LINK_DIAGNOSTIC_COUNT),
        'reset_credential_candidate_count': min(credential_candidate_count, MAX_LINK_DIAGNOSTIC_COUNT),
        'native_reset_link_shape': native_reset_link_shape,
    }


def format_part_evidence(evidence: dict | None) -> str:
    if not isinstance(evidence, dict) or set(evidence) != {'html', 'text'}:
        return 'unavailable'
    rendered = []
    for part in ('html', 'text'):
        values = evidence.get(part)
        if (not isinstance(values, dict) or set(values) != PART_EVIDENCE_KEYS
                or type(values.get('required_link_candidate_count')) is not int
                or type(values.get('native_route_candidate_count')) is not int
                or type(values.get('reset_credential_candidate_count')) is not int
                or type(values.get('native_reset_link_shape')) is not bool
                or not 0 <= values['required_link_candidate_count'] <= MAX_LINK_DIAGNOSTIC_COUNT
                or not 0 <= values['native_route_candidate_count'] <= MAX_LINK_DIAGNOSTIC_COUNT
                or not 0 <= values['reset_credential_candidate_count'] <= MAX_LINK_DIAGNOSTIC_COUNT):
            return 'unavailable'
        rendered.append(
            f'{part}:refs={values["required_link_candidate_count"]},'
            f'native_route_refs={values["native_route_candidate_count"]},'
            f'credential_candidates={values["reset_credential_candidate_count"]},'
            f'native_shape={str(values["native_reset_link_shape"]).lower()}'
        )
    return ';'.join(rendered)


def write_diagnostics(result: dict) -> None:
    artifact_text, runner_temp = os.environ.get('QA_ARTIFACT_DIR', ''), os.environ.get('RUNNER_TEMP', '')
    if not artifact_text or not runner_temp:
        return
    artifact_dir, temp_dir = Path(artifact_text).resolve(), Path(runner_temp).resolve()
    try:
        artifact_dir.relative_to(temp_dir)
    except ValueError:
        return
    if artifact_dir == temp_dir:
        return
    part_evidence = result.get('message_part_evidence')
    valid_part_evidence = part_evidence is None or (
        isinstance(part_evidence, dict) and set(part_evidence) == {'html', 'text'}
        and all(isinstance(part_evidence.get(part), dict)
                and set(part_evidence[part]) == PART_EVIDENCE_KEYS
                and type(part_evidence[part].get('required_link_candidate_count')) is int
                and 0 <= part_evidence[part]['required_link_candidate_count'] <= MAX_LINK_DIAGNOSTIC_COUNT
                and type(part_evidence[part].get('native_route_candidate_count')) is int
                and 0 <= part_evidence[part]['native_route_candidate_count'] <= MAX_LINK_DIAGNOSTIC_COUNT
                and type(part_evidence[part].get('reset_credential_candidate_count')) is int
                and 0 <= part_evidence[part]['reset_credential_candidate_count'] <= MAX_LINK_DIAGNOSTIC_COUNT
                and type(part_evidence[part].get('native_reset_link_shape')) is bool
                for part in ('html', 'text'))
    )
    if (set(result) != {
            'status', 'language', 'stage', 'exception_type', 'response_status',
            'message_check', 'message_part_evidence',
            'same_origin', 'native_route', 'language_matches', 'email_field_present',
            'submit_control_present', 'submit_center_in_viewport',
            'submit_center_unobstructed', 'success_alert_present', 'reset_fields_present',
        }
            or not valid_part_evidence
            or result['status'] not in {'success', 'failure'}
            or result['language'] not in (*LANGUAGES, 'none')
            or result['stage'] not in SAFE_STAGES
            or result['message_check'] not in SAFE_MESSAGE_CHECKS
            or (result['exception_type'] is not None and result['exception_type'] not in SAFE_EXCEPTION_TYPES)
            or (result['response_status'] is not None and (
                type(result['response_status']) is not int or not 100 <= result['response_status'] <= 599
            ))
            or any(type(result[key]) is not bool for key in (
                'same_origin', 'native_route', 'language_matches', 'email_field_present',
                'submit_control_present', 'submit_center_in_viewport',
                'submit_center_unobstructed', 'success_alert_present', 'reset_fields_present'))):
        return
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / 'reset-email-locale-result.json').write_text(
        json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + '\n', encoding='utf-8'
    )


def navigation_status(driver):
    status = driver.execute_script("""
      const entries = performance.getEntriesByType('navigation');
      const entry = entries.length ? entries[0] : null;
      return entry && Number.isInteger(entry.responseStatus) ? entry.responseStatus : null;
    """)
    return status if type(status) is int and 100 <= status <= 599 else None


def native_password_route(current: str, expected: str, base: str) -> bool:
    if not same_origin(current, base):
        return False
    return unquote(urlparse(current).path) == unquote(urlparse(expected).path)


def endpoint(value: str, port: int) -> None:
    parsed = urlparse(value)
    try:
        loopback = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname or '').is_loopback
    except ValueError:
        loopback = False
    if (parsed.scheme != 'http' or not loopback or parsed.port != port
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('isolated loopback endpoint required')


def same_origin(value: str, base: str) -> bool:
    parsed, expected = urlparse(value), urlparse(base)
    return (parsed.username is None and parsed.password is None
            and (parsed.scheme, parsed.hostname, parsed.port)
            == (expected.scheme, expected.hostname, expected.port))


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self.text_fragments = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.hrefs.append(href)

    def handle_data(self, data):
        self.text_fragments.append(data)


def assert_message(message: dict, language: str, base: str, reset_path: str,
                   forbidden: dict[str, str]) -> str:
    html, text = message.get('HTML'), message.get('Text')
    if not isinstance(html, str) or not isinstance(text, str) or not html or not text:
        raise MessageValidationError('parts_missing')
    secret_categories = ('raw_password', 'password_hash', 'customer_secure_key')
    if (not isinstance(forbidden, dict) or set(forbidden) != set(secret_categories)
            or any(not isinstance(forbidden[key], str) or not forbidden[key] for key in secret_categories)):
        raise ValueError('native reset secret categories required')
    parser = Links()
    parser.feed(html)
    for visible in (' '.join(parser.text_fragments), text):
        without_urls = re.sub(r'https?://[^\s<>]+', '', visible)
        if MARKERS[language] not in without_urls.casefold():
            raise MessageValidationError('locale_marker_missing')
    for category, check in (('raw_password', 'raw_password_disclosure'),
                            ('password_hash', 'password_hash_disclosure')):
        if any(forbidden[category] in body for body in (html, text)):
            raise MessageValidationError(check)
    for body in (html, text):
        if re.search(r'account\s*(?:number|no\b)|口座番号|계좌\s*번호', body, re.I):
            raise MessageValidationError('generic_bank_details')
    verified_url = None
    verified_credentials = None
    credential_keys = {'token', 'reset_token', 'id_customer'}
    secure_key = forbidden['customer_secure_key']
    allowed_secure_key_occurrences = {'HTML': 0, 'Text': 0}
    html_visible_urls = re.findall(r'https?://[^\s<>"\']+', ' '.join(parser.text_fragments))
    text_urls = re.findall(r'https?://[^\s<>"\']+', text)
    part_candidates = (
        ('HTML', [*parser.hrefs, *html_visible_urls], parser.hrefs),
        ('Text', text_urls, text_urls),
    )
    part_evidence = {
        part.lower(): safe_link_candidate_evidence(
            list({candidate.rstrip('.,);]') for candidate in required_link_candidates}),
            base, reset_path,
        )
        for part, _, required_link_candidates in part_candidates
    }
    for part, candidates, required_link_candidates in part_candidates:
        required_candidates = {candidate.rstrip('.,);]') for candidate in required_link_candidates}
        required_reset_link_found = False
        for candidate in candidates:
            candidate = candidate.rstrip('.,);]')
            query = parse_qs(urlparse(candidate).query, keep_blank_values=True)
            if not (credential_keys & query.keys()):
                continue
            if ('token' not in query or not ({'reset_token', 'id_customer'} & query.keys())
                    or any(len(query[key]) != 1 or not query[key][0].strip()
                           for key in credential_keys & query.keys())):
                raise MessageValidationError('reset_credentials_invalid')
            destination = urljoin(base + '/', candidate)
            if not same_origin(destination, base):
                raise MessageValidationError('reset_link_origin_mismatch')
            if unquote(urlparse(destination).path) != unquote(reset_path):
                raise MessageValidationError('reset_link_path_mismatch')
            credentials = tuple((key, query[key][0]) for key in sorted(credential_keys & query.keys()))
            if verified_credentials is not None and credentials != verified_credentials:
                raise MessageValidationError('parts_credentials_mismatch')
            verified_credentials = credentials
            verified_url = verified_url or destination
            if candidate in required_candidates:
                required_reset_link_found = True
            if query.get('token') == [secure_key] and candidate.count(secure_key) == 1:
                allowed_secure_key_occurrences[part] += 1
        if not required_reset_link_found:
            raise MessageValidationError(f'{part.lower()}_reset_link_missing', part_evidence)
    for part, body in (('HTML', html), ('Text', text)):
        if body.count(secure_key) != allowed_secure_key_occurrences[part]:
            raise MessageValidationError('customer_secure_key_outside_reset_link')
    return verified_url


def assert_reset_page(driver, language: str, base: str, reset_path: str) -> None:
    if (not same_origin(driver.current_url, base)
            or unquote(urlparse(driver.current_url).path) != unquote(reset_path)):
        raise AssertionError('email recovery destination left native isolated route')
    document_language = driver.find_element('tag name', 'html').get_attribute('lang') or ''
    if document_language.lower().split('-')[0] != language:
        raise AssertionError('email recovery destination language mismatch')


def request_json(url: str) -> dict:
    with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=10) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError('unexpected capture response')
    return payload


def wait_message(api: str, email: str) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        listing = request_json(api + '/api/v1/messages?start=0&limit=100')
        for message in listing.get('messages', []):
            recipients = message.get('To', [])
            if any(isinstance(item, dict) and item.get('Address', '').lower() == email for item in recipients):
                identifier = message.get('ID') or message.get('Id')
                if isinstance(identifier, str) and identifier:
                    return request_json(api + '/api/v1/message/' + quote(identifier, safe=''))
        time.sleep(0.5)
    raise TimeoutError('isolated reset capture did not arrive')


SEED_PHP = r'''
if (getenv('CI') !== 'true' || getenv('GITHUB_ACTIONS') !== 'true' || getenv('KURANEA_ISOLATED_CI') !== '1'
    || !preg_match('/\A[0-9]+\z/D', (string) getenv('GITHUB_RUN_ID'))
    || !preg_match('/\A[0-9]+\z/D', (string) getenv('GITHUB_RUN_ATTEMPT'))
    || getenv('KURANEA_CI_PROJECT_NAME') !== 'kuranea-ci-' . getenv('GITHUB_RUN_ID') . '-' . getenv('GITHUB_RUN_ATTEMPT')) {
    throw new RuntimeException('isolated reset fixture context required');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require '/var/www/html/config/config.inc.php';
foreach (['PS_MAIL_METHOD' => '2', 'PS_MAIL_SERVER' => 'mailpit', 'PS_MAIL_SMTP_PORT' => '1025',
          'PS_MAIL_USER' => '', 'PS_MAIL_PASSWD' => '', 'PS_MAIL_SMTP_ENCRYPTION' => ''] as $key => $expected) {
    if ((string) Configuration::get($key) !== $expected) {
        throw new RuntimeException('existing isolated Mailpit configuration required');
    }
}
$iso = getenv('ORDENOWA_RESET_LOCALE');
if (!in_array($iso, ['ja', 'en', 'ko'], true)) { throw new RuntimeException('unsupported fixture locale'); }
$idLang = (int) Language::getIdByIso($iso, true);
$language = new Language($idLang);
if (!$idLang || !Validate::isLoadedObject($language) || !$language->active) {
    throw new RuntimeException('active native fixture language required');
}
$context = Context::getContext();
$context->language = $language;
$customer = new Customer();
$customer->firstname = 'ORDENOWA';
$customer->lastname = 'CI Reset Locale';
$customer->email = getenv('ORDENOWA_RESET_EMAIL');
$rawPassword = bin2hex(random_bytes(24));
$customer->passwd = Tools::hash($rawPassword);
$customer->secure_key = md5(bin2hex(random_bytes(16)));
$customer->id_lang = $idLang;
$customer->id_default_group = (int) Configuration::get('PS_CUSTOMER_GROUP');
$customer->id_shop = (int) $context->shop->id;
$customer->active = 1;
if (!$customer->add()) { throw new RuntimeException('isolated reset fixture creation failed'); }
echo json_encode(['url' => $context->link->getPageLink('password', null, $idLang),
                  'forbidden' => ['raw_password' => $rawPassword,
                                  'password_hash' => $customer->passwd,
                                  'customer_secure_key' => $customer->secure_key]], JSON_THROW_ON_ERROR);
'''


def seed(project: str, language: str, email: str) -> dict:
    command = ['docker', 'compose', '-p', project, 'exec', '-T', '--user', 'www-data']
    for key, value in {'CI': 'true', 'GITHUB_ACTIONS': 'true', 'KURANEA_ISOLATED_CI': '1',
                       'GITHUB_RUN_ID': os.environ['GITHUB_RUN_ID'],
                       'GITHUB_RUN_ATTEMPT': os.environ['GITHUB_RUN_ATTEMPT'],
                       'KURANEA_CI_PROJECT_NAME': project, 'ORDENOWA_RESET_LOCALE': language,
                       'ORDENOWA_RESET_EMAIL': email}.items():
        command += ['--env', key + '=' + value]
    result = subprocess.run(command + ['prestashop', 'php', '-r', SEED_PHP],
                            capture_output=True, text=True, timeout=45, check=False)
    if result.returncode:
        raise RuntimeError('isolated reset fixture preparation failed')
    return json.loads(result.stdout)


def validate_context() -> tuple[str, str, str]:
    run_id, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
    project = os.environ.get('CI_COMPOSE_PROJECT_NAME', '')
    if (any(os.environ.get(key) != value for key, value in
            {'CI': 'true', 'GITHUB_ACTIONS': 'true', 'KURANEA_ISOLATED_CI': '1'}.items())
            or not re.fullmatch(r'[0-9]+', run_id) or not re.fullmatch(r'[0-9]+', attempt)
            or project != f'kuranea-ci-{run_id}-{attempt}'):
        raise ValueError('exact isolated CI Compose project required')
    base, api = os.environ['SHOP_BASE_URL'].rstrip('/'), os.environ['MAILPIT_API_URL'].rstrip('/')
    endpoint(base, 18080)
    endpoint(api, 8025)
    return project, base, api


def run() -> bool:
    driver = None
    stage, language = 'context', 'none'
    diagnostic = {
        'status': 'failure', 'language': 'none', 'stage': 'context', 'exception_type': None,
        'message_check': 'none', 'message_part_evidence': None,
        'response_status': None, 'same_origin': False, 'native_route': False,
        'language_matches': False, 'email_field_present': False,
        'submit_control_present': False, 'submit_center_in_viewport': False,
        'submit_center_unobstructed': False, 'success_alert_present': False,
        'reset_fields_present': False,
    }
    try:
        project, base, api = validate_context()
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        for language in LANGUAGES:
            stage = 'seed'
            diagnostic.update(language=language, stage=stage, response_status=None,
                              message_check='none', message_part_evidence=None,
                              same_origin=False, native_route=False, language_matches=False,
                              email_field_present=False, submit_control_present=False,
                              submit_center_in_viewport=False, submit_center_unobstructed=False,
                              success_alert_present=False, reset_fields_present=False)
            email = f'ordenowa-reset-locale-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}-{language}-{secrets.token_hex(4)}@example.invalid'
            fixture = seed(project, language, email)
            if not same_origin(fixture['url'], base):
                raise AssertionError('native recovery route left isolated origin')
            options = Options()
            for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage'):
                options.add_argument(flag)
            options.add_argument('--window-size=1440,960')
            driver = webdriver.Chrome(options=options)
            stage = 'native_request_document'
            driver.get(fixture['url'])
            wait = WebDriverWait(driver, 30)
            diagnostic['response_status'] = navigation_status(driver)
            diagnostic['same_origin'] = same_origin(driver.current_url, base)
            diagnostic['native_route'] = native_password_route(driver.current_url, fixture['url'], base)
            stage = 'native_request_email_field'
            email_field = wait.until(EC.visibility_of_element_located((By.ID, 'email')))
            diagnostic['email_field_present'] = True
            email_field.send_keys(email)
            stage = 'native_request_submit_control'
            submit_control = wait.until(EC.element_to_be_clickable((By.ID, 'send-reset-link')))
            diagnostic['submit_control_present'] = True
            hit_test = driver.execute_script("""
              const element = arguments[0], box = element.getBoundingClientRect();
              const x = box.left + box.width / 2, y = box.top + box.height / 2;
              const inViewport = box.width > 0 && box.height > 0
                && x >= 0 && x < innerWidth && y >= 0 && y < innerHeight;
              const hit = inViewport ? document.elementFromPoint(x, y) : null;
              return {
                inViewport,
                unobstructed: Boolean(hit && (hit === element || element.contains(hit)))
              };
            """, submit_control)
            if isinstance(hit_test, dict):
                diagnostic['submit_center_in_viewport'] = hit_test.get('inViewport') is True
                diagnostic['submit_center_unobstructed'] = hit_test.get('unobstructed') is True
            if not diagnostic['submit_center_in_viewport'] or not diagnostic['submit_center_unobstructed']:
                raise AssertionError('native reset submit center is outside the unobstructed viewport')
            stage = 'native_request_submit'
            submit_control.click()
            stage = 'native_request_readback'
            success = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.alert-success')))
            diagnostic['success_alert_present'] = True
            if not success.text.strip() or not same_origin(driver.current_url, base):
                raise AssertionError('native reset request did not succeed')
            diagnostic['same_origin'] = same_origin(driver.current_url, base)
            diagnostic['native_route'] = native_password_route(driver.current_url, fixture['url'], base)
            document_language = (driver.find_element(By.TAG_NAME, 'html').get_attribute('lang') or '').lower().split('-')[0]
            diagnostic['language_matches'] = document_language == language
            if not diagnostic['language_matches']:
                raise AssertionError('native recovery response language mismatch')
            stage = 'captured_message'
            reset_path = urlparse(fixture['url']).path
            reset_url = assert_message(wait_message(api, email), language, base,
                                       reset_path, fixture['forbidden'])
            stage = 'native_link_document'
            driver.get(reset_url)
            diagnostic['response_status'] = navigation_status(driver)
            diagnostic['same_origin'] = same_origin(driver.current_url, base)
            diagnostic['native_route'] = native_password_route(driver.current_url, fixture['url'], base)
            stage = 'native_link_password_field'
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="passwd"]')))
            stage = 'native_link_confirmation_field'
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="confirmation"]')))
            diagnostic['reset_fields_present'] = True
            assert_reset_page(driver, language, base, reset_path)
            driver.quit()
            driver = None
            print(f'PASS: isolated native reset email locale={language}')
        stage = 'complete'
        diagnostic.update(status='success', language='ko', stage=stage, exception_type=None)
        return True
    except Exception as error:
        diagnostic['exception_type'] = type(error).__name__ if type(error).__name__ in SAFE_EXCEPTION_TYPES else 'OtherError'
        if isinstance(error, MessageValidationError):
            diagnostic['message_check'] = error.check
            diagnostic['message_part_evidence'] = error.part_evidence
        response_status = diagnostic['response_status']
        if type(response_status) is not int or not 100 <= response_status <= 599:
            response_status = 'unavailable'
        print(
            f'FAIL: isolated native reset email locale={language} stage={stage} '
            f'exception={diagnostic["exception_type"]}; response_status={response_status}; '
            f'message_check={diagnostic["message_check"]}; '
            f'message_parts={format_part_evidence(diagnostic["message_part_evidence"])}; '
            f'same_origin={str(diagnostic["same_origin"]).lower()}; '
            f'native_route={str(diagnostic["native_route"]).lower()}; '
            f'language_matches={str(diagnostic["language_matches"]).lower()}; '
            f'email_field={str(diagnostic["email_field_present"]).lower()}; '
            f'submit_control={str(diagnostic["submit_control_present"]).lower()}; '
            f'submit_center_in_viewport={str(diagnostic["submit_center_in_viewport"]).lower()}; '
            f'submit_center_unobstructed={str(diagnostic["submit_center_unobstructed"]).lower()}; '
            f'success_alert={str(diagnostic["success_alert_present"]).lower()}; '
            f'reset_fields={str(diagnostic["reset_fields_present"]).lower()}',
            file=sys.stderr,
        )
        return False
    finally:
        diagnostic['language'], diagnostic['stage'] = language, stage
        write_diagnostics(diagnostic)
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(0 if run() else 1)
