"""Guard Korean native-product administration and its isolated QA coverage."""
from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneacatalog"


class ProductAdminContractTests(unittest.TestCase):
    def test_product_manager_round_trips_english_fields_alongside_japanese_and_korean(self) -> None:
        draft = (MODULE / "src" / "Domain" / "ProductAdminDraft.php").read_text(encoding="utf-8")
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        persistence = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")

        for expected in ("nameEn", "descriptionEn", "name_en", "description_en"):
            with self.subTest(draft=expected):
                self.assertIn(expected, draft)
        self.assertIn("$values['name_en'] ?? ''", draft)
        self.assertIn("$values['description_en'] ?? ''", draft)
        for expected in ('Tools::getValue(\'name_en\'', 'Tools::getValue(\'description_en\'', 'renderTextField(\'name_en\'', 'renderTextArea(\'description_en\''):
            with self.subTest(controller=expected):
                self.assertIn(expected, controller)
        for expected in ("'en' => null", "'name_en'", "'description_en'", "$draft->nameEn", "$draft->descriptionEn"):
            with self.subTest(service=expected):
                self.assertIn(expected, service)
        for expected in ("name_en", "description_en", "English name", "English description", "link_rewrite", "image_lang", "English image legend"):
            with self.subTest(persistence=expected):
                self.assertIn(expected, persistence)
        for expected in ('#name_en', '#description_en', 'fill(driver, "#name_en"', 'fill(driver, "#description_en"'):
            with self.subTest(browser=expected):
                self.assertIn(expected, browser)

    def test_native_product_create_reports_individual_failed_persistence_fields(self) -> None:
        integration = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")

        self.assertIn("$createChecks = [", integration)
        self.assertIn("Native product create failed checks:", integration)
        for check in ("Japanese name", "English name", "English product slug", "English image legend", "inactive sale gate"):
            with self.subTest(check=check):
                self.assertIn(f"'{check}' =>", integration)
        for readback_key in ("english-field readback", "expected_slug", "saved_slug", "expected_image_legend", "saved_image_legend"):
            with self.subTest(readback=readback_key):
                self.assertIn(readback_key, integration)
        for edit_readback in ("english-field readback", "expected_slug", "saved_slug", "expected_image_legend", "saved_image_legend"):
            with self.subTest(edit_readback=edit_readback):
                self.assertIn(edit_readback, integration.split("$englishEditFieldReadback", 1)[1])

    def test_native_manager_reapplies_localized_slugs_and_image_legends_per_language(self) -> None:
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        save_method = service.split("public function save(", 1)[1].split("public function optionGroups(", 1)[0]

        self.assertIn("$this->persistLocalizedFields($savedProductId, $draft, $shopId);", save_method)
        persistence = service.split("private function persistLocalizedFields(", 1)[1].split("private function optionText(", 1)[0]
        for expected in (
            "\\Language::getLanguages(false)",
            "if (!array_key_exists($languageId, $slugs) || !array_key_exists($languageId, $legends))",
            "SELECT `link_rewrite` FROM `",
            "SELECT `legend` FROM `",
            "$savedSlug !== $slugs[$languageId]",
            "$savedLegend !== $legends[$languageId]",
            "상품 URL 슬러그의 언어별 저장값을 다시 확인하지 못했습니다.",
            "상품 이미지 설명의 언어별 저장값을 다시 확인하지 못했습니다.",
            "new \\Product($productId, false, $languageId, $shopId)",
            "setFieldsToUpdate(['link_rewrite' => [$languageId => true]])",
            "new \\Image($imageId, $languageId, $shopId)",
            "setFieldsToUpdate(['legend' => [$languageId => true]])",
            "if (!$localizedProduct->update())",
            "if (!$image->update())",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, persistence)

    def test_localized_persistence_failures_report_payload_and_shop_scope_without_values(self) -> None:
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        persistence = service.split("private function persistLocalizedFields(", 1)[1].split("private function optionText(", 1)[0]

        for expected in (
            "localizedPersistenceDiagnostics(",
            "context_shop_ids",
            "payload_field_present",
            "payload_language_ids",
            "payload_value_length",
            "stored_shop_rows",
            "shop_id",
            "value_length",
            "stored_value_length",
            "expected_matches",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, persistence)
        self.assertNotIn("'expected_value' =>", persistence)
        self.assertNotIn("'stored_value' =>", persistence)

    def test_localized_readbacks_do_not_add_a_second_get_value_limit(self) -> None:
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        persistence = service.split("private function persistLocalizedFields(", 1)[1].split("private function optionText(", 1)[0]
        readbacks = re.findall(r"getValue\(\s*(.*?)\s*,\s*false\s*\)", persistence, re.DOTALL)

        self.assertEqual(4, len(readbacks))
        for query in readbacks:
            with self.subTest(query=query):
                self.assertNotRegex(query, r"\bLIMIT\s+1\b")

    def test_native_admin_fixture_get_value_readbacks_do_not_add_a_duplicate_limit(self) -> None:
        integration = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")
        readbacks = re.findall(r"Db::getInstance\(\)->getValue\(\s*(.*?)\n\);", integration, re.DOTALL)

        self.assertEqual(7, len(readbacks))
        for query in readbacks:
            with self.subTest(query=query):
                self.assertNotRegex(query, r"\bLIMIT\b")

    def test_english_fallback_php_fixture_preserves_required_legacy_fields(self) -> None:
        fixture = (ROOT / "tests" / "catalog" / "product_admin_draft.php").read_text(encoding="utf-8")
        fallback = fixture.split("$englishFallbackDraft = ProductAdminDraft::fromArray([", 1)[1].split(
            "\n]);", 1
        )[0]

        for existing_field in ("'name_ja'", "'name_ko'", "'description_ja'", "'description_ko'"):
            with self.subTest(field=existing_field):
                self.assertIn(existing_field, fallback)
        self.assertNotIn("'name_en'", fallback)
        self.assertNotIn("'description_en'", fallback)

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
        self.assertIn("상품명 (영어)", controller)
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

    def test_product_save_reuses_prestashop_admin_controller_token_validation(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(
            encoding="utf-8"
        )
        save_method = controller.split("private function processProductSave(", 1)[1].split(
            "private function submittedValues()", 1
        )[0]
        render_method = controller.split("private function renderManager(", 1)[1].split(
            "private function renderTextField(", 1
        )[0]

        self.assertIn("if (!$this->checkToken())", save_method)
        self.assertNotIn("Tools::getAdminTokenLite", save_method)
        self.assertIn("Tools::getAdminTokenLite('AdminOrdenowaProductManager')", render_method)

    def test_native_product_manager_enforces_safe_state_and_native_fields(self) -> None:
        service_path = MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php"
        self.assertTrue(service_path.is_file(), "the native product manager service is missing")
        service = service_path.read_text(encoding="utf-8")
        for expected in (
            "available_for_order",
            "show_price",
            "product_shop",
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

    def test_imported_product_editor_rejects_new_images_but_keeps_other_edits_and_removals(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")
        save_method = controller.split("private function processProductSave(", 1)[1].split(
            "private function submittedValues()", 1
        )[0]
        self.assertIn("private function isImportedProduct(", controller)
        imported_check = controller.split("private function isImportedProduct(", 1)[1].split(
            "private function fail(", 1
        )[0]
        upload_check = controller.split("private function hasSuccessfulImageUpload(", 1)[1].split(
            "private function renderManager(", 1
        )[0]
        image_renderer = controller.split("private function renderImages(", 1)[1].split(
            "private function emptyFormValues()", 1
        )[0]

        self.assertIn("$this->isImportedProduct($this->editorProductId)", save_method)
        self.assertIn("UPLOAD_ERR_OK", upload_check)
        self.assertIn("$this->hasSuccessfulImageUpload($uploads)", save_method)
        self.assertIn("$uploads = []", save_method)
        self.assertIn("$this->selectedImageIds", save_method)
        self.assertIn("ProductAdminDraft::fromArray($this->formValues)", save_method)
        self.assertIn("save(", save_method)
        self.assertIn("가져온 초안에는 이 화면에서 새 이미지를 추가하지 않았습니다", save_method)
        self.assertIn("str_starts_with((string) $product->reference, 'OWA-IMPORT-')", imported_check)
        self.assertIn('CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_)', imported_check)
        self.assertIn('containsLinkedNativeProduct($productId)', imported_check)
        self.assertIn('return true', imported_check)
        self.assertIn("disabled", image_renderer)
        self.assertIn("출처 이미지 검수에서 사용권을 기록한 뒤 연결해 주세요", image_renderer)
        self.assertIn('name="remove_image_ids[]"', image_renderer)

    def test_imported_draft_creation_and_retry_require_complete_persisted_readback(self) -> None:
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        imported_method = service.split("public function saveImportedDraftWithResult(", 1)[1].split(
            "private function persistLocalizedFields(", 1
        )[0]

        existing_retry = imported_method.split("if ($existingId > 0)", 1)[1].split(
            "return new NativeImportedDraftResult($existingId, false)", 1
        )[0]
        created_save = imported_method.split("$createdId = $this->save(null", 1)[1]
        self.assertIn("$this->assertPersistedImportedDraftMatches(", existing_retry)
        self.assertIn("$this->assertPersistedImportedDraftMatches(", created_save)
        helper = service.split("private function assertPersistedImportedDraftMatches(", 1)[1].split(
            "private function persistLocalizedFields(", 1
        )[0]
        for persisted_field in (
            "editorData($productId)",
            "name_ja",
            "name_en",
            "name_ko",
            "description_ja",
            "description_en",
            "description_ko",
            "price_jpy",
            "tax_rules_group_id",
            "category_ids",
            "combination_quantities",
            "imageIds($productId)",
            "show_price",
            "available_for_order",
            "visibility",
            "active",
        ):
            with self.subTest(field=persisted_field):
                self.assertIn(persisted_field, helper)

    def test_imported_draft_readback_compares_exact_native_combination_tuples(self) -> None:
        service = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        helper = service.split("private function assertPersistedImportedDraftMatches(", 1)[1].split(
            "private function persistLocalizedFields(", 1
        )[0]
        for marker in (
            "product_attribute_combination",
            "$expectedOptionMemberships",
            "$actualOptionMemberships",
            "actualCombinationPriceAdjustments",
            "네이티브 옵션 조합이 검토한 전체 옵션 조합",
            "검토되지 않은 개별 가격 조정",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, helper)

        integration = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")
        self.assertIn("incomplete imported combination", integration)
        self.assertIn("$incompleteImportedDraftRetryRejected", integration)
        self.assertIn("unreviewed imported variant price", integration)
        self.assertIn("$unreviewedImportedVariantPriceRetryRejected", integration)
        self.assertIn("$productCountBeforeImportedRetry", integration)
        self.assertIn("$productCountAfterImportedRetry", integration)

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
        for expected in ("saved product ID", "Japanese name", "price", "sale gate", "editor Japanese name", "editor Korean name", "Japanese description", "Korean description", "categories", "options", "combination IDs replaced", "image replacement"):
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
            "Verify Japanese, English, and Korean native product draft validation in PHP",
        ):
            with self.subTest(workflow=expected):
                self.assertIn(expected, workflow)
        self.assertLess(
            workflow.index("Verify native inactive Korean admin product create and edit persistence"),
            workflow.index("Download and import official Japan Post KEN_ALL data"),
        )

    def test_browser_upload_fixtures_remain_available_until_chrome_closes(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        run = browser.split("def run() -> None:", 1)[1].split("def run_mobile_layout() -> None:", 1)[0]
        create_flow = run.split('stage = "native_product_create"', 1)[1].split(
            'stage = "native_product_edit"', 1
        )[0]
        edit_flow = run.split('stage = "native_product_edit"', 1)[1].split(
            "except Exception as error:", 1
        )[0]
        cleanup = run.split("    finally:", 1)[1]

        self.assertIn("temporary_upload_paths: list[Path] = []", run)
        self.assertIn("def write_temporary_png", browser)
        self.assertIn("write_temporary_png(png,", create_flow)
        self.assertIn("write_temporary_png(png,", edit_flow)
        self.assertNotIn("with tempfile.NamedTemporaryFile", create_flow + edit_flow)
        self.assertLess(cleanup.index("driver.quit()"), cleanup.index("image_path.unlink(missing_ok=True)"))

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
        self.assertIn("add_denied_marker:", browser)
        self.assertIn("edit_denied_marker:", browser)
        self.assertIn("save_diagnostics", failure_handler)
        self.assertIn("alert_class", browser)
        self.assertIn("message_category", browser)

    def test_native_product_save_wait_ignores_only_the_static_information_banner(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(
            encoding="utf-8"
        )
        save_result = browser.split("def product_save_result", 1)[1].split(
            "def product_post_failure_diagnostics", 1
        )[0]

        self.assertIn("candidate.classList.contains('alert-info')", save_result)
        self.assertIn("상품은 기본적으로 비활성·비노출·주문 불가 상태로 저장됩니다.", save_result)
        self.assertIn("return !isExpectedInformationalBanner", save_result)
        self.assertIn(
            "'<p class=\"alert alert-info\">상품은 기본적으로 비활성·비노출·주문 불가 상태로 저장됩니다.",
            controller,
        )

    def test_product_post_failure_diagnostics_are_allowlisted_and_token_safe(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        self.assertIn("def product_post_failure_diagnostics", browser)
        helper = browser.split("def product_post_failure_diagnostics", 1)[1].split(
            "\n\ndef product_links", 1
        )[0]
        form_diagnostics = browser.split("def product_form_diagnostics", 1)[1].split(
            "\n\ndef product_save_result", 1
        )[0]
        failure_handler = browser.split("except Exception as error:", 1)[1].split("finally:", 1)[0]

        for expected in (
            "window.location.pathname",
            "params.get('controller')",
            "document.title",
            "responseStatus",
            "page_markers",
            "product_form_present",
            "login_form_present",
            "manager_route_present",
            "product_list_present",
            "alert_class",
            "error_markers",
            "no_visible_response",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, helper)

        self.assertNotIn("window.location.href", helper)
        self.assertNotIn("innerHTML", helper)
        self.assertIn('"form_before_submit": form_before_submit or {}', helper)
        self.assertIn('"form_after_response": product_form_diagnostics(driver)', helper)
        self.assertIn("populated_field_names", form_diagnostics)
        self.assertNotIn('"token"', helper)
        self.assertIn("product_post_failure_diagnostics(driver, form_before_submit)", failure_handler)
        self.assertNotIn("alert_text", failure_handler)

    def test_product_post_route_and_network_diagnostics_are_path_only_and_bounded(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        self.assertIn("def product_post_network_diagnostics", browser)
        form_diagnostics = browser.split("def product_form_diagnostics", 1)[1].split(
            "\n\ndef product_save_result", 1
        )[0]
        network_diagnostics = browser.split("def product_post_network_diagnostics", 1)[1].split(
            "\n\ndef product_post_failure_diagnostics", 1
        )[0]
        failure_diagnostics = browser.split("def product_post_failure_diagnostics", 1)[1].split(
            "\n\ndef product_links", 1
        )[0]
        create_flow = browser.split('stage = "native_product_create"', 1)[1].split(
            'stage = "native_product_edit"', 1
        )[0]

        for expected in (
            "action_origin_matches_current",
            "action_path",
            "action_is_admin_path",
            "action_controller_is_manager",
            "action.pathname",
            "action.origin === window.location.origin",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, form_diagnostics)

        for expected in (
            'driver.get_log("performance")',
            "Network.requestWillBeSent",
            "Network.responseReceived",
            "Network.loadingFailed",
            "redirects",
            "redirect_target_path",
            "post_response_status",
            "failure_category",
            "[:2000]",
            "len(redirects) < 3",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, network_diagnostics)

        self.assertIn('options.set_capability("goog:loggingPrefs", {"performance": "ALL"})', browser)
        self.assertIn("clear_product_browser_network_events(driver)", create_flow)
        self.assertIn('"post_network_records": network_diagnostics["records"]', failure_diagnostics)
        self.assertIn("safePath(action.pathname)", form_diagnostics)
        self.assertNotIn("action.href", form_diagnostics)
        self.assertNotIn('"headers"', network_diagnostics)
        self.assertNotIn('"postData"', network_diagnostics)
        self.assertNotIn('"request_url"', network_diagnostics)
        self.assertNotIn('"redirect_url"', network_diagnostics)

    def test_product_post_network_records_drop_query_values_headers_and_request_body(self) -> None:
        browser_path = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"
        tree = ast.parse(browser_path.read_text(encoding="utf-8"))
        helper_names = {
            "_safe_network_url_metadata",
            "_safe_http_status",
            "_safe_network_failure_category",
            "product_post_network_diagnostics",
        }
        helper_nodes = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({node.name for node in helper_nodes}, helper_names)

        namespace = {
            "BASE": "http://localhost:18080",
            "ADMIN_PATH": "/admin-kuranea",
            "json": json,
            "re": re,
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "webdriver": SimpleNamespace(Chrome=object),
        }
        helper_module = ast.Module(body=helper_nodes, type_ignores=[])
        exec(compile(helper_module, str(browser_path), "exec"), namespace)

        post_url = (
            "http://localhost:18080/admin-kuranea/index.php"
            "?controller=AdminOrdenowaProductManager&token=post-token-sentinel"
        )
        redirect_url = "http://localhost:18080/?token=redirect-token-sentinel"

        def event(method: str, params: dict[str, object]) -> dict[str, str]:
            return {"message": json.dumps({"message": {"method": method, "params": params}})}

        events = [
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "request-id-sentinel",
                    "request": {
                        "method": "POST",
                        "url": post_url,
                        "headers": {"Cookie": "session-cookie-sentinel", "Authorization": "auth-sentinel"},
                        "postData": "private-product-value-sentinel",
                    },
                },
            ),
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "request-id-sentinel",
                    "request": {"method": "GET", "url": redirect_url},
                    "redirectResponse": {
                        "url": post_url,
                        "status": 302,
                        "headers": {"Location": redirect_url, "Cookie": "response-cookie-sentinel"},
                    },
                },
            ),
            event(
                "Network.responseReceived",
                {"requestId": "request-id-sentinel", "response": {"status": 200, "headers": {}}},
            ),
        ]

        class FakeDriver:
            def get_log(self, name: str) -> list[dict[str, str]]:
                self.log_name = name
                return events

        fake_driver = FakeDriver()
        diagnostics = namespace["product_post_network_diagnostics"](fake_driver)
        rendered = json.dumps(diagnostics, sort_keys=True)

        self.assertEqual(fake_driver.log_name, "performance")
        self.assertEqual(len(diagnostics["records"]), 1)
        record = diagnostics["records"][0]
        self.assertEqual(record["path"], "/admin-kuranea/index.php")
        self.assertTrue(record["origin_matches_shop"])
        self.assertTrue(record["is_admin_path"])
        self.assertTrue(record["controller_is_manager"])
        self.assertEqual(record["post_response_status"], 302)
        self.assertEqual(record["redirects"][0]["redirect_target_path"], "/")
        self.assertEqual(record["redirects"][0]["status"], 302)
        for secret_marker in (
            "post-token-sentinel",
            "redirect-token-sentinel",
            "session-cookie-sentinel",
            "response-cookie-sentinel",
            "auth-sentinel",
            "private-product-value-sentinel",
            "AdminOrdenowaProductManager",
            "request-id-sentinel",
        ):
            with self.subTest(secret_marker=secret_marker):
                self.assertNotIn(secret_marker, rendered)

    def test_product_network_failure_category_preserves_only_safe_error_enums(self) -> None:
        browser_path = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"
        tree = ast.parse(browser_path.read_text(encoding="utf-8"))
        helper = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_safe_network_failure_category"
        )
        namespace: dict[str, object] = {}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(browser_path), "exec"), namespace)
        categorize = namespace["_safe_network_failure_category"]

        self.assertEqual(categorize("net::ERR_ABORTED"), "aborted")
        self.assertEqual(categorize("net::ERR_CONNECTION_RESET"), "connection_reset")
        self.assertEqual(categorize("net::ERR_HTTP2_PROTOCOL_ERROR"), "net_error_http2_protocol_error")
        for value in (
            "net::ERR_",
            "net::ERR_BAD ERROR private-token",
            "net::ERR_" + "A" * 65,
            "net::ERR_ÄRGER",
            "untrusted secret-token",
            {"errorText": "net::ERR_SECRET"},
            None,
        ):
            with self.subTest(value=repr(value)):
                result = categorize(value)
                self.assertEqual(result, "other_failure")
                self.assertNotIn("SECRET", result)

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

    def test_product_edit_timeout_diagnostics_are_bounded_and_value_free(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        helper = browser.split("def product_edit_failure_diagnostics(", 1)[1].split(
            "\n\ndef product_links", 1
        )[0]
        edit_flow = browser.split('stage = "native_product_edit"', 1)[1].split(
            'stage = "mobile_product_admin_layout"', 1
        )[0]
        failure_handler = browser.split("except Exception as error:", 1)[1].split("finally:", 1)[0]

        for expected in (
            "manager_route_present",
            "product_form_present",
            "product_id_present",
            "product_id_matches",
            "category_ids_before_submit",
            "category_ids_after_response",
            "save_result_category",
            "error_markers",
            "final_field_match",
            "post_network_capture_available",
            "post_network_records_truncated",
            "post_network_records",
            ".slice(0, 20)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, helper)

        self.assertNotIn("window.location.href", helper)
        self.assertNotIn("alert_text", helper)
        self.assertNotIn("document.body.innerText", helper)
        self.assertIn('edit_operation = "wait_edit_save_confirmation"', edit_flow)
        self.assertIn("clear_product_browser_network_events(driver)", edit_flow)
        self.assertIn("product_edit_failure_diagnostics(", failure_handler)
        self.assertIn('edit_diagnostics=', failure_handler)

    def test_product_edit_confirmation_wait_uses_stale_safe_save_result(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        edit_flow = browser.split('stage = "native_product_edit"', 1)[1].split(
            "    except Exception as error:", 1
        )[0]

        self.assertIn('edit_save_result = WebDriverWait(driver, 45).until(product_save_result)', edit_flow)
        self.assertIn('edit_save_result.get("status") != "success"', edit_flow)
        self.assertNotIn('find_element(By.TAG_NAME, "body").text', edit_flow)

    def test_distinct_option_stock_readback_waits_for_fresh_form_and_retries_stale_snapshot(self) -> None:
        browser_path = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"
        browser = browser_path.read_text(encoding="utf-8")
        edit_flow = browser.split('stage = "native_product_edit"', 1)[1].split(
            "    except Exception as error:", 1
        )[0]
        submit_flow = edit_flow.split('edit_operation = "submit_distinct_option_stock"', 1)[1].split(
            'driver.save_screenshot(str(DEST / "product-admin-distinct-combination-stock-desktop.png"))', 1
        )[0]

        self.assertIn('distinct_stock_form = visible(driver, "form #name_ja")', edit_flow)
        self.assertIn("WebDriverWait(driver, 45).until(EC.staleness_of(distinct_stock_form))", submit_flow)
        self.assertIn("distinct_stock_result = WebDriverWait(driver, 45).until(product_save_result)", submit_flow)
        self.assertIn("saved_combination_stock_values = wait_for_combination_stock_values(", submit_flow)
        self.assertIn("expected_combination_quantities,", submit_flow)
        self.assertIn("saved_combination_stock_values != expected_combination_quantities", submit_flow)
        self.assertNotIn("saved_combination_stock_inputs = driver.find_elements", submit_flow)
        self.assertLess(
            submit_flow.index("EC.staleness_of(distinct_stock_form)"),
            submit_flow.index("product_save_result"),
        )
        self.assertLess(
            submit_flow.index("product_save_result"),
            submit_flow.index("wait_for_combination_stock_values"),
        )

        tree = ast.parse(browser)
        helper_names = {"combination_stock_values", "wait_for_combination_stock_values"}
        helper_nodes = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({node.name for node in helper_nodes}, helper_names)

        class StaleElementReferenceException(Exception):
            pass

        class FakeWebDriverWait:
            def __init__(self, driver, timeout, ignored_exceptions=()):
                self.driver = driver
                self.ignored_exceptions = ignored_exceptions

            def until(self, condition):
                for _attempt in range(3):
                    try:
                        result = condition(self.driver)
                    except self.ignored_exceptions:
                        continue
                    if result:
                        return result
                raise AssertionError("the stock readback did not become available")

        class FakeDriver:
            def __init__(self):
                self.snapshot_attempts = 0

            def execute_script(self, script):
                self.assert_stock_selector(script)
                self.snapshot_attempts += 1
                if self.snapshot_attempts == 1:
                    raise StaleElementReferenceException()
                if self.snapshot_attempts == 2:
                    return ["0", "0", "0", "0"]
                return ["0", "2", "4", "6"]

            @staticmethod
            def assert_stock_selector(script):
                if 'input[name^="combination_quantities["]' not in script:
                    raise AssertionError("stock readback must query fresh combination inputs")

        namespace = {
            "StaleElementReferenceException": StaleElementReferenceException,
            "WebDriverWait": FakeWebDriverWait,
            "webdriver": SimpleNamespace(Chrome=object),
        }
        exec(compile(ast.Module(body=helper_nodes, type_ignores=[]), str(browser_path), "exec"), namespace)
        driver = FakeDriver()
        self.assertEqual(
            namespace["wait_for_combination_stock_values"](driver, ["0", "2", "4", "6"]),
            ["0", "2", "4", "6"],
        )
        self.assertEqual(driver.snapshot_attempts, 3)

    def test_product_edit_category_diagnostics_keep_only_bounded_numeric_ids(self) -> None:
        browser_path = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"
        tree = ast.parse(browser_path.read_text(encoding="utf-8"))
        sanitizer = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_safe_category_ids"
        )
        namespace: dict[str, object] = {}
        exec(compile(ast.Module(body=[sanitizer], type_ignores=[]), str(browser_path), "exec"), namespace)

        diagnostic_ids = namespace["_safe_category_ids"](
            ["secret-token-sentinel", -3, 0, True, 2**40, *range(1, 26)]
        )

        self.assertEqual(diagnostic_ids, list(range(1, 21)))
        self.assertNotIn("secret-token-sentinel", diagnostic_ids)

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
        self.assertIn(
            'if visible(driver, "#description_en").get_attribute("value") != "Synthetic English product description":',
            edit_flow,
            "Chromium must confirm the saved English description is reloaded before editing it",
        )
        self.assertIn('edited_links = product_links(driver, product_id)', edit_flow)
        self.assertIn('edited_links[0].find_element(By.XPATH, "./ancestor::li[contains(@class, \'well\')]")', edit_flow)
        self.assertIn('f"ID {product_id}"', edit_flow)

    def test_browser_product_create_reads_back_ja_en_ko_descriptions(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        create_flow = browser.split('stage = "native_product_create"', 1)[1].split(
            'stage = "native_product_edit"', 1
        )[0]
        persisted_fields = create_flow.split("for selector, expected in (", 1)[1].split("):", 1)[0]

        self.assertIn('("#description_ja", "CI用の商品説明")', persisted_fields)
        self.assertIn('("#description_en", "Synthetic English product description")', persisted_fields)
        self.assertIn('("#description_ko", "CI용 상세 설명")', persisted_fields)

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
        self.assertIn('edit_category_name = f"ORDENOWA CI EDIT CATEGORY {run_id}-{run_attempt}"', edit_selection)
        self.assertIn("if not alternate_categories:", edit_selection)
        self.assertIn('edit_category_name in box.find_element(By.XPATH, "./ancestor::label[1]").text', edit_selection)
        self.assertIn("expected_category_ids = {edit_category_id}", edit_selection)
        self.assertNotIn("currently_selected.intersection(usable_ids)", edit_selection)

    def test_browser_category_selection_uses_visible_label_and_keyboard_fallback(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        self.assertIn("def set_category_checkbox_state", browser)
        category_click = browser.split("def set_category_checkbox_state", 1)[1].split("def fill(", 1)[0]
        create_flow = browser.split('create_operation = "select_default_category"', 1)[1].split(
            'create_operation = "prepare_image_file"', 1
        )[0]
        edit_flow = browser.split('edit_operation = "select_edit_category"', 1)[1].split(
            "edit_category_ids_before_submit =", 1
        )[0]

        self.assertIn('find_element(By.XPATH, "./ancestor::label[1]")', category_click)
        self.assertIn("if checkbox.is_selected() == selected:", category_click)
        self.assertIn("scrollIntoView({block: 'center'", category_click)
        self.assertIn("label.click()", category_click)
        self.assertIn("except ElementClickInterceptedException:", category_click)
        self.assertIn("checkbox.send_keys(Keys.SPACE)", category_click)
        self.assertIn("lambda _browser: checkbox.is_selected() == selected", category_click)
        self.assertIn("set_category_checkbox_state(driver, initial_category, True)", create_flow)
        self.assertIn("set_category_checkbox_state(driver, box, category_id in expected_category_ids)", edit_flow)

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
        diagnostics = browser.split("def manager_page_diagnostics", 1)[1].split(
            "\n\ndef clear_product_browser_network_events", 1
        )[0]

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

    def test_product_edit_switches_to_a_distinct_ci_category_and_persists_it(self) -> None:
        verifier = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")
        edit_verifier = verifier.split("$stage = 'native product edit';", 1)[1]
        edit_browser = browser.split('stage = "native_product_edit"', 1)[1].split(
            'stage = "mobile_product_admin_layout"', 1
        )[0]

        self.assertIn("new Category()", verifier)
        self.assertIn("$stage = 'synthetic product edit category';", verifier)
        self.assertIn("'ORDENOWA CI EDIT CATEGORY ' . $runId . '-' . $attempt", verifier)
        self.assertIn("ORDENOWA CI EDIT CATEGORY", verifier)
        self.assertIn("$editCategory->id_parent = $categoryId;", verifier)
        self.assertIn("$editCategory->id_shop_default = $shopId;", verifier)
        self.assertIn("$editCategory->active = 1;", verifier)
        self.assertIn("$editCategory->add()", verifier)
        self.assertIn("$editCategoryId === $categoryId", verifier)
        self.assertIn("'category_ids' => [(string) $editCategoryId]", edit_verifier)
        self.assertIn("'category default' => (int) $editedProduct->id_category_default === $editCategoryId", edit_verifier)
        self.assertIn("'category association changed'", edit_verifier)
        self.assertIn("'new category association'", edit_verifier)
        self.assertIn("ORDENOWA CI EDIT CATEGORY", edit_browser)
        self.assertIn("if not alternate_categories:", edit_browser)
        self.assertIn("category edit must select the isolated CI category", edit_browser)
        self.assertNotIn("currently_selected.intersection(usable_ids)", edit_browser)

    def test_product_edit_verifies_changed_option_values_in_native_combinations(self) -> None:
        verifier = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")
        edit_verifier = verifier.split("$stage = 'native product edit';", 1)[1]

        self.assertIn("'options' => \"色:青|緑\\nサイズ:S|M\"", edit_verifier)
        self.assertIn("$editedOptionGroups = $manager->optionGroups($savedProductId, $languageId, $shopId);", edit_verifier)
        self.assertIn("'option groups' => $editedOptionGroups === [", edit_verifier)
        self.assertIn("'native option combinations' => $editedCombinationValueSets === $expectedEditedCombinationValueSets", edit_verifier)
        self.assertIn("'combination IDs replaced'", edit_verifier)
        self.assertIn("'options' => ($editedEditor['options'] ?? '') === \"色:青|緑\\nサイズ:S|M\"", edit_verifier)

    def test_each_native_combination_has_an_editable_nonnegative_stock_value(self) -> None:
        draft = (MODULE / "src" / "Domain" / "ProductAdminDraft.php").read_text(encoding="utf-8")
        manager = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")
        verifier = (ROOT / "tests" / "catalog" / "verify_native_product_admin.php").read_text(encoding="utf-8")
        browser = (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8")

        self.assertIn("public readonly array $combinationQuantities", draft)
        self.assertIn("combination_quantities", draft)
        self.assertIn("'combination_quantities' =>", manager)
        self.assertIn("combinationStockRows", manager)
        self.assertIn("product-level stock row", manager)
        self.assertIn("Tools::getValue('combination_quantities', [])", controller)
        self.assertIn("renderCombinationQuantities", controller)
        self.assertIn('name="combination_quantities[', controller)
        self.assertIn("StockAvailable::setQuantity($productId, $combinationId, $quantity, $shopId)", manager)
        self.assertIn("array_combine($editedCombinationIds, [0, 2, 4, 6])", verifier)
        self.assertIn("unique combination quantities", verifier)
        self.assertIn("missing combination ID", verifier)
        self.assertIn("foreign combination ID", verifier)
        self.assertIn("($createdEditor['quantity'] ?? -1) !== 0", verifier)
        self.assertIn('input[name^="combination_quantities["]', browser)
        self.assertIn('("#quantity", "0")', browser)
        self.assertIn("distinct option stock", browser)
        self.assertIn('product-admin-distinct-combination-stock-desktop.png', browser)

if __name__ == "__main__":
    unittest.main()
