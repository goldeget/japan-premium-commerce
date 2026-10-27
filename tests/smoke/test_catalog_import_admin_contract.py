"""Guard the Korean catalog import review form and its safe admin actions."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "modules" / "kuraneacatalog" / "controllers" / "admin" / "AdminKuraneaCatalogReviewController.php"
PRODUCT_DRAFT = ROOT / "modules" / "kuraneacatalog" / "src" / "Domain" / "ProductAdminDraft.php"
NATIVE_MANAGER = ROOT / "modules" / "kuraneacatalog" / "src" / "Integration" / "PrestaShopNativeProductManager.php"
IMAGE_PREVIEW = ROOT / "modules" / "kuraneacatalog" / "views" / "js" / "catalog-import-image-preview.js"


class CatalogImportAdminContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.controller = CONTROLLER.read_text(encoding="utf-8")
        cls.product_draft = PRODUCT_DRAFT.read_text(encoding="utf-8")
        cls.import_form = cls.controller.split("private function renderImportedDraftForm(", 1)[1].split(
            "private function hiddenReviewFields(", 1
        )[0]
        cls.draft_validation = cls.controller.split("private function processImportedDraft(", 1)[1].split(
            "private function validateImportMutation(", 1
        )[0]
        cls.batch_renderer = cls.controller.split("private function renderBatch(", 1)[1].split(
            "/** @param list<ProductReviewQueueEntry> $pending */", 1
        )[0]
        cls.tax_renderer = cls.controller.split("private function reviewTaxRules(", 1)[1].split(
            "/** @param list<array{id_category:int,name:string}> $categories */", 1
        )[0]
        import_processing = cls.controller.split("private function processImportRequests(", 1)[1].split(
            "private function processApproval(", 1
        )[0]
        cls.batch_submission = import_processing.split(
            "if (Tools::isSubmit('submitKuraneaCatalogImportBatch'))", 1
        )[1].split("if (Tools::isSubmit('submitKuraneaCatalogImportNext'))", 1)[0]

    def test_import_form_requires_separate_english_and_korean_translation_review(self) -> None:
        for field in ("translation_reviewed_en", "translation_reviewed_ko"):
            with self.subTest(field=field):
                self.assertIn(f'name="{field}" value="1" required', self.import_form)
        self.assertIn("영어 상품명·상세 설명 번역을 검수했습니다", self.import_form)
        self.assertIn("한국어 상품명·상세 설명 번역을 검수했습니다", self.import_form)
        self.assertIn("영어 상품명과 상세 설명을 일본어 원문과 대조", self.import_form)
        self.assertIn("한국어 상품명과 상세 설명을 일본어 원문과 대조", self.import_form)
        self.assertIn("Tools::getValue('translation_reviewed_en') !== '1'", self.draft_validation)
        self.assertIn("Tools::getValue('translation_reviewed_ko') !== '1'", self.draft_validation)

    def test_import_form_confirms_option_combinations_and_matching_source_price(self) -> None:
        self.assertIn("name=\"confirm_options_supported\" value=\"1\" required", self.import_form)
        self.assertIn("단일 옵션 값", self.import_form)
        self.assertIn("name=\"confirm_same_source_price\" value=\"1\"", self.import_form)
        self.assertIn("출처 참고 가격과 같은 판매가격", self.import_form)

        self.assertIn("$draft->priceJpy === $entry->snapshot->priceJpy", self.draft_validation)
        self.assertIn("Tools::getValue('confirm_same_source_price') !== '1'", self.draft_validation)
        self.assertIn("Tools::getValue('confirm_options_supported') !== '1'", self.draft_validation)
        self.assertIn("count($entry->snapshot->options) > 1", self.draft_validation)
        self.assertIn("옵션 연결을 지원하지 않아 초안 등록이 차단됩니다", self.import_form)
        self.assertIn("조합별 가격이나 출처 재고는 가져오지 않습니다", self.import_form)

    def test_imported_draft_readback_selects_native_combination_price(self) -> None:
        manager = NATIVE_MANAGER.read_text(encoding="utf-8")
        readback = manager.split("private function assertPersistedImportedDraftMatches(", 1)[1]
        self.assertIn("SELECT pa.`id_product_attribute`, pa.`price`,", readback)
        self.assertIn("$row['price'] ?? null", readback)
        self.assertIn("$priceAdjustment !== 0.0", readback)

    def test_import_form_exposes_tax_classification_and_exemption_evidence(self) -> None:
        self.assertIn('name="tax_treatment"', self.tax_renderer)
        self.assertIn('value="taxable"', self.tax_renderer)
        self.assertIn('value="explicitly_exempt"', self.tax_renderer)
        self.assertIn('name="tax_evidence_reference"', self.tax_renderer)
        self.assertIn('name="tax_rules_group_id" required', self.tax_renderer)

        self.assertIn("$taxTreatment !== 'explicitly_exempt'", self.draft_validation)
        self.assertIn("$taxEvidenceReference === ''", self.draft_validation)
        self.assertIn("$taxTreatment !== 'taxable'", self.draft_validation)
        self.assertIn("'tax_rules_group_id' => Tools::getValue('tax_rules_group_id', null)", self.draft_validation)
        self.assertIn("세금 규칙 그룹을 명시적으로 선택해 주세요.", self.product_draft)

    def test_batch_auto_progress_submits_the_named_action_button(self) -> None:
        self.assertIn('name="submitKuraneaCatalogImportNext" value="1"', self.batch_renderer)
        self.assertIn("querySelector(\\'button[name=\"submitKuraneaCatalogImportNext\"]\\')", self.batch_renderer)
        self.assertIn("f.requestSubmit(button)", self.batch_renderer)
        self.assertNotIn("f.requestSubmit();", self.batch_renderer)

    def test_unsupported_product_urls_use_safe_korean_feedback(self) -> None:
        self.assertIn(
            "$this->fail('상품 URL을 등록할 수 없습니다. 아마존 일본 또는 라쿠텐의 지원 상품 주소를 1~10개 입력해 주세요.');",
            self.batch_submission,
        )
        self.assertNotIn("$this->fail($exception->getMessage());", self.batch_submission)
        harness = (ROOT / "tests" / "catalog" / "admin_review_controller.php").read_text(encoding="utf-8")
        for marker in (
            "submitKuraneaCatalogImportBatch",
            "https://example.invalid/not-a-supported-product",
            "상품 URL을 등록할 수 없습니다. 아마존 일본 또는 라쿠텐의 지원 상품 주소를 1~10개 입력해 주세요.",
            "not a supported marketplace product URL",
            "A catalog import batch must contain between one and ten URLs.",
            'id="catalog-import-progress"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, harness)

    def test_admin_marketplace_heading_uses_korean_names_while_source_identifiers_remain_stable(self) -> None:
        render_form = self.controller.split("private function renderImportForm(", 1)[1].split(
            "private function renderBatch(", 1
        )[0]
        source_labels = self.controller.split("private function sourceLabel(", 1)[1].split(
            "private function fail(", 1
        )[0]

        self.assertIn("<h3>아마존 일본·라쿠텐 상품 URL 수집</h3>", render_form)
        self.assertNotIn("Amazon Japan", render_form)
        self.assertNotIn("Rakuten", render_form)
        self.assertIn("'amazon_jp' => '아마존 일본'", source_labels)
        self.assertIn("'rakuten_ichiba' => '라쿠텐 이치바'", source_labels)

    def test_existing_product_link_uses_the_product_managers_own_admin_token(self) -> None:
        self.assertIn("getAdminLink('AdminOrdenowaProductManager')", self.controller)
        self.assertIn("$this->productManagerUrl((int) $entry->linkedProductId)", self.controller)
        product_url_builder = self.controller.split("private function productManagerUrl(", 1)[1].split(
            "/** @param list<array{id_tax_rules_group:int,name:string}> $groups */", 1
        )[0]
        self.assertIn("'id_product=' . max(0, $productId)", product_url_builder)
        self.assertNotIn("'controller=AdminOrdenowaProductManager&id_product='", self.controller)

    def test_review_result_displays_approved_or_rejected_status_read_only(self) -> None:
        self.assertIn("private ?ProductReviewQueueEntry $reviewedEntry = null;", self.controller)
        self.assertIn("ProductReviewQueueEntry::STATUS_APPROVED", self.controller)
        self.assertIn("ProductReviewQueueEntry::STATUS_REJECTED", self.controller)
        self.assertIn("검수 처리 상태", self.controller)
        status_renderer = self.controller.split("private function renderReviewedStatus(): string", 1)[1].split(
            "private function productManagerUrl(", 1
        )[0]
        self.assertNotIn("<form", status_renderer)
        self.assertIn("$this->escape((string) $entry->rejectionReason)", status_renderer)

    def test_persisted_import_and_decision_history_is_bounded_and_read_only(self) -> None:
        batch_interface = (ROOT / "modules" / "kuraneacatalog" / "src" / "Domain" / "CatalogImportBatchRepositoryInterface.php").read_text(encoding="utf-8")
        queue_interface = (ROOT / "modules" / "kuraneacatalog" / "src" / "Domain" / "ProductReviewQueueRepositoryInterface.php").read_text(encoding="utf-8")
        batch_repository = (ROOT / "modules" / "kuraneacatalog" / "src" / "Infrastructure" / "Persistence" / "JsonFileCatalogImportBatchRepository.php").read_text(encoding="utf-8")
        persistent_queue = (ROOT / "modules" / "kuraneacatalog" / "src" / "Infrastructure" / "Persistence" / "JsonFileProductReviewQueueRepository.php").read_text(encoding="utf-8")
        in_memory_queue = (ROOT / "modules" / "kuraneacatalog" / "src" / "Domain" / "ProductReviewQueue.php").read_text(encoding="utf-8")
        history_renderer = self.controller.split("private function renderCatalogImportHistory(", 1)[1].split(
            "private function renderReviewedStatus(", 1
        )[0]

        self.assertIn("public function recent(int $limit = 20): array", batch_interface)
        self.assertIn("public function recentReviewed(int $limit = 20): array", queue_interface)
        self.assertIn("recent(int $limit = 20): array", batch_repository)
        self.assertIn("recentReviewed(int $limit = 20): array", persistent_queue)
        self.assertIn("recentReviewed(int $limit = 20): array", in_memory_queue)
        self.assertIn("$batches->recent(", history_renderer)
        self.assertIn("$queue->recentReviewed(", history_renderer)
        self.assertIn('id="catalog-import-history"', history_renderer)
        self.assertIn("catalogBatchUrl(", history_renderer)
        self.assertNotIn("canonicalUrl", history_renderer)
        self.assertIn("$this->activeBatchCanAutoAdvance", self.batch_renderer)
        self.assertIn("$this->canView()", self.controller)

    def test_import_mutations_keep_admin_token_and_capability_checks(self) -> None:
        validation = self.controller.split("private function validateImportMutation(): bool", 1)[1].split(
            "private function catalogImportService(", 1
        )[0]
        queue_renderer = self.controller.split("private function renderQueue(", 1)[1].split(
            "private function renderReviewedStatus(", 1
        )[0]
        self.assertIn("isValidImportMutationToken()", validation)
        self.assertIn("!$this->canApprove()", validation)
        self.assertIn("elseif ($this->canApprove())", queue_renderer)

    def test_import_mutations_delegate_masked_csrf_validation_to_prestashop(self) -> None:
        validator = self.controller.split("private function isValidImportMutationToken(): bool", 1)[1].split(
            "private function catalogImportService(", 1
        )[0]
        self.assertIn("\\PrestaShop\\PrestaShop\\Adapter\\SymfonyContainer::getInstance()", validator)
        self.assertIn("UserTokenManager::class", validator)
        self.assertIn("->isTokenValid()", validator)
        self.assertIn("catch (Throwable)", validator)
        self.assertNotIn("getAdminTokenLite", validator)
        self.assertNotIn("hash_equals", validator)

        harness = (ROOT / "tests" / "catalog" / "admin_review_controller.php").read_text(encoding="utf-8")
        self.assertIn("class_alias(", harness)
        self.assertIn("PrestaShop\\\\PrestaShop\\\\Adapter\\\\SymfonyContainer", harness)
        self.assertNotIn("final class SymfonyContainer", harness)

        approval = self.controller.split("private function processApproval(", 1)[1].split(
            "private function renderImportForm(", 1
        )[0]
        self.assertIn("$this->isValidImportMutationToken()", approval)
        self.assertNotIn("getAdminTokenLite", approval)

    def test_missing_csrf_service_negative_fixture_executes_a_real_approval_post(self) -> None:
        harness = (ROOT / "tests" / "catalog" / "admin_review_controller.php").read_text(encoding="utf-8")
        missing_service_case = harness.split("CatalogAdminTestSymfonyContainer::$available = false;", 1)[1].split(
            "CatalogAdminTestSymfonyContainer::$available = true;", 1
        )[0]
        self.assertIn("$_SERVER['REQUEST_METHOD'] = 'POST';", missing_service_case)
        self.assertIn("Tools::$submitted = true;", missing_service_case)
        self.assertIn("Tools::$submittedAction = 'submitKuraneaCatalogApprove';", missing_service_case)
        self.assertIn("'idempotency_key' => $missingTokenEntry->idempotencyKey", missing_service_case)
        self.assertIn("'token' => $formCsrfToken", missing_service_case)
        self.assertIn("$missingCsrfServiceController->initContent();", missing_service_case)
        self.assertIn("A missing PrestaShop CSRF service must fail closed.", missing_service_case)
        self.assertIn("A missing CSRF service must not invoke native product registration.", missing_service_case)
        self.assertIn("'pending', $catalogAdminQueue->find($missingTokenEntry->idempotencyKey)?->status", missing_service_case)

    def test_review_capabilities_use_prestashop_lazy_access_api(self) -> None:
        view = self.controller.split("private function canView(): bool", 1)[1].split(
            "private function canApprove(): bool", 1
        )[0]
        approve = self.controller.split("private function canApprove(): bool", 1)[1].split(
            "private function sourceLabel(", 1
        )[0]

        self.assertIn("return $this->viewAccess();", view)
        self.assertNotIn("tabAccess", view)
        self.assertIn("return $this->canView() && $this->access('edit') && $this->access('add');", approve)
        self.assertNotIn("tabAccess", approve)

    def test_ci_reads_catalog_review_access_for_the_same_synthetic_admin_without_identifiers(self) -> None:
        probe = (ROOT / "tests" / "catalog" / "read_catalog_import_admin_access.php").read_text(encoding="utf-8")
        for marker in (
            "getenv('ADMIN_MAIL')",
            "->getByEmail($email)",
            "employee_email_matches",
            "employee_active",
            "strtolower(trim((string) $employeeRecord->email)) === strtolower($email)",
            "AdminKuraneaCatalogReview",
            "employee_found",
            "profile_is_superadmin",
            "tab_found",
            "failure_stage",
            "exception_class",
            "profile_access_read",
            "profile_access_create",
            "profile_access_update",
            "authorization_basis",
            "ORDENOWA_CATALOG_ADMIN_ACCESS=",
            "authorization_ready",
            "$employeeFound\n        && $employeeEmailMatches\n        && $employeeActive\n        && $profileId > 0\n        && $tabFound",
            "'authorization_ready' => $authorizationReady",
            "Profile::getProfileAccess($profileId, $tabId)",
            r"WHERE slug = \'",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, probe)
        self.assertNotIn("'email' =>", probe)
        self.assertNotIn("'id_employee' =>", probe)
        self.assertNotIn("'id_profile' =>", probe)

        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.assertIn("id: catalog_import_admin_access_readback", workflow)
        self.assertIn("read_catalog_import_admin_access.php", workflow)
        self.assertIn("catalog-import-admin-access.log", workflow)
        self.assertIn("if (($result['authorization_ready'] ?? false) !== true)", probe)
        self.assertIn("CATALOG_IMPORT_ADMIN_ACCESS_READY: ${{ steps.catalog_import_admin_access_readback.outputs.authorization_ready }}", workflow)
        self.assertIn('"catalog_import_admin_access_ready=$CATALOG_IMPORT_ADMIN_ACCESS_READY"', workflow)
        self.assertIn('if [[ "$CATALOG_IMPORT_FIXTURE_OUTCOME" == success ]]; then\n            required_artifacts+=(catalog-import-admin-access.log)', workflow)
        fixture_at = workflow.index("id: catalog_import_fixture")
        readback_at = workflow.index("id: catalog_import_admin_access_readback")
        browser_at = workflow.index("id: catalog_import_browser_qa")
        restore_at = workflow.index("id: catalog_import_restore")
        self.assertLess(fixture_at, readback_at)
        self.assertLess(readback_at, browser_at)
        self.assertLess(browser_at, restore_at)

    def test_isolated_ci_without_the_run_scoped_fixture_fails_closed_before_live_fetcher(self) -> None:
        service = self.controller.split("private function catalogImportService(", 1)[1].split(
            "private function isIsolatedCatalogCi(): bool", 1
        )[0]
        self.assertIn("if ($this->isIsolatedCatalogCi() && !$this->isRunScopedCatalogFixtureMode())", service)
        self.assertLess(service.index("throw new \\RuntimeException"), service.index("new PublicProductFetcher"))

    def test_import_images_remain_local_uploads_with_rights_record(self) -> None:
        self.assertIn('name="import_product_images[]" type="file"', self.import_form)
        self.assertIn('name="image_rights_basis"', self.import_form)
        self.assertIn('name="image_rights_reference"', self.import_form)
        self.assertIn('name="confirm_image_rights" value="1"', self.import_form)
        self.assertNotIn("file_get_contents($snapshot->images", self.controller)
        self.assertIn("normalizedImportUploads()", self.draft_validation)
        self.assertIn("validateImageRightsInputs(\n            $uploads,", self.draft_validation)
        self.assertIn("$entry->linkedProductId !== null", self.draft_validation)

    def test_selected_local_upload_has_a_preview_separate_from_remote_source_metadata_and_rights(self) -> None:
        self.assertIn("public function setMedia($isNewTheme = false)", self.controller)
        self.assertIn("parent::setMedia($isNewTheme)", self.controller)
        self.assertIn("catalog-import-image-preview.js", self.controller)
        self.assertIn('data-catalog-image-preview', self.import_form)
        self.assertIn("미리보기는 업로드 예정 파일만 표시하며 사용권 승인을 대신하지 않습니다.", self.import_form)
        self.assertTrue(IMAGE_PREVIEW.is_file(), "The local upload preview script must be installed with the module.")

        script = IMAGE_PREVIEW.read_text(encoding="utf-8")
        self.assertIn("input.files", script)
        self.assertIn("URL.createObjectURL(file)", script)
        self.assertIn("URL.revokeObjectURL", script)
        self.assertIn("data-preview-items", script)
        self.assertNotIn("snapshot->images", script)
        self.assertNotIn("image->url", script)

    def test_inactive_draft_link_and_evidence_are_saved_before_queue_approval(self) -> None:
        process = self.controller.split("private function processImportedDraft(", 1)[1].split(
            "private function validateImportMutation(", 1
        )[0]
        new_draft = process.split("foreach (['name_ja', 'name_en', 'name_ko']", 1)[1]
        self.assertLess(new_draft.index("saveImportedDraftWithResult"), new_draft.index("linkDraftIfCurrent"))
        self.assertLess(new_draft.index("linkDraftIfCurrent"), new_draft.index("approveIfPending"))
        self.assertIn("imageRights", process)
        self.assertIn("importReviewEvidence", process)
        self.assertIn("비활성 초안 연결과 이미지 검수 기록은 보존", process)
        self.assertIn("Tools::getValue(\n                    'tax_evidence_reference'", process)

    def test_synthetic_image_rights_choice_is_limited_to_matching_isolated_fixture_run(self) -> None:
        self.assertIn("if ($this->isRunScopedCatalogFixtureMode())", self.import_form)
        self.assertIn('value="synthetic_ci_fixture"', self.import_form)
        self.assertIn("합성 이미지 검증 기록 · 실제 사용권 없음", self.import_form)

        fixture_guard = self.controller.split("private function isRunScopedCatalogFixtureMode(): bool", 1)[1].split(
            "private function normalizedImportUploads(", 1
        )[0]
        isolated_guard = self.controller.split("private function isIsolatedCatalogCi(): bool", 1)[1].split(
            "private function isRunScopedCatalogFixtureMode(): bool", 1
        )[0]
        for expected in ("getenv('CI') === 'true'", "getenv('GITHUB_ACTIONS') === 'true'", "getenv('KURANEA_ISOLATED_CI') === '1'"):
            with self.subTest(expected=expected):
                self.assertIn(expected, isolated_guard)
        for expected in (
            "getenv('KURANEA_CATALOG_IMPORT_FIXTURE_MODE') !== '1'",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "kuranea-ci-' . $runId . '-' . $attempt",
            "/tmp/ordenowa-ci-catalog-import-fixture-fetcher.php",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, fixture_guard)

        validator = self.controller.split("private function validateImageRightsInputs(", 1)[1].split(
            "private function isIsolatedCatalogCi(): bool", 1
        )[0]
        self.assertIn("$isSyntheticFixture && !$this->isRunScopedCatalogFixtureMode()", validator)

    def test_image_rights_inputs_are_validated_before_native_import_mutation(self) -> None:
        validation_call = "$this->validateImageRightsInputs(\n            $uploads,"
        self.assertIn(validation_call, self.draft_validation)
        self.assertLess(
            self.draft_validation.index(validation_call),
            self.draft_validation.index("saveImportedDraftWithResult("),
        )

        validator = self.controller.split("private function validateImageRightsInputs(", 1)[1].split(
            "private function isIsolatedCatalogCi(): bool", 1
        )[0]
        for expected in (
            "ProductImageRightsEvidence::MAX_IMAGE_IDS",
            "ProductImageRightsEvidence::MAX_REFERENCE_LENGTH",
            "confirm_image_rights",
            "seller_owned",
            "licensed",
            "public_domain",
            "explicit_permission",
            "ProductImageRightsEvidence::BASIS_SYNTHETIC_CI_FIXTURE",
            "$this->isRunScopedCatalogFixtureMode()",
            "preg_match('/[\\x00-\\x1f\\x7f]/'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, validator)

    def test_retry_and_linked_product_approval_require_matching_persisted_image_evidence(self) -> None:
        unlinked_review = self.draft_validation.split("foreach (['name_ja', 'name_en', 'name_ko']", 1)[1]
        self.assertIn("$imageIds = $manager->imageIds($result->productId)", unlinked_review)
        self.assertIn("$this->imageIdsMatchEvidence($imageIds, $entry->imageRightsEvidence)", unlinked_review)
        self.assertIn("기존 이미지가 사용권 검수를 받지 않아", unlinked_review)
        self.assertLess(
            unlinked_review.index("imageIdsMatchEvidence($imageIds, $entry->imageRightsEvidence)"),
            unlinked_review.index("$queue->approveIfPending("),
        )

        linked_review = self.draft_validation.split("if ($entry->linkedProductId !== null)", 1)[1].split(
            "foreach (['name_ja', 'name_en', 'name_ko']", 1
        )[0]
        self.assertIn("$uploadCount > 0", linked_review)
        self.assertIn("$this->imageIdsMatchEvidence($imageIds, $imageRights)", linked_review)
        self.assertIn("confirm_existing_image_rights", linked_review)

    def test_changed_source_drops_old_commercial_evidence_and_requires_current_revision_review(self) -> None:
        evidence = (ROOT / "modules/kuraneacatalog/src/Domain/ProductImportReviewEvidence.php").read_text()
        queue_entry = (ROOT / "modules/kuraneacatalog/src/Domain/ProductReviewQueueEntry.php").read_text()
        self.assertIn("sourceContentHash", evidence)
        self.assertIn("[a-f0-9]{64}", evidence)
        self.assertIn("must match the exact source revision", queue_entry)
        queue = (ROOT / "modules/kuraneacatalog/src/Domain/ProductReviewQueue.php").read_text()
        repository = (ROOT / "modules/kuraneacatalog/src/Infrastructure/Persistence/JsonFileProductReviewQueueRepository.php").read_text()
        self.assertIn("importReviewEvidence: null", queue + repository)
        self.assertIn("sourceContentHash !== $entry->snapshot->contentHash", self.draft_validation)

        matcher = self.controller.split("private function imageIdsMatchEvidence(", 1)[1].split(
            "private function renderQueue(", 1
        )[0]
        self.assertIn("sort($imageIds, SORT_NUMERIC)", matcher)
        self.assertIn("sort($recordedImageIds, SORT_NUMERIC)", matcher)

    def test_synthetic_fixture_guard_uses_the_domain_evidence_run_identifiers(self) -> None:
        fixture_guard = self.controller.split("private function isRunScopedCatalogFixtureMode(): bool", 1)[1].split(
            "private function validateImageRightsInputs(", 1
        )[0]
        for expected in (
            "KURANEA_CI_RUN_ID",
            "KURANEA_CI_RUN_ATTEMPT",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "$domainRunId === $runId",
            "$domainAttempt === $attempt",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, fixture_guard)


if __name__ == "__main__":
    unittest.main()
