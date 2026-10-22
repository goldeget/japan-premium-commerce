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
        self.assertIn("new \\Product((int) $product->id, false, null, $shopId)", save_method)
        self.assertLess(save_method.index("$this->loadManagedProduct"), save_method.index("new \\Product((int) $product->id, false, null, $shopId)"))
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
        self.assertIn("Native product edit failed checks:", integration_text)
        for expected in ("saved product ID", "Japanese name", "price", "sale gate", "editor Japanese name", "editor Korean name", "Japanese description", "Korean description", "categories", "options", "combination IDs", "image replacement"):
            self.assertIn(f"'{expected}' =>", integration_text)
        for expected in (
            "새 상품 등록",
            "native_product_create",
            "native_product_edit",
            "expected_category_ids",
            "edited_options",
            "product-admin-created-desktop.png",
            "product-admin-mobile.png",
        ):
            self.assertIn(expected, browser_text)
        manager_navigation = browser_text.split('stage = "korean_product_manager_link"', 1)[1].split(
            'stage = "native_product_create"', 1
        )[0]
        self.assertIn('stage = "korean_product_manager_form"', manager_navigation)
        self.assertLess(
            manager_navigation.index("driver.get(href)"),
            manager_navigation.index('stage = "korean_product_manager_form"'),
        )
        self.assertLess(
            manager_navigation.index('stage = "korean_product_manager_form"'),
            manager_navigation.index('visible(driver, "form")'),
        )
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

    def test_chromium_product_failure_emits_a_github_annotation(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        handler = browser.split("except Exception as error:", 1)[1].split("finally:", 1)[0]

        self.assertIn("ORDENOWA_PRODUCT_ADMIN_STAGE=", handler)
        self.assertIn("::error title=ORDENOWA product admin browser::", handler)
        self.assertIn("replace('%', '%25')", handler)
        self.assertIn("print(annotation", handler)

    def test_chromium_startup_is_inside_the_product_failure_handler(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        run_method = browser.split("def run() -> None:", 1)[1].split("if __name__ == \"__main__\":", 1)[0]

        self.assertIn('stage = "chromium_startup"', run_method)
        self.assertLess(run_method.index("try:"), run_method.index("driver = webdriver.Chrome(options=options)"))
        self.assertIn("if driver is not None:", run_method)

    def test_manager_link_discovery_accepts_collapsed_sidebar_entries(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        manager_link = browser.split("def manager_link(", 1)[1].split("\n\ndef product_links", 1)[0]

        self.assertIn('parse_qs(urlparse(href).query).get("controller", []) == ["AdminOrdenowaProductManager"]', manager_link)
        self.assertNotIn("is_displayed()", manager_link)


if __name__ == "__main__":
    unittest.main()
