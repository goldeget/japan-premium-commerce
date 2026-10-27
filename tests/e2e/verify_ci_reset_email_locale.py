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
from email import policy
from email.parser import BytesParser
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
    'html_reset_link_missing', 'text_reset_link_missing', 'raw_message_unavailable',
    'html_mime_part_missing', 'html_mime_part_ambiguous',
    'text_mime_part_missing', 'text_mime_part_ambiguous', 'mime_part_decode_failed',
}
MAX_LINK_DIAGNOSTIC_COUNT = 20
MAX_RAW_MESSAGE_BYTES = 512 * 1024
SAFE_TEMPLATE_CANDIDATES = {
    'active_theme', 'parent_theme', 'shop_root', 'module_fallback', 'other', 'missing', 'unavailable',
}
SAFE_TEMPLATE_ISOS = {'ja', 'en', 'ko', 'other', 'none'}
SAFE_TEMPLATE_TEXT_SOURCES = {'text_template', 'html_to_text', 'none', 'unavailable'}
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
        if (not credential_keys.issubset(query.keys())
                or any(len(query[key]) != 1 or not query[key][0].strip()
                       for key in credential_keys if key in query)):
            continue
        if has_native_route:
            native_reset_link_shape = True
    return {
        'required_link_candidate_count': min(len(candidates), MAX_LINK_DIAGNOSTIC_COUNT),
        'native_route_candidate_count': min(native_route_candidate_count, MAX_LINK_DIAGNOSTIC_COUNT),
        'reset_credential_candidate_count': min(credential_candidate_count, MAX_LINK_DIAGNOSTIC_COUNT),
        'native_reset_link_shape': native_reset_link_shape,
    }


def text_has_native_reset_link_shape(text: str, base: str, reset_path: str) -> bool:
    candidates = re.findall(r'https?://[^\s<>"\']+', text)
    evidence = safe_link_candidate_evidence(candidates, base, reset_path)
    return evidence['native_reset_link_shape']


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
            'raw_text_native_link_shape', 'mailpit_preview_text_native_link_shape',
            'mailpit_preview_text_shape_match', 'pre_smtp_html_native_link_shape',
            'pre_smtp_text_native_link_shape', 'pre_smtp_reset_url_candidate_found',
            'pre_smtp_reset_template_context_recognized',
            'pre_smtp_template_url_candidate_present', 'pre_smtp_template_url_credentials_complete',
            'pre_smtp_template_url_native_route', 'pre_smtp_html_url_candidate_present',
            'pre_smtp_html_token_present', 'pre_smtp_html_reset_token_present',
            'pre_smtp_html_id_customer_present', 'pre_smtp_html_scheme_host_port_match',
            'pre_smtp_html_path_match', 'pre_smtp_html_credentials_complete',
            'pre_smtp_html_candidate_selected',
            'pre_smtp_text_setter_available', 'pre_smtp_text_setter_invoked',
            'mail_type', 'template_candidate', 'template_iso', 'text_source',
            'text_template_present', 'text_template_has_url',
            'html_template_present', 'html_template_has_url',
            'same_origin', 'native_route', 'language_matches', 'email_field_present',
            'submit_control_present', 'submit_center_in_viewport',
            'submit_center_unobstructed', 'success_alert_present', 'reset_fields_present',
        }
            or not valid_part_evidence
            or result['status'] not in {'success', 'failure'}
            or result['language'] not in (*LANGUAGES, 'none')
            or result['stage'] not in SAFE_STAGES
            or result['message_check'] not in SAFE_MESSAGE_CHECKS
            or result['mail_type'] not in (None, 1, 2, 3, 4)
            or result['template_candidate'] not in SAFE_TEMPLATE_CANDIDATES
            or result['template_iso'] not in SAFE_TEMPLATE_ISOS
            or result['text_source'] not in SAFE_TEMPLATE_TEXT_SOURCES
            or any(result[key] is not None and type(result[key]) is not bool for key in (
                'raw_text_native_link_shape', 'mailpit_preview_text_native_link_shape',
                'mailpit_preview_text_shape_match', 'pre_smtp_html_native_link_shape',
                'pre_smtp_text_native_link_shape', 'pre_smtp_reset_url_candidate_found',
                'pre_smtp_reset_template_context_recognized',
                'pre_smtp_template_url_candidate_present', 'pre_smtp_template_url_credentials_complete',
                'pre_smtp_template_url_native_route', 'pre_smtp_html_url_candidate_present',
                'pre_smtp_html_token_present', 'pre_smtp_html_reset_token_present',
                'pre_smtp_html_id_customer_present', 'pre_smtp_html_scheme_host_port_match',
                'pre_smtp_html_path_match', 'pre_smtp_html_credentials_complete',
                'pre_smtp_html_candidate_selected',
                'pre_smtp_text_setter_available', 'pre_smtp_text_setter_invoked'))
            or (result['exception_type'] is not None and result['exception_type'] not in SAFE_EXCEPTION_TYPES)
            or (result['response_status'] is not None and (
                type(result['response_status']) is not int or not 100 <= result['response_status'] <= 599
            ))
            or any(type(result[key]) is not bool for key in (
                'text_template_present', 'text_template_has_url',
                'html_template_present', 'html_template_has_url',
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


def parse_raw_mime_parts(source: bytes) -> tuple[str, str]:
    if not isinstance(source, bytes) or not source or len(source) > MAX_RAW_MESSAGE_BYTES:
        raise MessageValidationError('raw_message_unavailable')
    try:
        parsed = BytesParser(policy=policy.default).parsebytes(source)
        parts = {'html': [], 'text': []}

        def collect_body_parts(part) -> None:
            content_type = part.get_content_type().lower()
            if (part.get_content_disposition() == 'attachment'
                    or part.get_filename() is not None
                    or content_type in {'message/rfc822', 'message/global', 'message/delivery-status'}):
                return
            if part.is_multipart():
                for child in part.iter_parts():
                    collect_body_parts(child)
                return
            key = 'html' if content_type == 'text/html' else 'text' if content_type == 'text/plain' else None
            if key is not None:
                content = part.get_content()
                if not isinstance(content, str):
                    raise MessageValidationError('mime_part_decode_failed')
                parts[key].append(content)

        collect_body_parts(parsed)
    except MessageValidationError:
        raise
    except Exception:
        raise MessageValidationError('mime_part_decode_failed') from None
    for key in ('html', 'text'):
        if not parts[key]:
            raise MessageValidationError(f'{key}_mime_part_missing')
        if len(parts[key]) != 1:
            raise MessageValidationError(f'{key}_mime_part_ambiguous')
    return parts['html'][0], parts['text'][0]


def read_raw_mime_parts(api: str, message: dict, diagnostic: dict | None = None) -> tuple[str, str]:
    identifier = message.get('ID') or message.get('Id')
    if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
        raise MessageValidationError('raw_message_unavailable')
    try:
        request = Request(api + '/api/v1/message/' + quote(identifier, safe='') + '/raw',
                          headers={'Accept': 'text/plain'})
        with urlopen(request, timeout=10) as response:
            source = response.read(MAX_RAW_MESSAGE_BYTES + 1)
    except Exception:
        raise MessageValidationError('raw_message_unavailable') from None
    if diagnostic is not None:
        diagnostic.update(pre_smtp_message_shape_headers(source))
    return parse_raw_mime_parts(source)


def pre_smtp_message_shape_headers(source: bytes) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {
        'pre_smtp_html_native_link_shape': None,
        'pre_smtp_text_native_link_shape': None,
        'pre_smtp_reset_url_candidate_found': None,
        'pre_smtp_reset_template_context_recognized': None,
        'pre_smtp_template_url_candidate_present': None,
        'pre_smtp_template_url_credentials_complete': None,
        'pre_smtp_template_url_native_route': None,
        'pre_smtp_html_url_candidate_present': None,
        'pre_smtp_html_token_present': None,
        'pre_smtp_html_reset_token_present': None,
        'pre_smtp_html_id_customer_present': None,
        'pre_smtp_html_scheme_host_port_match': None,
        'pre_smtp_html_path_match': None,
        'pre_smtp_html_credentials_complete': None,
        'pre_smtp_html_candidate_selected': None,
        'pre_smtp_text_setter_available': None,
        'pre_smtp_text_setter_invoked': None,
    }
    try:
        message = BytesParser(policy=policy.default).parsebytes(source)
    except Exception:
        return result
    for name, key in (
        ('X-ORDENOWA-CI-Pre-SMTP-HTML-Native-Reset-Link', 'pre_smtp_html_native_link_shape'),
        ('X-ORDENOWA-CI-Pre-SMTP-Text-Native-Reset-Link', 'pre_smtp_text_native_link_shape'),
        ('X-ORDENOWA-CI-Reset-URL-Candidate-Found', 'pre_smtp_reset_url_candidate_found'),
        ('X-ORDENOWA-CI-Reset-Template-Context-Recognized', 'pre_smtp_reset_template_context_recognized'),
        ('X-ORDENOWA-CI-Reset-Template-URL-Candidate-Present', 'pre_smtp_template_url_candidate_present'),
        ('X-ORDENOWA-CI-Reset-Template-URL-Credentials-Complete', 'pre_smtp_template_url_credentials_complete'),
        ('X-ORDENOWA-CI-Reset-Template-URL-Native-Route', 'pre_smtp_template_url_native_route'),
        ('X-ORDENOWA-CI-Reset-HTML-URL-Candidate-Present', 'pre_smtp_html_url_candidate_present'),
        ('X-ORDENOWA-CI-Reset-HTML-Token-Present', 'pre_smtp_html_token_present'),
        ('X-ORDENOWA-CI-Reset-HTML-Reset-Token-Present', 'pre_smtp_html_reset_token_present'),
        ('X-ORDENOWA-CI-Reset-HTML-Customer-ID-Present', 'pre_smtp_html_id_customer_present'),
        ('X-ORDENOWA-CI-Reset-HTML-Scheme-Host-Port-Match', 'pre_smtp_html_scheme_host_port_match'),
        ('X-ORDENOWA-CI-Reset-HTML-Path-Match', 'pre_smtp_html_path_match'),
        ('X-ORDENOWA-CI-Reset-HTML-Credentials-Complete', 'pre_smtp_html_credentials_complete'),
        ('X-ORDENOWA-CI-Reset-HTML-Candidate-Selected', 'pre_smtp_html_candidate_selected'),
        ('X-ORDENOWA-CI-Text-Setter-Available', 'pre_smtp_text_setter_available'),
        ('X-ORDENOWA-CI-Text-Setter-Invoked', 'pre_smtp_text_setter_invoked'),
    ):
        values = message.get_all(name, [])
        if len(values) == 1 and str(values[0]).strip().lower() in {'true', 'false'}:
            result[key] = str(values[0]).strip().lower() == 'true'
    return result


def assert_message(message: dict, language: str, base: str, reset_path: str,
                   forbidden: dict[str, str], raw_mime_parts: tuple[str, str] | None = None) -> str:
    html, text = raw_mime_parts if raw_mime_parts is not None else (message.get('HTML'), message.get('Text'))
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
            if (not credential_keys.issubset(query.keys())
                    or any(len(query[key]) != 1 or not query[key][0].strip()
                           for key in credential_keys if key in query)):
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
$templateEvidence = [
    'mail_type' => (int) Configuration::get('PS_MAIL_TYPE'),
    'template_candidate' => 'unavailable',
    'template_iso' => 'none',
    'text_source' => 'unavailable',
    'text_template_present' => false,
    'text_template_has_url' => false,
    'html_template_present' => false,
    'html_template_has_url' => false,
];
try {
    $getTemplateBasePath = new ReflectionMethod(Mail::class, 'getTemplateBasePath');
    $getTemplateBasePath->setAccessible(true);
    $mailType = $templateEvidence['mail_type'];
    $defaultIso = Language::getIsoById((int) Configuration::get('PS_LANG_DEFAULT'));
    $templateIsos = [$iso];
    if ($defaultIso && $iso !== $defaultIso) {
        $templateIsos[] = $defaultIso;
    }
    if (!in_array('en', $templateIsos, true)) {
        $templateIsos[] = 'en';
    }
    $templateEvidence['text_source'] = $mailType === Mail::TYPE_BOTH_AUTOMATIC_TEXT
        ? 'html_to_text'
        : (in_array($mailType, [Mail::TYPE_BOTH, Mail::TYPE_TEXT], true) ? 'text_template' : 'none');
    $requiredText = in_array($mailType, [Mail::TYPE_BOTH, Mail::TYPE_TEXT], true);
    $requiredHtml = in_array($mailType, [Mail::TYPE_HTML, Mail::TYPE_BOTH, Mail::TYPE_BOTH_AUTOMATIC_TEXT], true);
    $foundTemplate = false;
    foreach ($templateIsos as $templateIso) {
        $templateBasePath = (string) $getTemplateBasePath->invoke(
            null,
            $templateIso . '/password_query',
            false,
            $context->shop->theme
        );
        if ($templateBasePath === '') {
            continue;
        }
        $resolvedBase = realpath($templateBasePath);
        $activeThemeBase = realpath(_PS_ROOT_DIR_ . '/themes/' . $context->shop->theme->getName() . '/mails');
        $parentName = (string) $context->shop->theme->get('parent');
        $parentThemeBase = $parentName !== ''
            ? realpath(_PS_ROOT_DIR_ . '/themes/' . $parentName . '/mails')
            : false;
        $shopRoot = realpath(_PS_ROOT_DIR_ . '/mails');
        $moduleRoot = realpath(_PS_MODULE_DIR_);
        if ($resolvedBase !== false && $resolvedBase === $activeThemeBase) {
            $templateEvidence['template_candidate'] = 'active_theme';
        } elseif ($resolvedBase !== false && $parentThemeBase !== false && $resolvedBase === $parentThemeBase) {
            $templateEvidence['template_candidate'] = 'parent_theme';
        } elseif ($resolvedBase !== false && $shopRoot !== false && $resolvedBase === $shopRoot) {
            $templateEvidence['template_candidate'] = 'shop_root';
        } elseif ($resolvedBase !== false && $moduleRoot !== false
            && str_starts_with($resolvedBase, $moduleRoot . DIRECTORY_SEPARATOR)) {
            $templateEvidence['template_candidate'] = 'module_fallback';
        } else {
            $templateEvidence['template_candidate'] = 'other';
        }
        $textTemplatePath = rtrim($templateBasePath, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR
            . $templateIso . '/password_query.txt';
        $htmlTemplatePath = rtrim($templateBasePath, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR
            . $templateIso . '/password_query.html';
        $textTemplate = is_file($textTemplatePath) ? file_get_contents($textTemplatePath) : false;
        $htmlTemplate = is_file($htmlTemplatePath) ? file_get_contents($htmlTemplatePath) : false;
        $templateEvidence['text_template_present'] = is_string($textTemplate);
        $templateEvidence['html_template_present'] = is_string($htmlTemplate);
        if (($requiredText && !is_string($textTemplate)) || ($requiredHtml && !is_string($htmlTemplate))) {
            continue;
        }
        $templateEvidence['template_iso'] = in_array($templateIso, ['ja', 'en', 'ko'], true)
            ? $templateIso
            : 'other';
        $templateEvidence['text_template_present'] = is_string($textTemplate);
        $templateEvidence['text_template_has_url'] = is_string($textTemplate) && str_contains($textTemplate, '{url}');
        $templateEvidence['html_template_present'] = is_string($htmlTemplate);
        $templateEvidence['html_template_has_url'] = is_string($htmlTemplate) && str_contains($htmlTemplate, '{url}');
        $foundTemplate = true;
        break;
    }
    if (!$foundTemplate) {
        $templateEvidence['template_candidate'] = 'missing';
        $templateEvidence['template_iso'] = 'none';
    }
} catch (Throwable $exception) {
    // Keep the diagnostic bounded; the live reset request and email assertions remain authoritative.
}
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
                  'template_evidence' => $templateEvidence,
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
        'raw_text_native_link_shape': None,
        'mailpit_preview_text_native_link_shape': None,
        'mailpit_preview_text_shape_match': None,
        'pre_smtp_html_native_link_shape': None,
        'pre_smtp_text_native_link_shape': None,
        'pre_smtp_reset_url_candidate_found': None,
        'pre_smtp_reset_template_context_recognized': None,
        'pre_smtp_template_url_candidate_present': None,
        'pre_smtp_template_url_credentials_complete': None,
        'pre_smtp_template_url_native_route': None,
        'pre_smtp_html_url_candidate_present': None,
        'pre_smtp_html_token_present': None,
        'pre_smtp_html_reset_token_present': None,
        'pre_smtp_html_id_customer_present': None,
        'pre_smtp_html_scheme_host_port_match': None,
        'pre_smtp_html_path_match': None,
        'pre_smtp_html_credentials_complete': None,
        'pre_smtp_html_candidate_selected': None,
        'pre_smtp_text_setter_available': None,
        'pre_smtp_text_setter_invoked': None,
        'mail_type': None, 'template_candidate': 'unavailable',
        'template_iso': 'none', 'text_source': 'unavailable',
        'text_template_present': False, 'text_template_has_url': False,
        'html_template_present': False, 'html_template_has_url': False,
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
                              raw_text_native_link_shape=None,
                              mailpit_preview_text_native_link_shape=None,
                              mailpit_preview_text_shape_match=None,
                              pre_smtp_html_native_link_shape=None,
                              pre_smtp_text_native_link_shape=None,
                              pre_smtp_reset_url_candidate_found=None,
                              pre_smtp_reset_template_context_recognized=None,
                              pre_smtp_template_url_candidate_present=None,
                              pre_smtp_template_url_credentials_complete=None,
                              pre_smtp_template_url_native_route=None,
                              pre_smtp_html_url_candidate_present=None,
                              pre_smtp_html_token_present=None,
                              pre_smtp_html_reset_token_present=None,
                              pre_smtp_html_id_customer_present=None,
                              pre_smtp_html_scheme_host_port_match=None,
                              pre_smtp_html_path_match=None,
                              pre_smtp_html_credentials_complete=None,
                              pre_smtp_html_candidate_selected=None,
                              pre_smtp_text_setter_available=None,
                              pre_smtp_text_setter_invoked=None,
                              same_origin=False, native_route=False, language_matches=False,
                              email_field_present=False, submit_control_present=False,
                              submit_center_in_viewport=False, submit_center_unobstructed=False,
                              success_alert_present=False, reset_fields_present=False)
            email = f'ordenowa-reset-locale-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}-{language}-{secrets.token_hex(4)}@example.invalid'
            fixture = seed(project, language, email)
            template_evidence = fixture.get('template_evidence')
            if (isinstance(template_evidence, dict)
                    and set(template_evidence) == {
                        'mail_type', 'template_candidate', 'text_template_present', 'text_template_has_url',
                        'template_iso', 'text_source', 'html_template_present', 'html_template_has_url',
                    }
                    and type(template_evidence.get('mail_type')) is int
                    and template_evidence['template_candidate'] in SAFE_TEMPLATE_CANDIDATES
                    and template_evidence['template_iso'] in SAFE_TEMPLATE_ISOS
                    and template_evidence['text_source'] in SAFE_TEMPLATE_TEXT_SOURCES
                    and all(type(template_evidence.get(key)) is bool for key in (
                        'text_template_present', 'text_template_has_url',
                        'html_template_present', 'html_template_has_url',
                    ))):
                diagnostic.update(template_evidence)
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
            captured_message = wait_message(api, email)
            raw_mime_parts = read_raw_mime_parts(api, captured_message, diagnostic)
            raw_text_shape = text_has_native_reset_link_shape(raw_mime_parts[1], base, reset_path)
            preview_text = captured_message.get('Text')
            preview_text_shape = (
                text_has_native_reset_link_shape(preview_text, base, reset_path)
                if isinstance(preview_text, str) else None
            )
            diagnostic['raw_text_native_link_shape'] = raw_text_shape
            diagnostic['mailpit_preview_text_native_link_shape'] = preview_text_shape
            diagnostic['mailpit_preview_text_shape_match'] = (
                raw_text_shape == preview_text_shape if preview_text_shape is not None else None
            )
            reset_url = assert_message(captured_message, language, base,
                                       reset_path, fixture['forbidden'], raw_mime_parts)
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
            print(
                f'PASS: isolated native reset email locale={language}; '
                f'raw_text_native_link={str(raw_text_shape).lower()}; '
                f'mailpit_preview_text_native_link={str(preview_text_shape).lower()}; '
                f'mailpit_preview_text_shape_match={str(diagnostic["mailpit_preview_text_shape_match"]).lower()}; '
                f'pre_smtp_html_native_link={str(diagnostic["pre_smtp_html_native_link_shape"]).lower()}; '
                f'pre_smtp_text_native_link={str(diagnostic["pre_smtp_text_native_link_shape"]).lower()}; '
                f'pre_smtp_url_candidate={str(diagnostic["pre_smtp_reset_url_candidate_found"]).lower()}; '
                f'pre_smtp_reset_template_context={str(diagnostic["pre_smtp_reset_template_context_recognized"]).lower()}; '
                f'pre_smtp_template_url={str(diagnostic["pre_smtp_template_url_candidate_present"]).lower()}; '
                f'pre_smtp_template_credentials={str(diagnostic["pre_smtp_template_url_credentials_complete"]).lower()}; '
                f'pre_smtp_template_route={str(diagnostic["pre_smtp_template_url_native_route"]).lower()}; '
                f'pre_smtp_html_candidate={str(diagnostic["pre_smtp_html_url_candidate_present"]).lower()}; '
                f'pre_smtp_html_credentials={str(diagnostic["pre_smtp_html_token_present"]).lower()}/'
                f'{str(diagnostic["pre_smtp_html_reset_token_present"]).lower()}/'
                f'{str(diagnostic["pre_smtp_html_id_customer_present"]).lower()}; '
                f'pre_smtp_html_route={str(diagnostic["pre_smtp_html_scheme_host_port_match"]).lower()}/'
                f'{str(diagnostic["pre_smtp_html_path_match"]).lower()}; '
                f'pre_smtp_html_selected={str(diagnostic["pre_smtp_html_candidate_selected"]).lower()}; '
                f'pre_smtp_text_setter_available={str(diagnostic["pre_smtp_text_setter_available"]).lower()}; '
                f'pre_smtp_text_setter_invoked={str(diagnostic["pre_smtp_text_setter_invoked"]).lower()}'
            )
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
            f'raw_text_native_link={str(diagnostic["raw_text_native_link_shape"]).lower()}; '
            f'mailpit_preview_text_native_link={str(diagnostic["mailpit_preview_text_native_link_shape"]).lower()}; '
            f'mailpit_preview_text_shape_match={str(diagnostic["mailpit_preview_text_shape_match"]).lower()}; '
            f'pre_smtp_html_native_link={str(diagnostic["pre_smtp_html_native_link_shape"]).lower()}; '
            f'pre_smtp_text_native_link={str(diagnostic["pre_smtp_text_native_link_shape"]).lower()}; '
            f'pre_smtp_url_candidate={str(diagnostic["pre_smtp_reset_url_candidate_found"]).lower()}; '
            f'pre_smtp_reset_template_context={str(diagnostic["pre_smtp_reset_template_context_recognized"]).lower()}; '
            f'pre_smtp_template_url={str(diagnostic["pre_smtp_template_url_candidate_present"]).lower()}; '
            f'pre_smtp_template_credentials={str(diagnostic["pre_smtp_template_url_credentials_complete"]).lower()}; '
            f'pre_smtp_template_route={str(diagnostic["pre_smtp_template_url_native_route"]).lower()}; '
            f'pre_smtp_html_candidate={str(diagnostic["pre_smtp_html_url_candidate_present"]).lower()}; '
            f'pre_smtp_html_credentials={str(diagnostic["pre_smtp_html_token_present"]).lower()}/'
            f'{str(diagnostic["pre_smtp_html_reset_token_present"]).lower()}/'
            f'{str(diagnostic["pre_smtp_html_id_customer_present"]).lower()}; '
            f'pre_smtp_html_route={str(diagnostic["pre_smtp_html_scheme_host_port_match"]).lower()}/'
            f'{str(diagnostic["pre_smtp_html_path_match"]).lower()}; '
            f'pre_smtp_html_selected={str(diagnostic["pre_smtp_html_candidate_selected"]).lower()}; '
            f'pre_smtp_text_setter_available={str(diagnostic["pre_smtp_text_setter_available"]).lower()}; '
            f'pre_smtp_text_setter_invoked={str(diagnostic["pre_smtp_text_setter_invoked"]).lower()}; '
            f'mail_type={diagnostic["mail_type"] if diagnostic["mail_type"] in (1, 2, 3, 4) else "unavailable"}; '
            f'template_candidate={diagnostic["template_candidate"]}; '
            f'template_iso={diagnostic["template_iso"]}; '
            f'text_source={diagnostic["text_source"]}; '
            f'text_template_present={str(diagnostic["text_template_present"]).lower()}; '
            f'text_template_has_url={str(diagnostic["text_template_has_url"]).lower()}; '
            f'html_template_present={str(diagnostic["html_template_present"]).lower()}; '
            f'html_template_has_url={str(diagnostic["html_template_has_url"]).lower()}; '
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
