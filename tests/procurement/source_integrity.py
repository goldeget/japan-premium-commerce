#!/usr/bin/env python3
"""Compare frozen application files to the image bundle and live runtime.

Only counts, booleans and the source SHA leave the private manifest directory.
Native parent distribution assets and generated child CCC files are classified
separately; unexpected PHP/source files cannot pass as generated assets.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ROOTS = (
    'modules/kuraneapostcode', 'modules/kuraneabackoffice',
    'modules/kuraneabusinessprofile', 'modules/kuraneacatalog',
    'modules/kuraneapush', 'modules/ordenowaprocurement',
    'themes/kuranea', 'themes/hummingbird',
)
VENDOR = 'modules/kuraneapush/vendor/'
PHP_MANIFEST = r'''
$base=$argv[1]??'';
if(!in_array($base,['/opt/kuranea','/var/www/html'],true))exit(77);
$paths=['modules/kuraneapostcode','modules/kuraneabackoffice','modules/kuraneabusinessprofile','modules/kuraneacatalog','modules/kuraneapush','modules/ordenowaprocurement','themes/kuranea','themes/hummingbird'];
$out=[];
foreach($paths as$path){
    $dir=$base.'/'.$path;if(!is_dir($dir))exit(2);
    $it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir,FilesystemIterator::SKIP_DOTS));
    foreach($it as$f){
        if(!$f->isFile())continue;
        $relative=substr($f->getPathname(),strlen($base)+1);
        if(preg_match('~(?:^|/)(?:\.git|node_modules)(?:/|$)~',$relative))continue;
        $h=hash_file('sha256',$f->getPathname());if(!is_string($h))exit(3);
        $out[$relative]=$h;
    }
}
ksort($out);echo json_encode($out,JSON_THROW_ON_ERROR);
'''


def check(condition: bool) -> None:
    if not condition:
        raise AssertionError('source integrity guard')


def manifest(compose: list[str], base: str) -> dict[str, str]:
    result = subprocess.run(compose + ['exec', '-T', '-u', 'www-data', 'prestashop', 'php', '-r', PHP_MANIFEST, base],
                            capture_output=True, text=True, timeout=60, check=True)
    value = json.loads(result.stdout)
    check(isinstance(value, dict) and bool(value))
    check(all(isinstance(key, str) and isinstance(item, str) and re.fullmatch(r'[a-f0-9]{64}', item)
              for key, item in value.items()))
    return value


def allowed_extra(path: str) -> str | None:
    if re.fullmatch(r'themes/kuranea/assets/cache/(?:theme|bottom)-[a-f0-9]+\.(?:css|js)', path):
        return 'generated_child_ccc'
    if path.startswith('themes/hummingbird/assets/') and Path(path).suffix.lower() in (
        '.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.html', '.map',
    ):
        return 'native_parent_prebuilt_assets'
    return None


def main(phase: str, outcome: dict) -> None:
    check(phase in ('native_source', 'restart_source'))
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    project = os.environ['CI_COMPOSE_PROJECT_NAME']
    check(os.environ.get('CI') == 'true' and os.environ.get('KURANEA_ISOLATED_CI') == '1')
    check(bool(re.fullmatch(r'[0-9]+', run)) and bool(re.fullmatch(r'[0-9]+', attempt)))
    check(project == 'ordenowa-procurement-ci-' + run + '-' + attempt)
    check(os.environ.get('SHOP_BASE_URL') == 'http://localhost:18081' and os.environ.get('PS_DOMAIN') == 'localhost:18081')
    private = Path(os.environ['PROCUREMENT_IDENTITY_FILE']).parent / 'source-manifests'
    artifact = Path(os.environ['QA_ARTIFACT_DIR']).resolve()
    runner = Path(os.environ['RUNNER_TEMP']).resolve()
    check(runner in artifact.parents and runner in private.resolve().parents)
    check(private.resolve() != artifact and artifact not in private.resolve().parents)
    private.mkdir(mode=0o700, exist_ok=True)
    compose = ['docker', 'compose', '-f', 'compose.yaml', '-f', 'tests/procurement/ci.compose.yaml', '-p', project]
    host = {}
    for prefix in ROOTS:
        check((ROOT / prefix).is_dir())
        for path in (ROOT / prefix).rglob('*'):
            relative = path.relative_to(ROOT)
            if (path.is_file() and not any(part in ('.git', 'node_modules') for part in relative.parts)
                    and not str(relative).startswith(VENDOR)):
                host[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    bundled = manifest(compose, '/opt/kuranea')
    runtime = manifest(compose, '/var/www/html')
    for label, value in (('host', host), ('bundle', bundled), ('runtime', runtime)):
        target = private / (phase + '-' + label + '.json')
        target.write_text(json.dumps(value, sort_keys=True) + '\n')
        target.chmod(0o600)
    bundled_app = {key: value for key, value in bundled.items() if not key.startswith(VENDOR)}
    extra = set(runtime) - set(bundled)
    classifications = {'generated_child_ccc': 0, 'native_parent_prebuilt_assets': 0}
    unclassified = 0
    for path in extra:
        kind = allowed_extra(path)
        if kind is None:
            unclassified += 1
        else:
            classifications[kind] += 1
    vendor = {key: value for key, value in bundled.items() if key.startswith(VENDOR)}
    matches = {
        'host_equals_bundled_application': host == bundled_app,
        'host_equals_runtime_application': all(runtime.get(key) == value for key, value in host.items()),
        'bundled_equals_runtime_push_vendor': bool(vendor) and all(runtime.get(key) == value for key, value in vendor.items()),
        'no_unclassified_runtime_files': unclassified == 0,
    }
    outcome.update({
        'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip(),
        'application_source_files': len(host), 'push_vendor_files': len(vendor),
        'matches': matches, 'classified_extra_counts': classifications,
        'unclassified_extra_count': unclassified, 'passed': all(matches.values()),
    })
    check(outcome['passed'])


if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) == 2 else 'invalid'
    result = {'passed': False, 'phase': phase if phase in ('native_source', 'restart_source') else 'invalid'}
    try:
        main(phase, result)
    except Exception as error:
        # A native subprocess exception can contain runtime details; never print it.
        result['error_type'] = type(error).__name__
    destination = Path(os.environ['QA_ARTIFACT_DIR'])
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    (destination / (result['phase'] + '-outcome.json')).write_text(json.dumps(result, sort_keys=True) + '\n')
    print(('PASS' if result['passed'] else 'FAIL') + ' procurement source integrity phase=' + result['phase'])
    raise SystemExit(0 if result['passed'] else 1)
