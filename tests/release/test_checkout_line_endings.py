from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('git'), 'real Git required')
class DockerCheckoutLineEndingsTests(unittest.TestCase):
    def checkout(self, files: dict[str, bytes]) -> dict[str, bytes]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True, capture_output=True)
            for key, value in [('core.autocrlf', 'true'), ('core.safecrlf', 'false')]:
                subprocess.run(['git', '-C', str(source), 'config', key, value], check=True, capture_output=True)
            attributes = ROOT / '.gitattributes'
            if attributes.is_file():
                (source / '.gitattributes').write_bytes(attributes.read_bytes().replace(b'\r\n', b'\n'))
            for name, content in files.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True, capture_output=True)
            destination = root / 'checkout'
            subprocess.run(
                ['git', '-C', str(source), 'checkout-index', '--all', '--prefix=' + destination.as_posix() + '/'],
                check=True, capture_output=True,
            )
            return {name: (destination / name).read_bytes() for name in files}

    def test_actual_docker_entry_scripts_survive_a_crlf_configured_checkout(self) -> None:
        files = {path.relative_to(ROOT).as_posix(): path.read_bytes().replace(b'\r\n', b'\n')
                 for path in (ROOT / 'docker').rglob('*.sh')}
        self.assertTrue(files)
        actual = self.checkout(files)
        for name, content in files.items():
            with self.subTest(script=name):
                self.assertTrue(content.startswith(b'#!'))
                self.assertNotIn(b'\r\n', actual[name], 'CRLF breaks the Linux interpreter/entrypoint')
                self.assertEqual(actual[name], content)

    def test_rule_covers_future_docker_and_test_shell_scripts(self) -> None:
        contents = b'#!/usr/bin/env bash\nset -euo pipefail\nprintf "ready\\n"\n'
        files = {'docker/future-entry.sh': contents, 'tests/procurement/future-ci.sh': contents}
        self.assertEqual(self.checkout(files), files)

    def test_binary_assets_are_not_normalized(self) -> None:
        files = {'assets/source.png': b'\x89PNG\r\n\x1a\n\x00\x00binary\r\n'}
        self.assertEqual(self.checkout(files), files)


if __name__ == '__main__':
    unittest.main()
