from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOST_HELPER = ROOT / 'tests/admin_locale/ci_authenticated_mbo.sh'
ACCEPTANCE = ROOT / 'tests/procurement/ci_acceptance.sh'


def bash_executable() -> str | None:
    candidate = Path('C:/Program Files/Git/bin/bash.exe')
    if os.name == 'nt' and candidate.is_file():
        return str(candidate)
    return shutil.which('bash')


def shell_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name == 'nt' and len(value) > 2 and value[1:3] == ':/':
        return '/' + value[0].lower() + value[2:]
    return value


@unittest.skipUnless(bash_executable(), 'Bash required')
class AuthenticatedAdminPairTests(unittest.TestCase):
    def run_pair(self, mbo_status: int, facebook_status: int) -> tuple[int, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = root / 'calls.txt'
            env = os.environ.copy()
            env.update({
                'HOST_HELPER': shell_path(HOST_HELPER),
                'PAIR_CALLS': shell_path(calls),
                'MBO_STATUS': str(mbo_status),
                'FACEBOOK_STATUS': str(facebook_status),
            })
            script = r'''
set -euo pipefail
source "$HOST_HELPER"
authenticated_mbo_acceptance() {
  printf '%s\n' mbo >> "$PAIR_CALLS"
  return "$MBO_STATUS"
}
authenticated_facebook_acceptance() {
  printf '%s\n' facebook >> "$PAIR_CALLS"
  return "$FACEBOOK_STATUS"
}
if authenticated_admin_pair_acceptance; then
  printf '0\n'
else
  printf '%s\n' "$?"
fi
'''
            result = subprocess.run(
                [bash_executable() or 'bash', '-c', script],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(calls.is_file(), 'both probes must write their call record')
            return int(result.stdout.strip()), calls.read_text(encoding='utf-8').splitlines()

    def test_first_probe_failure_does_not_suppress_second_probe(self):
        status, calls = self.run_pair(17, 0)
        self.assertEqual(1, status)
        self.assertEqual(['mbo', 'facebook'], calls)

    def test_second_probe_failure_fails_aggregate_after_both_run(self):
        status, calls = self.run_pair(0, 23)
        self.assertEqual(1, status)
        self.assertEqual(['mbo', 'facebook'], calls)

    def test_both_probes_must_pass(self):
        status, calls = self.run_pair(0, 0)
        self.assertEqual(0, status)
        self.assertEqual(['mbo', 'facebook'], calls)

    def test_native_boundary_uses_the_pair_aggregator(self):
        source = ACCEPTANCE.read_text(encoding='utf-8')
        boundary = source.split('native_boundaries() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('authenticated_admin_pair_acceptance || return "$?"', boundary)
        self.assertNotIn('authenticated_mbo_acceptance || return', boundary)
        self.assertNotIn('authenticated_facebook_acceptance || return', boundary)


if __name__ == '__main__':
    unittest.main()
