#!/usr/bin/env python3
"""Inspect MIME in memory; persist/print only fixed PASS or failure stages."""
import email.policy
from email.parser import BytesParser
from email.utils import getaddresses
import json
import html
import os
from pathlib import Path
import re
import sys
from urllib.request import urlopen
from urllib.parse import urlparse, parse_qs

STAGE = 'guard'
try:
    run = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    assert re.fullmatch(r'[0-9]+-[0-9]+', run)
    assert os.environ['CI_COMPOSE_PROJECT_NAME'] == 'ordenowa-procurement-ci-' + run
    assert os.environ.get('CI') == 'true' and os.environ.get('KURANEA_ISOLATED_CI') == '1'
    fixture = json.loads(Path(os.environ['PROCUREMENT_IDENTITY_FILE']).read_text())
    assert fixture['run'] == run
    base = 'http://127.0.0.1:18025'
    STAGE = 'actual_message_count'
    with urlopen(base + '/api/v1/messages', timeout=10) as response:
        messages = json.load(response)['messages']
    assert len(messages) == 5
    subjects = set()
    bodies = []
    for message in messages:
        STAGE = 'raw_mime_identity'
        mid = message['ID']
        assert re.fullmatch(r'[A-Za-z0-9_-]+', mid)
        with urlopen(base + '/api/v1/message/' + mid + '/raw', timeout=10) as response:
            mime = BytesParser(policy=email.policy.default).parsebytes(response.read())
        recipients = [address for _, address in getaddresses(mime.get_all('To', []))]
        assert recipients == [fixture['customers']['a']['email']]
        assert not mime.get('Bcc')
        subject = str(mime['Subject'])
        assert subject.startswith(fixture['mail_subject_prefix'])
        subjects.add(subject[len(fixture['mail_subject_prefix']):])
        STAGE = 'private_safe_template'
        text = '\n'.join(part.get_content() for part in mime.walk() if part.get_content_type() in ('text/plain', 'text/html'))
        # Native Link chooses locale-aware friendly paths; raw query-string
        # substrings reject valid native links and do not prove destination.
        urls = re.findall(r'''https?://[^\s<>"']+''', html.unescape(text))
        expected_paths = {urlparse(route['workspace']).path for route in fixture['routes'].values()}
        assert urls
        for url in urls:
            parsed = urlparse(url)
            assert parsed.scheme in ('http', 'https') and parsed.netloc == 'localhost:18081'
            assert parsed.path in expected_paths and not parsed.fragment
            query = parse_qs(parsed.query)
            assert set(query) == {'view'} and query['view'] in (['assignments'], ['requests'], ['points'])
        assert not re.search(r'(?:100|80|-20)\s*P\b', text)
        assert not re.search(r'[?&](?:token|id_customer|id_request|id_assignment)=', text)
        assert fixture['customers']['b']['email'] not in text
        bodies.append(text)
    STAGE = 'three_locale_templates'
    assert subjects == {'ORDENOWA お知らせ', 'ORDENOWA notification', 'ORDENOWA 알림'}
    assert any('Your procurement request was received.' in body or 'A new procurement assignment is available.' in body for body in bodies)
    assert any('새로운 상품 발주 안내가 있습니다.' in body or '상품 발주 요청이 접수되었습니다.' in body for body in bodies)
    assert any('手当ポイント' in body for body in bodies)
    print('PASS actual native JA EN KO MIME, recipient isolation and no replay duplicates')
except Exception as error:
    print('FAIL procurement MIME stage=' + STAGE + ' type=' + type(error).__name__, file=sys.stderr)
    sys.exit(1)
