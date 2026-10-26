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
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

LANGUAGES = ('ja', 'en', 'ko')
MARKERS = {'ja': 'パスワード', 'en': 'password', 'ko': '비밀번호'}


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


def assert_message(message: dict, language: str, base: str, reset_path: str, forbidden: list[str]) -> str:
    html, text = message.get('HTML'), message.get('Text')
    if not isinstance(html, str) or not isinstance(text, str) or not html or not text:
        raise AssertionError('native reset email requires HTML and text')
    parser = Links()
    parser.feed(html)
    for visible in (' '.join(parser.text_fragments), text):
        without_urls = re.sub(r'https?://[^\s<>]+', '', visible)
        if MARKERS[language] not in without_urls.casefold():
            raise AssertionError('reset email language mismatch')
    for body in (html, text):
        if any(value and value in body for value in forbidden):
            raise AssertionError('credential disclosure in reset email')
        if re.search(r'account\s*(?:number|no\b)|口座番号|계좌\s*번호', body, re.I):
            raise AssertionError('generic bank account disclosure in reset email')
    verified_url = None
    verified_credentials = None
    credential_keys = {'token', 'reset_token', 'id_customer'}
    for candidates in (parser.hrefs, re.findall(r'https?://[^\s<>"\']+', text)):
        reset_links = []
        for candidate in candidates:
            candidate = candidate.rstrip('.,);]')
            query = parse_qs(urlparse(candidate).query, keep_blank_values=True)
            if not (credential_keys & query.keys()):
                continue
            if ('token' not in query or not ({'reset_token', 'id_customer'} & query.keys())
                    or any(len(query[key]) != 1 or not query[key][0].strip()
                           for key in credential_keys & query.keys())):
                raise AssertionError('reset email credentials are missing or ambiguous')
            destination = urljoin(base + '/', candidate)
            if not same_origin(destination, base):
                raise AssertionError('reset email link left isolated shop origin')
            if unquote(urlparse(destination).path) != unquote(reset_path):
                raise AssertionError('reset email link does not use native recovery path')
            credentials = tuple((key, query[key][0]) for key in sorted(credential_keys & query.keys()))
            if verified_credentials is not None and credentials != verified_credentials:
                raise AssertionError('reset email parts identify different recovery credentials')
            verified_credentials = credentials
            verified_url = verified_url or destination
            reset_links.append(destination)
        if not reset_links:
            raise AssertionError('native reset link missing from email part')
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
                  'forbidden' => [$rawPassword, $customer->passwd, $customer->secure_key]], JSON_THROW_ON_ERROR);
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
    try:
        project, base, api = validate_context()
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        for language in LANGUAGES:
            stage = 'seed'
            email = f'ordenowa-reset-locale-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}-{language}-{secrets.token_hex(4)}@example.invalid'
            fixture = seed(project, language, email)
            if not same_origin(fixture['url'], base):
                raise AssertionError('native recovery route left isolated origin')
            options = Options()
            for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage'):
                options.add_argument(flag)
            driver = webdriver.Chrome(options=options)
            stage = 'native_request'
            driver.get(fixture['url'])
            wait = WebDriverWait(driver, 30)
            wait.until(EC.visibility_of_element_located((By.ID, 'email'))).send_keys(email)
            wait.until(EC.element_to_be_clickable((By.ID, 'send-reset-link'))).click()
            success = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.alert-success')))
            if not success.text.strip() or not same_origin(driver.current_url, base):
                raise AssertionError('native reset request did not succeed')
            if driver.find_element(By.TAG_NAME, 'html').get_attribute('lang').split('-')[0] != language:
                raise AssertionError('native recovery response language mismatch')
            stage = 'captured_message'
            reset_path = urlparse(fixture['url']).path
            reset_url = assert_message(wait_message(api, email), language, base,
                                       reset_path, fixture['forbidden'])
            stage = 'native_link_destination'
            driver.get(reset_url)
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="passwd"]')))
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="confirmation"]')))
            assert_reset_page(driver, language, base, reset_path)
            driver.quit()
            driver = None
            print(f'PASS: isolated native reset email locale={language}')
        return True
    except Exception:
        print(f'FAIL: isolated native reset email locale={language} stage={stage}', file=sys.stderr)
        return False
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(0 if run() else 1)
