from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"


class OrdersEmptyStateAssetTests(unittest.TestCase):
    def test_module_uses_the_shared_admin_end_hook_and_scopes_to_orders_in_korean(self) -> None:
        module_source = (MODULE / "kuraneabackoffice.php").read_text()

        self.assertIn("displayAdminEndContent", module_source)
        self.assertIn("hookDisplayAdminEndContent", module_source)
        self.assertIn("controller_name", module_source)
        self.assertIn("AdminOrders", module_source)
        self.assertIn("str_starts_with($languageIsoCode, 'ko')", module_source)
        self.assertIn("orders-empty-state-korean.js", module_source)

        upgrade = MODULE / "upgrade" / "upgrade-1.0.1.php"
        self.assertTrue(upgrade.is_file(), "existing installs need a hook registration upgrade")
        self.assertIn("registerHook('displayAdminEndContent')", upgrade.read_text())

    def test_module_script_replaces_only_the_core_orders_empty_state_asset(self) -> None:
        script_path = MODULE / "views" / "js" / "orders-empty-state-korean.js"
        self.assertTrue(script_path.is_file(), "missing module-owned Orders empty-state script")
        script = script_path.read_text()

        self.assertIn("themes/new-theme/img/empty_state/order.svg", script)
        self.assertIn("orders-empty-state-ko.svg", script)
        self.assertIn("MutationObserver", script)

    def test_replacement_illustration_has_no_english_sample_order_copy(self) -> None:
        image_path = MODULE / "views" / "img" / "orders-empty-state-ko.svg"
        self.assertTrue(image_path.is_file(), "missing module-owned localized illustration")
        image = image_path.read_text()

        for sample in ("Isabella", "$72", ">Order<"):
            with self.subTest(sample=sample):
                self.assertNotIn(sample, image)
        self.assertIn('viewBox="0 0 762 492"', image)


if __name__ == "__main__":
    unittest.main()
