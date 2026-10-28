#!/usr/bin/env python3
"""Offline contract for authoritative native account routes; no browser required."""
import ast
from pathlib import Path
import unittest
from urllib.parse import urlparse


SOURCE = ast.parse(Path(__file__).with_name('ci_browser.py').read_text())


class NativeRouteTests(unittest.TestCase):
    def setUp(self):
        def check(condition):
            if not condition:
                raise AssertionError('Native route denied')
        self.routes = {'authentication': 'http://localhost:18081/ja/login',
                       'identity': 'http://localhost:18081/ja/identity'}
        self.namespace = {'IDENTITY': {'routes': {'ja': self.routes}},
                          'BASE': 'http://localhost:18081', 'urlparse': urlparse, 'check': check}
        function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == 'native_page_url')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'native_page_url', 'exec'), self.namespace)
        self.route = self.namespace['native_page_url']

    def test_native_generated_urls_are_preserved_exactly(self):
        for controller, expected in self.routes.items():
            self.assertEqual(self.route(controller), expected)
        self.routes['authentication'] = 'http://localhost:18081/ja/login?back=my-account'
        self.assertEqual(self.route('authentication'), self.routes['authentication'])

    def test_cross_origin_userinfo_and_relative_routes_are_denied(self):
        for invalid in ('https://external.invalid/login', 'https://localhost:18081/login',
                        'http://localhost:18082/login', 'http://user:password@localhost:18081/login', '/login'):
            with self.subTest(route=invalid):
                self.routes['authentication'] = invalid
                with self.assertRaises(AssertionError):
                    self.route('authentication')

    def test_login_and_identity_consume_native_route_helper(self):
        for function_name, controller in (('login_customer', 'authentication'), ('native_identity', 'identity')):
            function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == function_name)
            first = function.body[0].value
            self.assertIsInstance(first, ast.Call)
            self.assertEqual(first.func.attr, 'get')
            self.assertEqual(first.args[0].func.id, 'native_page_url')
            self.assertEqual(first.args[0].args[0].value, controller)


if __name__ == '__main__':
    unittest.main()
