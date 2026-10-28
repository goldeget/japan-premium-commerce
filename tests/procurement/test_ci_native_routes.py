#!/usr/bin/env python3
"""Offline native account route and server form navigation contracts."""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse


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


    def test_native_admin_form_action_preserves_target_and_denies_route_gaps(self):
        namespace = dict(self.namespace, parse_qs=parse_qs)
        function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == 'native_admin_form_url')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'native_admin_form_url', 'exec'), namespace)
        target = 'AdminOrdenowaProcurementPolicies'
        action = 'http://localhost:18081/admin-kuranea/index.php?controller=' + target + '&token=native-form-token&_token=native-session-token'
        self.assertEqual(namespace['native_admin_form_url'](action, target, 'own-form-token'), action)
        directory_action = action.replace('/admin-kuranea/index.php', '/admin-kuranea/')
        self.assertEqual(namespace['native_admin_form_url'](directory_action, target, 'own-form-token'), directory_action)
        for invalid, controller, form_token in (
            (action.replace('localhost:18081', 'external.invalid'), target, 'own'),
            (action.replace('/admin-kuranea/index.php', '/other/path'), target, 'own'),
            (action, 'AdminOrdenowaProcurementReviews', 'own'),
            (action.replace('&token=native-form-token', ''), target, 'own'),
            (action + '&token=duplicate', target, 'own'),
            (action, target, ''),
            (action, 'AdminUnrelated', 'own'),
        ):
            with self.subTest(controller=controller, form_token=bool(form_token)):
                with self.assertRaises(AssertionError):
                    namespace['native_admin_form_url'](invalid, controller, form_token)

    def test_acl_denial_posts_target_form_body_token(self):
        captured = {}
        driver = SimpleNamespace(current_url='http://localhost:18081/admin-kuranea/index.php?token=url-token',
                                 find_elements=lambda *args: [])
        token = SimpleNamespace(get_attribute=lambda name: 'target-form-body-token')
        form = SimpleNamespace(find_element=lambda *args: token)
        def fetch(current, url, data):
            captured.update(data)
            return {'status': 403, 'private': True}
        namespace = dict(self.namespace, admin_page=lambda *args: None,
                         visible=lambda *args: form, fetch=fetch, By=SimpleNamespace(CSS_SELECTOR='css'))
        function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == 'denied_admin_action')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'denied_admin_action', 'exec'), namespace)
        namespace['denied_admin_action'](driver, 'AdminOrdenowaProcurementReviews', 'review', {'id_request': 1})
        self.assertEqual(captured['token'], 'target-form-body-token')
        self.assertNotEqual(captured['token'], 'url-token')
        self.assertEqual(captured['procurement_action'], 'review')

    def test_submission_requires_replaced_complete_document_with_original_budget(self):
        testcase = self
        driver = SimpleNamespace(phase='old_complete')
        driver.execute_script = lambda script: 'loading' if driver.phase == 'new_loading' else 'complete'
        observations = []

        class Wait:
            def __init__(self, current, budget):
                testcase.assertIs(current, driver)
                testcase.assertEqual(budget, 30)

            def until(self, condition):
                for phase, expected in (('old_complete', False), ('new_loading', False), ('new_complete', True)):
                    driver.phase = phase
                    observed = bool(condition(driver))
                    observations.append(observed)
                    testcase.assertEqual(observed, expected)

        namespace = {'WebDriverWait': Wait,
                     'EC': SimpleNamespace(staleness_of=lambda form: lambda current: current.phase != 'old_complete')}
        function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == 'wait_admin_submission')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'wait_admin_submission', 'exec'), namespace)
        namespace['wait_admin_submission'](driver, object())
        self.assertEqual(observations, [False, False, True])
        consumers = [node for node in ast.walk(SOURCE) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'wait_admin_submission']
        self.assertEqual(len(consumers), 2)  # Generic actions and policy save.

    def test_viewport_waits_for_pending_running_cancelled_and_replaced_transitions(self):
        namespace = {}
        function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == 'viewport_ready')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'viewport_ready', 'exec'), namespace)
        ready = namespace['viewport_ready']
        for transitions, expected in (
            ([{'pending': True, 'playState': 'running'}], False),
            ([{'pending': False, 'playState': 'running'}], False),
            ([{'pending': False, 'playState': 'paused'}], False),
            ([{'pending': False, 'playState': 'unknown'}], False),
            ([{'pending': False, 'playState': 'idle'}], True),  # Cancelled.
            ([{'pending': False, 'playState': 'idle'}, {'pending': True, 'playState': 'running'}], False),
            ([{'pending': False, 'playState': 'idle'}, {'pending': False, 'playState': 'finished'}], True),
            ([], True),
        ):
            with self.subTest(transitions=transitions):
                driver = SimpleNamespace(execute_script=lambda script: {'width': 320, 'transitions': transitions})
                self.assertEqual(ready(driver, 320), expected)
        driver = SimpleNamespace(execute_script=lambda script: {'width': 390, 'transitions': []})
        self.assertFalse(ready(driver, 320))
        script = function.body[0].value.args[0].value
        self.assertIn('document.documentElement.offsetHeight', script)
        self.assertIn('document.getAnimations()', script)
        self.assertIn("typeof animation.transitionProperty === 'string'", script)

    def test_viewport_preserves_original_wait_budget_and_exact_width_guard(self):
        observed = []
        driver = SimpleNamespace(execute_cdp_cmd=lambda *args: None, execute_script=lambda script: 320)
        testcase = self
        class Wait:
            def __init__(self, current, budget):
                testcase.assertIs(current, driver)
                testcase.assertEqual(budget, 30)
            def until(self, condition):
                testcase.assertTrue(condition(driver))
        namespace = {'WebDriverWait': Wait, 'check': lambda condition: testcase.assertTrue(condition),
                     'viewport_ready': lambda current, width: observed.append((current, width)) or True}
        function = next(node for node in SOURCE.body if isinstance(node, ast.FunctionDef) and node.name == 'viewport')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'viewport', 'exec'), namespace)
        namespace['viewport'](driver, 320)
        self.assertEqual(observed, [(driver, 320)])


if __name__ == '__main__':
    unittest.main()
