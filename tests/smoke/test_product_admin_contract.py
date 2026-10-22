"""Guard Korean native-product administration and its isolated QA coverage."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneacatalog"


class ProductAdminContractTests(unittest.TestCase):
    def test_korean_product_manager_tab_and_controller_are_registered(self) -> None:
        module = (MODULE / "kuraneacatalog.php").read_text(encoding="utf-8")
        controller_path = MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php"

        self.assertTrue(controller_path.is_file(), "the native Korean product manager controller is missing")
        controller = controller_path.read_text(encoding="utf-8")
        self.assertIn("AdminOrdenowaProductManager", module)
        self.assertIn("Tab::getIdFromClassName('ShopParameters')", module)
        self.assertIn("상품 등록·관리", module)
        self.assertIn("상품명 (일본어)", controller)
        self.assertIn("상품명 (한국어)", controller)
        self.assertIn("상세 설명", controller)
        self.assertIn("상품 이미지", controller)
        self.assertIn("옵션", controller)
        self.assertIn("재고", controller)
        self.assertIn("카테고리", controller)

    def test_native_product_manager_enforces_safe_state_and_native_fields(self) -> None:
        service_path = MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php"
        self.assertTrue(service_path.is_file(), "the native product manager service is missing")
        service = service_path.read_text(encoding="utf-8")
        for expected in (
            "available_for_order",
            "visibility",
            "active",
            "StockAvailable::setQuantity",
            "new \\Combination",
            "new \\Image",
            "updateCategories",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, service)
        self.assertIn("OWA-ADMIN-", service)
        self.assertIn("validateImageChanges", service)
        self.assertIn("resultingImageCount", service)
        self.assertIn("validateOptionChanges", service)
        self.assertIn("\\Tools::str2url", service)
        self.assertNotIn("\\Tools::link_rewrite", service)
        save_method = service.split("public function save(", 1)[1].split("public function optionGroups(", 1)[0]
        self.assertLess(save_method.index("validateImageChanges"), save_method.index("$product->add()"))
        self.assertLess(save_method.index("validateImageChanges"), save_method.index("$product->update()"))
        self.assertLess(save_method.index("validateOptionChanges"), save_method.index("$product->add()"))
        self.assertLess(save_method.index("validateOptionChanges"), save_method.index("$product->update()"))
        self.assertIn("Tools::getAdminTokenLite", (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8"))

    def test_ci_product_persistence_and_browser_flows_cover_create_and_edit(self) -> None:
        integration = ROOT / "tests" / "catalog" / "verify_native_product_admin.php"
        browser = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.assertTrue(integration.is_file(), "isolated native product persistence verifier is missing")
        self.assertTrue(browser.is_file(), "Chromium product manager flow is missing")
        integration_text = integration.read_text(encoding="utf-8")
        browser_text = browser.read_text(encoding="utf-8")
        for expected in ("OWA-ADMIN-", "combinationRows", "createdCombinationIds", "editorData", "ShopParameters", "StockAvailable", "id_category_default", "available_for_order", "tooManyImagesRejected"):
            self.assertIn(expected, integration_text)
        for expected in (
            "상품 등록·관리",
            "native_product_create",
            "native_product_edit",
            "expected_category_ids",
            "edited_options",
            "product-admin-created-desktop.png",
            "product-admin-mobile.png",
        ):
            self.assertIn(expected, browser_text)
        for expected in (
            "tests/smoke/test_product_admin_contract.py",
            "tests/catalog/product_admin_draft.php",
            "tests/catalog/verify_native_product_admin.php",
            "tests/e2e/verify_product_admin_browser.py",
            "product-admin-e2e.log",
            "Verify Japanese and Korean native product draft validation in PHP",
        ):
            with self.subTest(workflow=expected):
                self.assertIn(expected, workflow)
        self.assertLess(
            workflow.index("Verify native inactive Korean admin product create and edit persistence"),
            workflow.index("Download and import official Japan Post KEN_ALL data"),
        )


if __name__ == "__main__":
    unittest.main()
