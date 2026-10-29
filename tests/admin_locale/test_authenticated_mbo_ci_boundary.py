from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOST_HELPER = ROOT / 'tests/admin_locale/ci_authenticated_mbo.sh'
BOOTSTRAP = ROOT / 'tests/admin_locale/prepare_test_browserkit.sh'
fixture_spec = importlib.util.spec_from_file_location('safe_mbo_fixture', ROOT / 'tests/admin_locale/test_safe_authenticated_outcome.py')
fixture_module = importlib.util.module_from_spec(fixture_spec)
assert fixture_spec and fixture_spec.loader
fixture_spec.loader.exec_module(fixture_module)
facebook_spec = importlib.util.spec_from_file_location('safe_facebook_fixture', ROOT / 'tests/admin_locale/test_safe_native_facebook_outcome.py')
facebook_fixture = importlib.util.module_from_spec(facebook_spec)
assert facebook_spec and facebook_spec.loader
facebook_spec.loader.exec_module(facebook_fixture)


def shell_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name == 'nt' and len(value) > 2 and value[1:3] == ':/':
        return '/' + value[0].lower() + value[2:]
    return value


def bash_executable() -> str | None:
    candidate = Path('C:/Program Files/Git/bin/bash.exe')
    if os.name == 'nt' and candidate.is_file():
        return str(candidate)
    return shutil.which('bash')


@unittest.skipUnless(bash_executable(), 'Bash required')
class AuthenticatedMboCiBoundaryTests(unittest.TestCase):
    def run_host_boundary(self, raw: str, *, helper_status: int = 0, preparation_status: int = 0, cleanup_status: int = 0, probe: str = 'mbo'):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'private').mkdir()
        (root / 'safe').mkdir()
        capture = root / 'capture.txt'
        capture.write_text(raw, encoding='utf-8')
        env = os.environ.copy()
        env.update({
            'HOST_HELPER': shell_path(HOST_HELPER), 'REAL_PY': shell_path(Path(sys.executable)),
            'TEST_PRIVATE': shell_path(root / 'private'), 'TEST_SAFE': shell_path(root / 'safe'),
            'TEST_CAPTURE': shell_path(capture), 'MOCK_COMPOSE_LOG': shell_path(root / 'compose.log'),
            'TEST_HELPER_STATUS': str(helper_status), 'TEST_PREPARATION_STATUS': str(preparation_status),
            'TEST_CLEANUP_STATUS': str(cleanup_status),
            'TEST_PROBE': probe,
        })
        script = '''
umask 077
source "$HOST_HELPER"
private_dir="$TEST_PRIVATE"
QA_ARTIFACT_DIR="$TEST_SAFE"
CI_COMPOSE_PROJECT_NAME=ordenowa-procurement-ci-431-2
bash() { return "$TEST_PREPARATION_STATUS"; }
python3() { "$REAL_PY" "$@"; }
compose() {
  printf '%s\\n' "$*" >> "$MOCK_COMPOSE_LOG"
  if [[ "$*" == *native_mbo_error_authenticated.php* || "$*" == *native_facebook_transport_fallback.php* ]]; then
    cat "$TEST_CAPTURE"
    return "$TEST_HELPER_STATUS"
  fi
  return "$TEST_CLEANUP_STATUS"
}
"authenticated_${TEST_PROBE}_acceptance"
'''
        result = subprocess.run([bash_executable(), '-c', script], cwd=ROOT, env=env, capture_output=True, text=True)
        artifact = 'native-mbo-authenticated-outcome.json' if probe == 'mbo' else 'native-facebook-transport-outcome.json'
        safe = json.loads((root / 'safe' / artifact).read_text(encoding='utf-8'))
        log = (root / 'compose.log').read_text(encoding='utf-8')
        return result, safe, log

    def test_success_collects_private_output_and_always_cleans_owned_dependencies(self):
        payload = fixture_module.valid_helper_payload()
        payload['password'] = 'PRIVATE_NATIVE_CAPTURE'
        result, safe, log = self.run_host_boundary(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(safe['passed'])
        self.assertEqual(safe['test_dependencies_cleanup'], 'success')
        self.assertNotIn('PRIVATE_NATIVE_CAPTURE', json.dumps(safe) + result.stdout + result.stderr)
        self.assertIn('native_mbo_error_authenticated.php', log)
        self.assertIn('.ordenowa-ci-project', log)

    def test_premature_success_with_raw_output_is_not_a_pass_or_public_capture(self):
        result, safe, log = self.run_host_boundary('<html>PRIVATE_PASSWORD_AND_TOKEN</html>')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(safe['passed'])
        self.assertEqual(safe['failure_code'], 'invalid_helper_json')
        self.assertNotIn('PRIVATE_PASSWORD', json.dumps(safe) + result.stdout + result.stderr)
        self.assertIn('.ordenowa-ci-project', log)

    def test_preparation_failure_skips_authentication_and_still_attempts_safe_cleanup(self):
        result, safe, log = self.run_host_boundary('', preparation_status=42)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(safe['passed'])
        self.assertEqual(safe['failed_stage'], 'test_only_dependency_bootstrap')
        self.assertNotIn('native_mbo_error_authenticated.php', log)
        self.assertIn('.ordenowa-ci-project', log)

    def test_dependency_cleanup_failure_prevents_a_successful_auth_probe_passing(self):
        result, safe, _ = self.run_host_boundary(json.dumps(fixture_module.valid_helper_payload()), cleanup_status=31)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(safe['passed'])
        self.assertEqual(safe['test_dependencies_cleanup'], 'failed')

    def test_facebook_private_collection_and_dependency_cleanup_are_mandatory(self):
        payload = facebook_fixture.valid_payload()
        payload['raw_error'] = 'FACEBOOK_PRIVATE_SECRET'
        result, safe, log = self.run_host_boundary(json.dumps(payload), probe='facebook')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(safe['passed'])
        self.assertEqual(safe['test_dependencies_cleanup'], 'success')
        self.assertIn('native_facebook_transport_fallback.php', log)
        self.assertNotIn('FACEBOOK_PRIVATE_SECRET', json.dumps(safe) + result.stdout + result.stderr)
        result, safe, log = self.run_host_boundary('<html>FACEBOOK_PRIVATE_SECRET</html>', probe='facebook')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(safe['passed'])
        self.assertNotIn('FACEBOOK_PRIVATE_SECRET', json.dumps(safe) + result.stdout + result.stderr)
        self.assertIn('.ordenowa-ci-project', log)
        result, safe, _ = self.run_host_boundary(json.dumps(payload), probe='facebook', cleanup_status=31)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(safe['passed'])
        self.assertEqual(safe['test_dependencies_cleanup'], 'failed')

    def test_both_admin_probes_run_inside_the_required_native_boundary(self):
        source = (ROOT / 'tests/procurement/ci_acceptance.sh').read_text(encoding='utf-8')
        boundary = source.split('native_boundaries() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('authenticated_mbo_acceptance || return "$?"', boundary)
        self.assertIn('authenticated_facebook_acceptance || return "$?"', boundary)

    def test_git_fetch_failure_stops_before_any_container_dependency_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'docker.log'
            env = os.environ.copy()
            env.update({
                'BOOTSTRAP_UNDER_TEST': shell_path(BOOTSTRAP), 'REAL_PY': shell_path(Path(sys.executable)),
                'MOCK_DOCKER_LOG': shell_path(log), 'RUNNER_TEMP': shell_path(root),
                'CI': 'true', 'GITHUB_ACTIONS': 'true', 'KURANEA_ISOLATED_CI': '1',
                'GITHUB_RUN_ID': '431', 'GITHUB_RUN_ATTEMPT': '2',
                'CI_COMPOSE_PROJECT_NAME': 'ordenowa-procurement-ci-431-2',
                'KURANEA_CI_PROJECT_NAME': 'ordenowa-procurement-ci-431-2',
                'PS_DOMAIN': 'localhost:18081',
            })
            script = '''
git() {
  for argument in "$@"; do if [[ "$argument" == fetch ]]; then return 42; fi; done
  if [[ "$*" == *rev-parse* ]]; then printf '%s\\n' 4f631476bb549d882a173c47bf693f3ef84c722d; fi
  if [[ "$*" == *archive* ]]; then printf 'synthetic archive'; fi
  return 0
}
docker() { printf 'called\\n' >> "$MOCK_DOCKER_LOG"; return 0; }
python3() { "$REAL_PY" "$@"; }
source "$BOOTSTRAP_UNDER_TEST"
'''
            result = subprocess.run([bash_executable(), '-c', script], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(log.exists(), 'A failed source pin must stop before Docker copy/exec')
            self.assertEqual(list(root.glob('admin-kernel-test-deps.*')), [])


if __name__ == '__main__':
    unittest.main()
