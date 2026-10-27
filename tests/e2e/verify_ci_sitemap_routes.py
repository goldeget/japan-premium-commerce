#!/usr/bin/env python3
"""Exercise public sitemap and robots routes on the disposable local CI shop."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ElementTree


MAX_XML_BYTES = 50 * 1024 * 1024
SITEMAP_NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def fetch(base_url: str, path: str, expected_media_type: str) -> tuple[int, str, bytes]:
    request_url = base_url + path
    request = Request(request_url, headers={'Accept': 'application/xml, text/plain'})
    with urlopen(request, timeout=10) as response:
        final = urlsplit(response.geturl())
        expected = urlsplit(base_url)
        require(
            (final.scheme, final.hostname, final.port)
            == (expected.scheme, expected.hostname, expected.port),
            'route redirected outside the configured loopback shop',
        )
        media_type = response.headers.get_content_type().lower()
        require(media_type == expected_media_type, 'route returned an unexpected content type')
        body = response.read(MAX_XML_BYTES + 1)
        require(len(body) <= MAX_XML_BYTES, 'route exceeded the sitemap response size limit')
        return response.status, media_type, body


def parse_xml(body: bytes, expected_root: str) -> ElementTree.Element:
    upper = body.upper()
    require(b'<!DOCTYPE' not in upper and b'<!ENTITY' not in upper, 'XML contains a forbidden declaration')
    root = ElementTree.fromstring(body)
    require(root.tag == SITEMAP_NS + expected_root, 'route returned an unexpected XML root')
    return root


def main() -> int:
    stage = 'local loopback guard'
    try:
        if os.environ.get('CI') != 'true' or os.environ.get('GITHUB_ACTIONS') != 'true':
            raise AssertionError('route acceptance requires isolated GitHub Actions')
        base_url = os.environ.get('SHOP_BASE_URL', '').strip()
        parts = urlsplit(base_url)
        require(
            parts.scheme == 'http'
            and parts.hostname == 'localhost'
            and parts.port == 18080
            and parts.path in ('', '/')
            and not parts.query
            and not parts.fragment,
            'route target is not the isolated local shop',
        )
        base_url = 'http://localhost:18080/'

        stage = 'safe runtime fixture readback'
        fixture_path = Path(os.environ.get('SITEMAP_RUNTIME_FIXTURE', ''))
        fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
        require(fixture.get('fixture_scope') == 'isolated disposable GitHub Actions shop',
                'runtime fixture is outside the isolated shop')
        require(fixture.get('shop_base_url_sha256') == sha256(base_url),
                'configured ShopUrl does not match the isolated local origin')
        require(fixture.get('sitemap_url_sha256') == sha256(base_url + 'sitemap.xml'),
                'configured sitemap URL does not match the isolated ShopUrl')
        require(fixture.get('enabled_locales') == ['en', 'ja', 'ko'],
                'the expected populated storefront locale set is unavailable')
        require(fixture.get('enabled_profile_locales') == ['ja', 'en', 'ko'],
                'the published profile does not enable all populated storefront locales')
        require(fixture.get('rewriting_enabled') is True, 'rewritten routes are disabled')
        require(fixture.get('active_guest_visible_product') is True,
                'the active guest-visible synthetic product was not re-read')
        require(fixture.get('commerce_gate_enabled') is False,
                'the CI acceptance fixture must keep seller authorization pending')
        baseline_hashes = fixture.get('robots_core_directive_sha256')
        require(isinstance(baseline_hashes, list) and baseline_hashes,
                'core robots directives were not captured')

        stage = 'robots HTTP readback'
        robots_status, _, robots_body = fetch(base_url, 'robots.txt', 'text/plain')
        robots_text = robots_body.decode('utf-8', errors='strict')
        directives = [
            line.strip()
            for line in robots_text.splitlines()
            if re.match(r'^\s*(?:Allow|Disallow)\s*:', line, flags=re.IGNORECASE)
        ]
        directive_hashes = {sha256(line) for line in directives}
        require(set(baseline_hashes).issubset(directive_hashes),
                'PrestaShop Allow/Disallow directives were not preserved')
        sitemap_directives = list(re.finditer(
            r'^\s*Sitemap\s*:\s*(\S+)\s*$',
            robots_text,
            flags=re.IGNORECASE | re.MULTILINE,
        ))
        sitemap_hashes = {sha256(match.group(0).strip()) for match in sitemap_directives}
        core_sitemap_hashes = set(fixture.get('robots_core_sitemap_sha256', []))
        require(core_sitemap_hashes.issubset(sitemap_hashes),
                'PrestaShop sitemap directives were not preserved')
        configured_sitemaps = [
            match for match in sitemap_directives
            if sha256(match.group(1)) == fixture['sitemap_url_sha256']
        ]
        require(len(configured_sitemaps) == 1,
                'robots.txt does not reference the configured sitemap URL exactly once')

        stage = 'pending-gate sitemap HTTP readback'
        index_status, _, index_body = fetch(base_url, 'sitemap.xml', 'application/xml')
        index_root = parse_xml(index_body, 'sitemapindex')
        index_locations = index_root.findall(SITEMAP_NS + 'sitemap/' + SITEMAP_NS + 'loc')
        require(index_status == 200 and len(index_root) == 0 and not index_locations,
                'pending seller authorization exposed sitemap index entries')

        locale_page_statuses = {}
        for locale in ('ja', 'en', 'ko'):
            stage = 'pending-gate locale page readback'
            page_status, _, page_body = fetch(
                base_url, f'sitemap-{locale}-1.xml', 'application/xml'
            )
            page_root = parse_xml(page_body, 'urlset')
            page_locations = page_root.findall(SITEMAP_NS + 'url/' + SITEMAP_NS + 'loc')
            require(page_status == 200 and len(page_root) == 0 and not page_locations,
                    'pending seller authorization exposed locale sitemap URLs')
            locale_page_statuses[locale] = page_status

        print(json.dumps({
            'result': 'success',
            'robots_status': robots_status,
            'robots_core_directives_preserved': True,
            'configured_sitemap_directive_count': len(configured_sitemaps),
            'sitemap_index_status': index_status,
            'sitemap_index_entries_while_gate_pending': len(index_locations),
            'locale_page_statuses': locale_page_statuses,
            'locale_page_url_count_while_gate_pending': 0,
            'active_guest_visible_product_fixture': True,
            'commerce_gate_pending': True,
        }, sort_keys=True, separators=(',', ':')))
        return 0
    except (AssertionError, HTTPError, URLError, OSError, UnicodeError, json.JSONDecodeError, ElementTree.ParseError) as error:
        print(
            f'ORDENOWA_SITEMAP_HTTP stage={stage}; exception_class={type(error).__name__}',
            file=sys.stderr,
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
