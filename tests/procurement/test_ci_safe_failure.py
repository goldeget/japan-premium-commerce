#!/usr/bin/env python3
"""Offline regression for the setup failure evidence boundary."""
import json
from pathlib import Path
import unittest

from ci_safe_failure import evidence


class SafeFailureTests(unittest.TestCase):
    def test_secrets_urls_emails_and_tokens_are_redacted(self):
        env = {'ADMIN_MAIL': 'diagnostic-user@example.invalid', 'ADMIN_PASSWD': 'Synthetic!Password/Value',
               'MARIADB_PASSWORD': 'SyntheticDatabasePassword1234', 'MARIADB_ROOT_PASSWORD': 'SyntheticRootPassword1234',
               'HTTPS_PROXY': 'https://operator:ProxyPassword@proxy.example.invalid:8443',
               'ACTIONS_RUNTIME_TOKEN': 'SecretRuntimeTokenABCDEFGHIJKLMNOP'}
        raw = '#14 [push_dependencies 4/4] RUN composer install\nERROR failed ' + ' '.join(env.values())
        raw += ' https://other:UnboundPassword@registry.example.invalid/path?token=abcdefghijklmnop1234567890 someone@example.invalid'
        raw += ' Synthetic%21Password%2FValue'
        result = evidence(raw, 'image_build', 1, env)
        serialized = json.dumps(result)
        for value in env.values():
            self.assertNotIn(value, serialized)
        for value in ('UnboundPassword', 'registry.example.invalid', 'someone@example.invalid', 'abcdefghijklmnop1234567890', 'Synthetic%21Password%2FValue'):
            self.assertNotIn(value, serialized)
        self.assertFalse(result['passed'])
        self.assertFalse(result['raw_log_uploaded'])
        self.assertTrue(result['safe_error_lines'])

    def test_categories_are_evidence_not_guesses(self):
        for raw, expected in (
            ('ERROR toomanyrequests: pull rate limit', 'registry_rate_limit'),
            ('additional privileges requested: pass "--allow=network.host --allow=fs.example.crt" to grant requested privileges', 'build_entitlements'),
            ('failed: invalid IP address in add-host: host-gateway', 'build_host_gateway'),
            ('failed CONNECT tunnel: response 403', 'network_policy'),
            ('failed: SSL certificate problem: unable to get local issuer', 'tls_certificate'),
            ('failed: Could not resolve host', 'network_dns'),
            ('Your lock file does not contain a compatible set of packages', 'composer_platform'),
            ('failed to calculate checksum: not found', 'build_context'),
            ('failed: no space left on device', 'disk_capacity'),
            ('unrecognized failure with no known cause', 'unclassified'),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(evidence(raw, 'image_build', 1, {})['error_category'], expected)

    def test_non_keyword_fatal_tail_is_retained_after_redaction(self):
        raw = '#1 [internal] load local bake definitions\nreading from stdin 3.41kB\nterminal stream interruption password-value'
        result = evidence(raw, 'image_build', 1, {'ADMIN_PASSWD':'password-value'})
        self.assertEqual(result['error_category'], 'unclassified')
        self.assertTrue(any('terminal stream interruption' in line for line in result['safe_tail_lines']))
        self.assertNotIn('password-value', json.dumps(result))

    def test_hosted_compose_uses_standard_build_network_and_image_trust(self):
        root = Path(__file__).resolve().parents[2]
        override = (root / 'tests/procurement/ci.compose.yaml').read_text()
        # Build routing belongs to an explicit private managed-cloud override.
        self.assertNotRegex(override, r'(?m)^\s*(?:build|secrets|network|extra_hosts|args):')
        for setting in ('composer_ca', 'HTTP_PROXY', 'HTTPS_PROXY', 'HOST_CA_BUNDLE', 'host-gateway'):
            self.assertNotIn(setting, override)
        base = (root / 'compose.yaml').read_text()
        self.assertIn('    build:\n      context: .\n      dockerfile: docker/Dockerfile\n', base)
        self.assertNotRegex(base, r'(?m)^\s*(?:network|extra_hosts|secrets):')
        dockerfile = (root / 'docker/Dockerfile').read_text()
        self.assertIn('--mount=type=secret,id=composer_ca', dockerfile)
        self.assertNotIn('id=composer_ca,required', dockerfile)
        self.assertIn('if [ -f /run/secrets/composer_ca ]; then', dockerfile)

    def test_output_is_bounded_and_success_is_not_a_failure(self):
        raw = '\n'.join('ERROR ' + str(index) + ' ' + ('!' * 1000) for index in range(100))
        result = evidence(raw, 'runtime_start', 1, {})
        self.assertLessEqual(len(result['safe_error_lines']), 24)
        self.assertLessEqual(len(result['safe_tail_lines']), 12)
        self.assertTrue(all(len(line) <= 400 for line in result['safe_tail_lines']))
        self.assertTrue(all(len(line) <= 400 for line in result['safe_error_lines']))
        passed = evidence(raw, 'image_build', 0, {})
        self.assertTrue(passed['passed'])
        self.assertEqual(passed['error_category'], 'none')
        self.assertEqual(passed['safe_error_lines'], [])
        with self.assertRaises(ValueError):
            evidence(raw, 'arbitrary_path', 1, {})


if __name__ == '__main__':
    unittest.main()
