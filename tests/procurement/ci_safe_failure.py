#!/usr/bin/env python3
"""Persist bounded redacted image/runtime failure evidence; raw logs stay private."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, quote_plus

CATEGORIES = (
    ('build_entitlements', r'additional privileges requested|grant requested privileges|entitlement[^\n]{0,100}(?:not allowed|denied)'),
    ('registry_rate_limit', r'toomanyrequests|pull rate limit|rate limit exceeded'),
    ('registry_authentication', r'unauthorized:|authentication required|requested access .*denied'),
    ('build_host_gateway', r'host-gateway|host gateway|invalid (?:host|ip address)'),
    ('network_policy', r'(?:connect|proxy|tunnel)[^\n]{0,100}403|blocked by .*policy|denied by .*policy'),
    ('tls_certificate', r'certificate verify|unable to get local issuer|ssl certificate problem|x509:'),
    ('network_dns', r'could not resolve host|no such host|temporary failure in name'),
    ('composer_manifest', r'does not contain valid json|composer\.json[^\n]{0,100}(?:invalid|parse)'),
    ('composer_platform', r'lock file does not contain a compatible|requires (?:php|ext-)|platform requirements'),
    ('build_context', r'not found in build context|failed to calculate checksum[^\n]*not found|failed to walk[^\n]*no such file'),
    ('disk_capacity', r'no space left on device'),
    ('network_transport', r'connection timed out|i/o timeout|network is unreachable|could not connect'),
    ('image_reference', r'manifest unknown|manifest[^\n]{0,100}not found'),
    ('dockerfile_syntax', r'failed to parse dockerfile|unknown instruction'),
    ('compose_configuration', r'additional property[^\n]*not allowed|invalid compose|validating[^\n]*compose|services\.[^\n]*must be'),
)
ERROR = re.compile(r'error|failed|denied|not found|no such|invalid|unable|cannot|could not|requires |conflict|exception|exit code', re.I)
STAGE = re.compile(r'^#[0-9]+ \[[^\]\n]{1,120}\]')


def redact(text: str, environment: dict[str, str]) -> str:
    values = []
    for key, value in environment.items():
        if value and (key in ('ADMIN_MAIL', 'ADMIN_PASSWD', 'MARIADB_PASSWORD', 'MARIADB_ROOT_PASSWORD')
                      or re.search(r'PASSWORD|PASSWD|TOKEN|SECRET|CREDENTIAL|(?:^|_)KEY$|PROXY', key, re.I)):
            values.extend((value, quote(value, safe=''), quote_plus(value, safe='')))
    for value in sorted(set(values), key=len, reverse=True):
        text = text.replace(value, '[redacted]')
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'(?i)\b(?:https?|ssh|git)://[^\s<>"\']+', '[URL]', text)
    text = re.sub(r'[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', '[email]', text)
    text = re.sub(r'(?<![A-Za-z0-9])[A-Za-z0-9_+/=\-]{24,}(?![A-Za-z0-9])', '[long-token]', text)
    return ''.join(character for character in text if character in '\n\t' or ord(character) >= 32)


def evidence(raw: str, phase: str, status: int, environment: dict[str, str]) -> dict:
    if phase not in ('image_build', 'runtime_start'):
        raise ValueError('Unknown safe evidence phase')
    category = 'none' if status == 0 else next((label for label, pattern in CATEGORIES if re.search(pattern, raw, re.I)), 'unclassified')
    safe = redact(raw, environment)
    stages, errors, tail = [], [], []
    if status:
        for line in safe.splitlines():
            line = line.strip()
            if line:
                tail.append(line[:400])
            if ERROR.search(line) and line not in errors:
                errors.append(line[:400])
            elif STAGE.search(line) and line not in stages:
                stages.append(line[:240])
    return {'passed': status == 0, 'phase': phase, 'exit_code': status, 'error_category': category,
            'safe_error_lines': errors[-24:], 'safe_build_stage_lines': stages[-8:],
            'safe_tail_lines': tail[-12:],
            'raw_log_uploaded': False}


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == 'emit':
        path = Path(sys.argv[2])
        if not path.is_file():
            return
        result = json.loads(path.read_text())
        if result.get('passed') is not False:
            return
        phase = result['phase']
        if phase not in ('image_build', 'runtime_start'):
            raise ValueError('Unknown safe evidence phase')
        print('FAIL procurement setup phase=' + phase + ' category=' + result['error_category'])
        lines = result.get('safe_build_stage_lines', []) + result.get('safe_error_lines', []) + result.get('safe_tail_lines', [])
        for line in dict.fromkeys(lines):
            print('SAFE setup error: ' + str(line)[:400])
        return
    if len(sys.argv) != 5:
        raise ValueError('Safe evidence arguments required')
    phase, raw_file, artifact_file, status = sys.argv[1:]
    result = evidence(Path(raw_file).read_text(errors='replace'), phase, int(status), dict(os.environ))
    target = Path(artifact_file)
    target.write_text(json.dumps(result, sort_keys=True) + '\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('FAIL procurement setup safe_evidence=unavailable', file=sys.stderr)
        raise SystemExit(1)
