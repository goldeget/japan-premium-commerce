from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PREP_ROOT = Path(__file__).resolve().parents[2]
if (PREP_ROOT / "ci_restore.sh").is_file():
    RESTORE_SCRIPT = PREP_ROOT / "ci_restore.sh"
    WORKFLOW = PREP_ROOT / "procurement-platform.yml"
else:
    RESTORE_SCRIPT = PREP_ROOT / "tests" / "procurement" / "ci_restore.sh"
    WORKFLOW = PREP_ROOT / ".github" / "workflows" / "procurement-platform.yml"
SQL_FIXTURE = b"CREATE TABLE ci_restore_probe (id INT PRIMARY KEY);\nINSERT INTO ci_restore_probe VALUES (431);\n"


def write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8", newline="\n")
    path.chmod(0o755)


class EncryptedRestoreContractTests(unittest.TestCase):
    def test_workflow_installs_age_and_runs_this_contract_test(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("apt-get install --yes --no-install-recommends fonts-noto-cjk fontconfig age", workflow)
        self.assertIn("python3 -m unittest discover -s tests/procurement -p 'test_ci*.py'", workflow)
        restore = RESTORE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/tmp/ordenowa-procurement-ci/ci_readback.php", restore)
        self.assertIn("/tmp/ordenowa-procurement-ci/ci_restore_readback.php", restore)
        self.assertNotIn("/tmp/ordenowaprocurement-ci/", restore)
        import_offset = restore.index('docker exec -i "$restore_project"')
        self.assertLess(restore.index('cmp -s -- "$private_dir/backup.sql" "$private_dir/decrypted.sql"'), import_offset)
        self.assertLess(restore.index("tampered_ciphertext_rejected=true"), import_offset)
        self.assertLess(restore.index("wrong_identity_rejected=true"), import_offset)
        self.assertIn('"$private_dir/backup.sql.age"', restore)
        self.assertIn('"$private_dir/restore.agekey"', restore)
        self.assertIn('"$QA_ARTIFACT_DIR/encrypted-restore-outcome.json"', restore)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "mocked shell protocol test requires Linux Bash")
    def test_round_trip_imports_only_verified_bytes_and_keeps_only_safe_outcome(self) -> None:
        result, root, expected_sql = self._run_restore(corrupt_ciphertext=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertTrue((root / "imported.marker").is_file())
        self.assertEqual((root / "imported.marker").read_bytes(), expected_sql)
        self._assert_safe_outcome(root, passed=True, roundtrip=True, tampered=True, wrong_key=True, restored=True)
        self.assertEqual(list((root / "procurement-safe-artifacts").iterdir()), [root / "procurement-safe-artifacts" / "encrypted-restore-outcome.json"])
        self.assertEqual(list(root.glob("procurement-restore.*")), [])
        self.assertNotIn(expected_sql, result.stdout)
        self.assertNotIn(expected_sql, result.stderr)
        self.assertNotIn(b"AGE-MOCK-PRIVATE", result.stdout + result.stderr)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "mocked shell protocol test requires Linux Bash")
    def test_corrupt_ciphertext_aborts_before_database_import_and_cleans_private_files(self) -> None:
        result, root, expected_sql = self._run_restore(corrupt_ciphertext=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / "imported.marker").exists())
        self._assert_safe_outcome(root, passed=False, roundtrip=False, tampered=False, wrong_key=False, restored=False)
        self.assertEqual(list(root.glob("procurement-restore.*")), [])
        self.assertNotIn(expected_sql, result.stdout)
        self.assertNotIn(expected_sql, result.stderr)

    def _run_restore(self, *, corrupt_ciphertext: bool) -> tuple[subprocess.CompletedProcess[bytes], Path, bytes]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        marker = root / "imported.marker"
        age_keygen = r'''#!/usr/bin/env python3
import sys
from pathlib import Path
args = sys.argv[1:]
if args and args[0] == "-o":
    path = Path(args[1])
    path.write_text("wrong" if "wrong." in path.name else "good", encoding="ascii")
elif args and args[0] == "-y":
    print("age1wrongrecipient" if Path(args[1]).read_text(encoding="ascii") == "wrong" else "age1mockrecipient")
else:
    raise SystemExit(1)
'''
        age = r'''#!/usr/bin/env python3
import hashlib
import os
import sys
from pathlib import Path
args = sys.argv[1:]
if args == ["--version"]:
    print("v1.2.1")
    raise SystemExit(0)
if "--encrypt" in args:
    recipient = args[args.index("--recipient") + 1].encode("ascii")
    output = Path(args[args.index("--output") + 1])
    source = Path(args[-1])
    payload = source.read_bytes()
    encoded = b"AGE-MOCK-1\n" + recipient + b"\n" + hashlib.sha256(payload).hexdigest().encode("ascii") + b"\n" + payload
    if os.environ.get("FAKE_AGE_CORRUPT_ENCRYPT") == "1":
        encoded = encoded[:-1] + bytes([encoded[-1] ^ 1])
    output.write_bytes(encoded)
    raise SystemExit(0)
if "--decrypt" in args:
    identity = Path(args[args.index("--identity") + 1]).read_text(encoding="ascii")
    output = Path(args[args.index("--output") + 1])
    data = Path(args[-1]).read_bytes()
    try:
        magic, recipient, digest, payload = data.split(b"\n", 3)
    except ValueError:
        raise SystemExit(1)
    expected_recipient = b"age1wrongrecipient" if identity == "wrong" else b"age1mockrecipient"
    if magic != b"AGE-MOCK-1" or recipient != expected_recipient or hashlib.sha256(payload).hexdigest().encode("ascii") != digest:
        raise SystemExit(1)
    output.write_bytes(payload)
    raise SystemExit(0)
raise SystemExit(1)
'''
        docker = r'''#!/usr/bin/env python3
import os
import sys
from pathlib import Path
args = sys.argv[1:]
expected = bytes.fromhex(os.environ["FAKE_SQL_HEX"])
marker = Path(os.environ["FAKE_IMPORT_MARKER"])
if args and args[0] == "compose":
    if "ps" in args:
        print("source-mariadb-container")
        raise SystemExit(0)
    if "mariadb-dump" in args:
        sys.stdout.buffer.write(expected)
        raise SystemExit(0)
    if "ci_restore_readback.php" in args:
        if not marker.is_file() or marker.read_bytes() != expected:
            raise SystemExit(9)
        raise SystemExit(0)
    if "ci_readback.php" in args:
        raise SystemExit(0)
if args and args[0] == "inspect":
    print("mariadb:10.11@sha256:" + "a" * 64)
    raise SystemExit(0)
if args and args[0] == "run":
    print("run-owned-restore-container")
    raise SystemExit(0)
if args and args[0] == "exec":
    if len(args) > 1 and args[1] == "-i":
        imported = sys.stdin.buffer.read()
        if imported != expected:
            raise SystemExit(8)
        marker.write_bytes(imported)
        raise SystemExit(0)
    raise SystemExit(0)
if args[:2] == ["container", "inspect"]:
    raise SystemExit(1)
if args[:2] == ["rm", "-f"]:
    raise SystemExit(0)
raise SystemExit(2)
'''
        write_executable(bin_dir / "age-keygen", age_keygen)
        write_executable(bin_dir / "age", age)
        write_executable(bin_dir / "docker", docker)
        expected_sql = SQL_FIXTURE
        env = os.environ.copy()
        env.update({
            "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
            "CI": "true",
            "KURANEA_ISOLATED_CI": "1",
            "CI_COMPOSE_PROJECT_NAME": "ordenowa-procurement-ci-431-2",
            "GITHUB_RUN_ID": "431",
            "GITHUB_RUN_ATTEMPT": "2",
            "RUNNER_TEMP": str(root),
            "QA_ARTIFACT_DIR": str(root / "procurement-safe-artifacts"),
            "MARIADB_ROOT_PASSWORD": "TEST_ONLY_DO_NOT_LOG",
            "FAKE_SQL_HEX": expected_sql.hex(),
            "FAKE_IMPORT_MARKER": str(marker),
        })
        if corrupt_ciphertext:
            env["FAKE_AGE_CORRUPT_ENCRYPT"] = "1"
        else:
            env.pop("FAKE_AGE_CORRUPT_ENCRYPT", None)
        result = subprocess.run(
            [shutil.which("bash") or "bash", str(RESTORE_SCRIPT)],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result, root, expected_sql

    def _assert_safe_outcome(
        self,
        root: Path,
        *,
        passed: bool,
        roundtrip: bool,
        tampered: bool,
        wrong_key: bool,
        restored: bool,
    ) -> None:
        outcome_path = root / "procurement-safe-artifacts" / "encrypted-restore-outcome.json"
        self.assertTrue(outcome_path.is_file())
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        self.assertEqual(set(outcome), {
            "age_version", "ciphertext_tamper_rejected", "database_restore_verified",
            "decrypt_roundtrip_verified", "passed", "wrong_identity_rejected",
        })
        self.assertEqual(outcome["age_version"], "v1.2.1")
        self.assertEqual(outcome["passed"], passed)
        self.assertEqual(outcome["decrypt_roundtrip_verified"], roundtrip)
        self.assertEqual(outcome["ciphertext_tamper_rejected"], tampered)
        self.assertEqual(outcome["wrong_identity_rejected"], wrong_key)
        self.assertEqual(outcome["database_restore_verified"], restored)


if __name__ == "__main__":
    unittest.main()
