"""Guard the Korean catalog import review form and its safe admin actions."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "modules" / "kuraneacatalog" / "controllers" / "admin" / "AdminKuraneaCatalogReviewController.php"
PRODUCT_DRAFT = ROOT / "modules" / "kuraneacatalog" / "src" / "Domain" / "ProductAdminDraft.php"
NATIVE_MANAGER = ROOT / "modules" / "kuraneacatalog" / "src" / "Integration" / "PrestaShopNativeProductManager.php"


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

    def test_import_mutations_keep_admin_token_and_capability_checks(self) -> None:
        validation = self.controller.split("private function validateImportMutation(): bool", 1)[1].split(
            "private function catalogImportService(", 1
        )[0]
        queue_renderer = self.controller.split("private function renderQueue(", 1)[1].split(
            "private function renderReviewedStatus(", 1
        )[0]
        self.assertIn("hash_equals($expectedToken, $submittedToken)", validation)
        self.assertIn("!$this->canApprove()", validation)
        self.assertIn("elseif ($this->canApprove())", queue_renderer)

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
