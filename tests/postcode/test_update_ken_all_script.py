"""Safe contract checks for the Japan Post KEN_ALL refresh command."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UPDATE_SCRIPT = ROOT / "modules" / "kuraneapostcode" / "bin" / "update-ken-all.sh"
OFFICIAL_URL = "https://www.post.japanpost.jp/service/search/zipcode/download/kogaki/zip/ken_all.zip"


class JapanPostRefreshScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = tempfile.TemporaryDirectory(prefix="kuranea-kenall-test-")
        self.root = Path(self.temp_root.name)
        self.bin_dir = self.root / "bin"
        self.log_dir = self.root / "logs"
        self.tmp_dir = self.root / "tmp"
        self.bin_dir.mkdir()
        self.log_dir.mkdir()
        self.tmp_dir.mkdir()

        self._write_command(
            "curl",
            """#!/bin/sh
set -eu
printf '%s\\n' "$@" > "$TEST_LOG/curl-args"
output=
url=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) output=$2; shift 2 ;;
    --write-out) shift 2 ;;
    https://*) url=$1; shift ;;
    *) shift ;;
  esac
done
printf '%s' "$url" > "$TEST_LOG/curl-url"
printf 'ZIP TEST DATA' > "$output"
printf '%s\n%s' "${HTTP_STATUS:-200}" "${EFFECTIVE_URL:-https://www.post.japanpost.jp/service/search/zipcode/download/kogaki/zip/ken_all.zip}"
exit "${CURL_EXIT_CODE:-0}"
""",
        )
        self._write_command(
            "unzip",
            """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$TEST_LOG/unzip-calls"
case "$1" in
  -tq)
    [ "${UNZIP_TEST_STATUS:-0}" -eq 0 ] || exit "$UNZIP_TEST_STATUS"
    ;;
  -Z1)
    printf '%s\\n' "${ZIP_MEMBERS:-KEN_ALL.CSV}"
    ;;
  -p)
    printf '%s' "${CSV_CONTENT-postal-csv-fixture}"
    ;;
  *) exit 64 ;;
esac
""",
        )
        self._write_command(
            "php",
            """#!/bin/sh
set -eu
printf '%s\\n' "$@" > "$TEST_LOG/php-args"
csv_file=${2#--file=}
test -s "$csv_file"
printf '%s' "${PHP_EXIT_CODE:-0}" > "$TEST_LOG/php-exit"
exit "${PHP_EXIT_CODE:-0}"
""",
        )

        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin_dir}:{os.environ['PATH']}",
                "TEST_LOG": str(self.log_dir),
                "TMPDIR": str(self.tmp_dir),
            }
        )

    def tearDown(self) -> None:
        self.temp_root.cleanup()

    def _write_command(self, name: str, body: str) -> None:
        path = self.bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def _run(self, **environment: str) -> subprocess.CompletedProcess[str]:
        self.assertTrue(UPDATE_SCRIPT.is_file(), "the module should provide a Japan Post refresh command")
        return subprocess.run(
            [str(UPDATE_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
            env={**self.env, **environment},
        )

    def test_downloads_verified_official_archive_then_calls_transactional_importer(self) -> None:
        result = self._run()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(OFFICIAL_URL, (self.log_dir / "curl-url").read_text(encoding="utf-8"))
        curl_args = (self.log_dir / "curl-args").read_text(encoding="utf-8")
        self.assertIn("--proto", curl_args)
        self.assertIn("--proto-redir", curl_args)
        self.assertIn("--write-out", curl_args)
        self.assertIn("-tq", (self.log_dir / "unzip-calls").read_text(encoding="utf-8"))
        php_args = (self.log_dir / "php-args").read_text(encoding="utf-8").splitlines()
        self.assertTrue(php_args[0].endswith("/modules/kuraneapostcode/bin/import-ken-all.php"))
        self.assertTrue(php_args[1].startswith("--file="))
        self.assertFalse(list(self.tmp_dir.iterdir()), "temporary download files should be removed after success")

    def test_http_download_failure_reports_status_and_host_without_importing(self) -> None:
        result = self._run(
            CURL_EXIT_CODE="22",
            HTTP_STATUS="403",
            EFFECTIVE_URL="https://www.post.japanpost.jp/error?request=private-token",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("HTTP status: 403", result.stderr)
        self.assertIn("effective host: www.post.japanpost.jp", result.stderr)
        self.assertIn("curl exit: 22", result.stderr)
        self.assertNotIn("private-token", result.stderr)
        self.assertFalse((self.log_dir / "php-args").exists())
        self.assertFalse(list(self.tmp_dir.iterdir()), "temporary download files should be removed after failure")

    def test_bad_archive_is_rejected_before_the_database_importer_runs(self) -> None:
        result = self._run(UNZIP_TEST_STATUS="9")

        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.log_dir / "php-args").exists())
        self.assertFalse(list(self.tmp_dir.iterdir()), "temporary download files should be removed after failure")

    def test_archive_without_the_official_csv_member_is_rejected(self) -> None:
        result = self._run(ZIP_MEMBERS="README.txt")

        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.log_dir / "php-args").exists())

    def test_redirect_to_a_non_japan_post_host_is_rejected(self) -> None:
        result = self._run(EFFECTIVE_URL="https://example.invalid/ken_all.zip")

        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.log_dir / "php-args").exists())

    def test_empty_csv_is_rejected_before_import(self) -> None:
        result = self._run(CSV_CONTENT="")

        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.log_dir / "php-args").exists())

    def test_import_failure_is_returned_and_temporary_files_are_removed(self) -> None:
        result = self._run(PHP_EXIT_CODE="7")

        self.assertEqual(7, result.returncode)
        self.assertFalse(list(self.tmp_dir.iterdir()), "temporary download files should be removed after importer failure")


if __name__ == "__main__":
    unittest.main()
