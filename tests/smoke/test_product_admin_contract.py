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

    def test_product_save_helper_does_not_override_prestashop_admin_controller(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")

        self.assertIn("$this->processProductSave($manager);", controller)
        self.assertIn(
            "private function processProductSave(PrestaShopNativeProductManager $manager): void",
            controller,
        )
        self.assertNotIn("function processSave(", controller)

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
            "def usable_category_boxes(driver: webdriver.Chrome)",
            'box.get_attribute("value") != "1"',
            'box.get_attribute("value") == "2"',
            "created_category_ids != {initial_category_id}",
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

    def test_chromium_failure_diagnostics_never_emit_raw_exception_or_url(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        handlers = browser.split("except Exception as error:")[1:3]
        run_all = browser.split("def run_all() -> None:", 1)[1].split('\n\nif __name__ == "__main__":', 1)[0]

        self.assertEqual(len(handlers), 2, "desktop and mobile should each sanitize their scenario failures")
        for handler in handlers:
            with self.subTest(handler=handler[:50]):
                scenario_handler = handler.split("finally:", 1)[0]
                self.assertIn("type(error).__name__", scenario_handler)
                self.assertNotIn("{error}", scenario_handler)
                self.assertNotIn("str(error)", scenario_handler)
                self.assertNotIn("repr(error)", scenario_handler)
                self.assertNotIn("current_url", scenario_handler)
                self.assertIn("raise SystemExit(", scenario_handler)
                self.assertIn("from None", scenario_handler)

        self.assertIn("except SystemExit:", run_all)
        self.assertIn('raise SystemExit("product admin browser scenarios failed: " + ", ".join(failures)) from None', run_all)
        self.assertNotIn("window.location.href", browser)
        self.assertNotRegex(browser, r"(?m)^\s+raise\s*$")

    def test_chromium_startup_is_inside_the_product_failure_handler(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        run_method = browser.split("def run() -> None:", 1)[1].split("if __name__ == \"__main__\":", 1)[0]

        self.assertIn('stage = "chromium_startup"', run_method)
        self.assertLess(run_method.index("try:"), run_method.index("driver = webdriver.Chrome(options=options)"))
        self.assertIn("if driver is not None:", run_method)

    def test_product_admin_mobile_view_runs_after_desktop_failure(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        run_all = browser.split("def run_all() -> None:", 1)[1].split('\n\nif __name__ == "__main__":', 1)[0]

        self.assertIn("def run_mobile_layout() -> None:", browser)
        self.assertIn('("desktop", run)', run_all)
        self.assertIn('("mobile", run_mobile_layout)', run_all)
        self.assertIn("for label, scenario in", run_all)
        self.assertIn("try:", run_all)
        self.assertIn("scenario()", run_all)
        self.assertIn("except Exception as error:", run_all)
        self.assertIn("failures.append(label)", run_all)
        self.assertNotIn("break", run_all)

    def test_created_product_id_uses_presence_wait_for_hidden_input(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")

        self.assertIn('<input type="hidden" name="id_product"', controller)
        self.assertIn('presence_of_element_located((By.CSS_SELECTOR, \'input[name="id_product"]\'))', browser)
        self.assertNotIn('visible(driver, \'input[name="id_product"]\')', browser)

    def test_native_product_create_relocates_save_confirmation_body_and_reports_operation(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        create_flow = browser.split('stage = "native_product_create"', 1)[1].split(
            'stage = "native_product_edit"', 1
        )[0]
        failure_handler = browser.split("except Exception as error:", 1)[1].split("finally:", 1)[0]

        self.assertIn('create_operation = "submit_product"', create_flow)
        self.assertIn('create_operation = "wait_for_save_confirmation"', create_flow)
        self.assertIn("WebDriverWait(driver, 45).until(product_save_result)", create_flow)
        self.assertIn("bodyText.includes('상품 ID') && bodyText.includes('저장했습니다')", browser)
        self.assertNotIn('browser.find_element(By.TAG_NAME, "body").text', create_flow)
        self.assertIn('operation={create_operation}', failure_handler)

    def test_native_product_save_wait_reports_sanitized_visible_alerts_and_access_markers(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        create_flow = browser.split('stage = "native_product_create"', 1)[1].split(
            'stage = "native_product_edit"', 1
        )[0]
        failure_handler = browser.split("except Exception as error:", 1)[1].split("finally:", 1)[0]

        self.assertIn("def product_save_result", browser)
        self.assertIn('save_result["status"] != "success"', create_flow)
        self.assertIn('save_result["status"] == "alert"', create_flow)
        self.assertIn('"add_denied_marker"', browser)
        self.assertIn('"edit_denied_marker"', browser)
        self.assertIn("save_diagnostics", failure_handler)
        self.assertIn("alert_class", browser)
        self.assertIn("message_category", browser)
        self.assertNotIn("alert_text", failure_handler)

    def test_native_product_alert_diagnostics_identify_only_safe_controller_and_field_markers(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")
        draft = (MODULE / "src" / "Domain" / "ProductAdminDraft.php").read_text(encoding="utf-8")
        failure_handler = browser.split("except Exception as error:", 1)[1].split("finally:", 1)[0]

        for source_marker in ("관리자 보안 토큰이 올바르지 않습니다.", "상품을 등록할 권한이 없습니다.", "상품 저장에 실패했습니다."):
            self.assertIn(source_marker, controller)
        for source_marker in ("JPY 가격은", "재고는", "카테고리를 하나 이상", "상품 옵션 입력값"):
            self.assertIn(source_marker, draft)
        for expected in (
            "admin_token_invalid",
            "product_add_permission_denied",
            "price_jpy_invalid",
            "quantity_invalid",
            "category_ids_invalid",
            "product_options_invalid",
            "product_image_invalid",
            "field_error_names",
            "hidden_token_matches_action",
            "form_before_submit",
            "form_after_response",
            "product_list_present",
            "login_form_present",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, browser)
        self.assertNotIn("alert_text", failure_handler)
        self.assertNotIn("innerText", failure_handler)

    def test_browser_product_edit_verifies_korean_name_and_updated_inactive_list_record(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        edit_flow = browser.split('stage = "native_product_edit"', 1)[1].split(
            'stage = "mobile_product_admin_layout"', 1
        )[0]

        self.assertIn(
            'if visible(driver, "#name_ko").get_attribute("value") != korean_name + " 수정":',
            edit_flow,
            "Chromium must verify the edited Korean name on the same product record",
        )
        self.assertIn('edited_links = product_links(driver, product_id)', edit_flow)
        self.assertIn('edited_links[0].find_element(By.XPATH, "./ancestor::li[contains(@class, \'well\')]")', edit_flow)
        self.assertIn('f"ID {product_id}"', edit_flow)

    def test_browser_category_fixture_uses_home_and_excludes_technical_root(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        category_helper = browser.split("def usable_category_boxes", 1)[1].split("def fill(", 1)[0]
        edit_selection = browser.split('stage = "native_product_edit"', 1)[1].split(
            'stage = "mobile_product_admin_layout"', 1
        )[0]

        self.assertIn('box.get_attribute("value") != "1"', category_helper)
        self.assertIn('box.get_attribute("value") == "2"', category_helper)
        self.assertIn("initial_category = default_category_box(driver)", browser)
        self.assertIn("created_category_ids != {initial_category_id}", browser)
        self.assertIn("usable_ids = {box.get_attribute(\"value\") for box in usable_category_boxes(driver)}", edit_selection)
        self.assertIn("currently_selected.intersection(usable_ids)", edit_selection)

    def test_native_manager_excludes_root_and_rejects_it_as_a_default_category(self) -> None:
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        categories = service.split("public function categories()", 1)[1].split("public function managedProducts()", 1)[0]
        validation = service.split("private function validateCategories(", 1)[1].split("private function validateOptionChanges(", 1)[0]
        save_method = service.split("public function save(", 1)[1].split("public function optionGroups(", 1)[0]

        # PrestaShop's structural Root has id_parent=0. Home has a parent, so it
        # and other shop categories remain selectable while Root is rejected.
        self.assertIn("c.`id_parent` > 0", categories)
        self.assertIn("c.`id_parent` > 0", validation)
        self.assertLess(validation.index("c.`id_parent` > 0"), validation.index("c.`id_category` IN ("))
        self.assertLess(save_method.index("$this->validateCategories"), save_method.index("$product->id_category_default = $draft->categoryIds[0]"))

    def test_manager_link_discovery_accepts_collapsed_sidebar_entries(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        manager_link = browser.split("def manager_link(", 1)[1].split("\n\ndef product_links", 1)[0]

        self.assertIn('parse_qs(urlparse(href).query).get("controller", []) == ["AdminOrdenowaProductManager"]', manager_link)
        self.assertNotIn("is_displayed()", manager_link)

    def test_manager_page_failure_diagnostics_emit_no_raw_url_values(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        diagnostics = browser.split("def manager_page_diagnostics", 1)[1].split("def product_links", 1)[0]

        for expected in (
            "product_heading:",
            "name_ja_present:",
            "denied_marker:",
            "load_error_marker:",
            "login_form_present:",
            "product_form_present:",
            "manager_route_present:",
            "page_state=",
            "json.dumps",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, browser if expected in {"page_state=", "json.dumps"} else diagnostics)
        for unsafe_url_field in (
            "document.title",
            "window.location.pathname",
            "window.location.href",
            "window.location.host",
            "window.location.origin",
            "pathname:",
            "title:",
            "href:",
            "search:",
            "url:",
        ):
            with self.subTest(unsafe_url_field=unsafe_url_field):
                self.assertNotIn(unsafe_url_field, diagnostics)

    def test_install_verifier_checks_product_manager_read_permission(self) -> None:
        verifier = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")

        self.assertIn("Permission::PREFIX_TAB . 'ADMINORDENOWAPRODUCTMANAGER_READ'", verifier)
        self.assertIn("Access::isGranted($readPermission, 1)", verifier)


if __name__ == "__main__":
    unittest.main()
