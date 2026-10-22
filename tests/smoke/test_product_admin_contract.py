"""Guard Korean native-product administration and its isolated QA coverage."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneacatalog"


class ProductAdminContractTests(unittest.TestCase):
    def test_global_admin_controller_qualifies_builtin_exception_without_global_import(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")

        self.assertNotIn("use InvalidArgumentException;", controller)
        self.assertIn("catch (\\InvalidArgumentException $exception)", controller)

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

    def test_product_manager_uses_prestashop_lazy_tab_access_checks(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")
        can_view = controller.split("private function canView(): bool", 1)[1].split("private function canAdd()", 1)[0]
        can_add = controller.split("private function canAdd(): bool", 1)[1].split("private function canEdit()", 1)[0]
        can_edit = controller.split("private function canEdit(): bool", 1)[1].split("private function fail(", 1)[0]

        self.assertIn("return $this->viewAccess();", can_view)
        self.assertIn("$this->canView() && $this->access('add')", can_add)
        self.assertIn("$this->canView() && $this->access('edit')", can_edit)
        for access_method in (can_view, can_add, can_edit):
            self.assertNotIn("tabAccess", access_method)

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
            manager_navigation.index("manager_page_diagnostics(driver)"),
        )
        self.assertLess(
            manager_navigation.index("driver.get(href)"),
            manager_navigation.index('product-admin-manager-navigation.png'),
        )
        self.assertLess(
            manager_navigation.index('product-admin-manager-navigation.png'),
            manager_navigation.index("manager_page_diagnostics(driver)"),
        )
        self.assertIn("visible(driver, 'form #name_ja')", manager_navigation)
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

    def test_created_product_id_uses_presence_wait_for_hidden_input(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")

        self.assertIn('<input type="hidden" name="id_product"', controller)
        self.assertIn('presence_of_element_located((By.CSS_SELECTOR, \'input[name="id_product"]\'))', browser)
        self.assertNotIn('visible(driver, \'input[name="id_product"]\')', browser)

    def test_manager_link_discovery_accepts_collapsed_sidebar_entries(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        manager_link = browser.split("def manager_link(", 1)[1].split("\n\ndef product_links", 1)[0]

        self.assertIn('parse_qs(urlparse(href).query).get("controller", []) == ["AdminOrdenowaProductManager"]', manager_link)
        self.assertNotIn("is_displayed()", manager_link)

    def test_manager_page_failure_diagnostics_exclude_query_tokens(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")

        for expected in (
            "product_heading:",
            "name_ja_present:",
            "denied_marker:",
            "load_error_marker:",
            "login_form_present:",
            "product_form_present:",
            "pathname: window.location.pathname",
            "title: document.title",
            "page_state=",
            "json.dumps",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, browser)
        self.assertNotIn("window.location.search", browser)

    def test_install_verifier_checks_product_manager_read_permission(self) -> None:
        verifier = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")

        self.assertIn("Permission::PREFIX_TAB . 'ADMINORDENOWAPRODUCTMANAGER_READ'", verifier)
        self.assertIn("Access::isGranted($readPermission, 1)", verifier)


if __name__ == "__main__":
    unittest.main()
