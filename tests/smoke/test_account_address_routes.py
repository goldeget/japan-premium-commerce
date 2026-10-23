"""Execute the account address route repair against localized Meta fixtures."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
START = "// Repair the Korean address/address-list default route collision."
END = "// Run after bundled modules have installed"


class AccountAddressRouteTests(unittest.TestCase):
    def repair(self, routes: dict[str, str], *, write_ok: bool = True) -> dict:
        php = os.environ.get("ACCOUNT_ROUTE_PHP") or shutil.which("php")
        if not php:
            self.skipTest("PHP CLI is required for the account address route regression")
        source = (ROOT / "docker/kuran-install-modules.php").read_text()
        section = source.split(START, 1)[1].split(END, 1)[0] if START in source else ""
        fixture = json.dumps({"routes": routes, "write_ok": write_ok})
        program = r'''<?php
define('_DB_PREFIX_', 'ps_');
function pSQL($value) { return addslashes($value); }
class Language { public static function getIdByIso($iso, $active) { return $iso === 'ko' ? 3 : 0; } }
class AddressRouteDatabase {
    public $routes;
    public $writes = [];
    public $queries = [];
    public $writeOk;
    public function executeS($sql, $array, $cache) {
        $this->queries[] = $sql;
        return array_map(fn($page, $slug) => ['page' => $page, 'id_meta' => $page === 'address' ? 10 : 11, 'url_rewrite' => $slug], array_keys($this->routes), array_values($this->routes));
    }
    public function update($table, $data, $where, ...$options) {
        $this->writes[] = [$table, $data, $where];
        if (!$this->writeOk) return false;
        $this->routes['addresses'] = $data['url_rewrite'];
        return true;
    }
    public function getValue($sql, $cache) { return $this->routes['addresses']; }
}
'''
        program += "$fixture = json_decode(" + json.dumps(fixture) + ", true);\n"
        program += "$db = new AddressRouteDatabase(); $db->routes = $fixture['routes']; $db->writeOk = $fixture['write_ok'];\n"
        program += section
        program += "\necho json_encode(['routes' => $db->routes, 'writes' => $db->writes, 'queries' => $db->queries]);"
        result = subprocess.run([php, "-n"], input=program, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_official_korean_defaults_dispatch_to_distinct_address_pages(self) -> None:
        for slug in ("주소", "%EC%A3%BC%EC%86%8C"):
            with self.subTest(slug=slug):
                result = self.repair({"address": slug, "addresses": slug})
                self.assertEqual(result["routes"]["address"], slug)
                self.assertEqual(result["routes"]["addresses"], "addresses")
                self.assertIn("id_shop = 1", result["queries"][0])
                self.assertIn("id_lang = 3", result["queries"][0])
                self.assertIn("id_meta = 11", result["writes"][0][2])

    def test_custom_and_already_distinct_routes_are_preserved(self) -> None:
        for routes in (
            {"address": "주소", "addresses": "my-addresses"},
            {"address": "새주소", "addresses": "주소"},
            {"address": "custom", "addresses": "custom"},
            {"address": "주소", "addresses": "addresses"},
        ):
            with self.subTest(routes=routes):
                result = self.repair(routes)
                self.assertEqual(result["routes"], routes)
                self.assertEqual(result["writes"], [])

    def test_failed_write_remains_retryable_on_next_bootstrap(self) -> None:
        routes = {"address": "주소", "addresses": "주소"}
        self.assertEqual(self.repair(routes, write_ok=False)["routes"], routes)
        self.assertEqual(self.repair(routes)["routes"]["addresses"], "addresses")


if __name__ == "__main__":
    unittest.main()
