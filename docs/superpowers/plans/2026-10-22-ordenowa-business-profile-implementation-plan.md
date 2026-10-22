# ORDENOWA Business Profile Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Korean PrestaShop module that versions and publishes all ORDENOWA brand and operation settings from one source, with guarded customer-facing integrations.

**Architecture:** Add the `kuraneabusinessprofile` module without modifying PrestaShop core. Store immutable JSON profile versions in module-owned tables, keep draft/published pointers per shop, and read customer output through one locale-aware provider. Keep LOGISTEED reference information separate from the seller profile and keep production selling disabled until the relationship and seller data are explicitly approved.

**Tech Stack:** PrestaShop 9.2.0 module PHP, MariaDB 10.11, PrestaShop legacy admin controllers/tabs, Smarty hooks, PHP 8.3 tests, Docker Compose isolated CI.

**Spec:** `docs/superpowers/specs/2026-10-22-business-profile-admin-control-design.md`

## Global Constraints

- Work only on `work`; preserve `main`, existing local changes, database data, and named volumes.
- Do not modify PrestaShop core or the Hummingbird parent theme.
- The confirmed customer brand is `ORDENOWA`, `オーデノワ`, `오데노와`.
- Use the confirmed description `法人向け商品調達・受発注サービス` and slogan `企業と商品をつなぐ、次世代のB2B調達プラットフォーム`.
- Keep KURANEA images and history as legacy assets; do not reuse or create ORDENOWA logos while the attached official ZIP is unavailable.
- Keep LOGISTEED company reference data separate from the seller profile; production commerce and official seller claims stay disabled while approval is pending.
- Customer locales are ja-JP, en-US, and ko-KR; all new module UI and validation errors are Korean.
- Never persist real account secrets, customer data, or production credentials in GitHub, fixtures, or CI logs.
- Each task ends with a test, a small commit, push to `work`, remote SHA comparison, and remote file readback.

## Review Focus

- Malformed or missing profile JSON must fail closed and leave the currently published pointer unchanged.
- A normal admin must not read or restore bank account values; rendered history masks sensitive fields.
- An incomplete or unapproved seller profile must not be published or enable checkout.
- A preview must not mutate the published version, be indexed, or become visible to anonymous users.
- Missing/unreadable official image ZIP must leave ORDENOWA image slots empty and must not fall back to KURANEA assets.

---

### Task 1: Profile defaults, validation, and immutable version storage

**Files:**
- Create: `modules/kuraneabusinessprofile/autoload.php`
- Create: `modules/kuraneabusinessprofile/src/Domain/ProfileDefaults.php`
- Create: `modules/kuraneabusinessprofile/src/Domain/ProfileValidator.php`
- Create: `modules/kuraneabusinessprofile/src/Domain/ProfileVersion.php`
- Create: `modules/kuraneabusinessprofile/src/Infrastructure/DatabaseSchema.php`
- Create: `modules/kuraneabusinessprofile/src/Infrastructure/VersionedProfileRepository.php`
- Create: `tests/business_profile/run.php`

**Interfaces:**
- Produces `ProfileDefaults::initial(): array`, `ProfileValidator::validateDraft(array $profile): array`, `ProfileValidator::validateForPublish(array $profile): array`, and repository methods `loadDraft(int $shopId): ?array`, `loadPublished(int $shopId): ?array`, `saveDraft(int $shopId, array $profile, int $employeeId): int`, `publish(int $shopId, int $versionId, int $employeeId): bool`, `restoreAsDraft(int $shopId, int $versionId, int $employeeId): int`, and `history(int $shopId): array`.
- Initial defaults contain ORDENOWA names/description/slogan and user-provided LOGISTEED company reference values. Seller identity, customer support, bank details, policies, images, and approval remain empty/pending.

- [ ] Write `test_initial_profile_separates_brand_company_reference_and_pending_seller` asserting exact ORDENOWA values, LOGISTEED reference values, empty seller-specific contact/account fields, pending approval, and no KURANEA image paths.
- [ ] Write `test_profile_versions_restore_without_overwriting_history` asserting saved versions are immutable and restore creates a new draft.
- [ ] Write `test_unapproved_or_incomplete_profile_cannot_publish` asserting publish validation reports Korean errors and the published pointer does not change.
- [ ] Run: `docker run --rm -v "$PWD:/src" -w /src php:8.3-cli php tests/business_profile/run.php`
- [ ] Expected: tests fail because the profile module classes do not exist.
- [ ] Implement the minimal domain and idempotent schema/repository methods; uninstall must preserve tables and rows.
- [ ] Run: `docker run --rm -v "$PWD:/src" -w /src php:8.3-cli php tests/business_profile/run.php`
- [ ] Expected: all domain/version assertions pass.
- [ ] Commit only Task 1 module and test files; push and verify the remote SHA and file contents.

### Task 2: Korean Back Office settings and access control

**Files:**
- Create: `modules/kuraneabusinessprofile/kuraneabusinessprofile.php`
- Create: `modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileController.php`
- Create: `modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileBanksController.php`
- Create: `modules/kuraneabusinessprofile/views/templates/admin/configure.tpl`
- Create: `modules/kuraneabusinessprofile/translations/ko.php`
- Modify: `tests/business_profile/run.php`

**Interfaces:**
- The module installs tabs `AdminBusinessProfile` and `AdminBusinessProfileBanks` with Korean names `쇼핑몰 운영 설정` and `은행 계좌`; the second tab is the only UI that returns unmasked bank fields.
- General profile edit, bank edit, publish, history, and restore actions must each check the current employee's tab permissions and PrestaShop admin token before changing data.

- [ ] Add failing tests `test_admin_tabs_are_korean_and_module_preserves_profile_data_on_uninstall` and `test_bank_fields_are_not_rendered_by_general_settings_controller`.
- [ ] Run the Task 1 PHP suite and confirm the two new assertions fail for the missing module/controller contracts.
- [ ] Implement the two admin tabs with Korean section navigation and structured fields for brand, company reference, seller, support, payment, shipping, refunds, terms, privacy, specified-commercial-act display, locales, SEO, and PWA.
- [ ] Add focused module controller tests for permission/token guards and ensure ordinary history output masks bank values.
- [ ] Run the PHP suite and PHP lint for all module files; expected all checks pass.
- [ ] Commit, push, compare remote SHA, and read the module entry/controller from remote `work`.

### Task 3: Draft, preview, publish, audit history, and restore

**Files:**
- Modify: `modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileController.php`
- Create: `modules/kuraneabusinessprofile/controllers/front/preview.php`
- Create: `modules/kuraneabusinessprofile/src/Domain/ProfileChangeSet.php`
- Modify: `tests/business_profile/run.php`

**Interfaces:**
- Admin operations are `saveDraft`, `preview`, `publish`, `history`, and `restoreAsDraft`; publish validates seller authorization and required policy/locales/assets before atomically swapping the published pointer.
- Preview is employee-authenticated, `noindex`, locale-specific, and does not change the public provider.
- Audit entries carry editor/publisher, timestamps, version IDs, and a field-level change set with sensitive values redacted unless the employee has bank-tab access.

- [ ] Add failing tests for save → preview → publish, anonymous preview denial, locale-specific output, field-level history, redaction, and restore to a new draft.
- [ ] Run the PHP suite and confirm the lifecycle tests fail before implementation.
- [ ] Implement controller actions and repository transactions; write tests proving a failed publish leaves the current published version active.
- [ ] Run the PHP suite and module lint; expected all lifecycle and permission tests pass.
- [ ] Commit, push, verify SHA, and read back the controller and repository.

### Task 4: Versioned official media upload and recovery

**Files:**
- Create: `modules/kuraneabusinessprofile/src/Domain/BrandAssetValidator.php`
- Create: `modules/kuraneabusinessprofile/src/Infrastructure/BrandAssetStorage.php`
- Create: `modules/kuraneabusinessprofile/views/templates/admin/brand-assets.tpl`
- Modify: `tests/business_profile/run.php`

**Interfaces:**
- Validate PNG/JPEG/WebP by byte size, decoded MIME, dimensions, and successful image decoding; reject SVG and executable formats.
- Store immutable source files and versioned public derivatives, retain KURANEA legacy originals, and let restore reconnect the prior asset set.
- When GD/Imagick is unavailable, reject derivative generation with a Korean error and retain the current published asset set.

- [ ] Add failing tests for MIME mismatch, over-size, invalid image bytes, dimension bounds, stable source preservation, and restore selecting an earlier asset version.
- [ ] Run the PHP suite and confirm new asset tests fail before implementation.
- [ ] Implement upload validation, preview metadata, versioned storage, and deterministic non-distorting resized derivatives; never create substitutes from KURANEA files.
- [ ] Run the PHP suite and lint. With ORDENOWA ZIP unavailable, verify image upload flow using explicitly synthetic test-only fixtures and leave official image application BLOCKED.
- [ ] Commit, push, verify SHA, and read back asset validator/storage.

### Task 5: Customer-facing profile provider and safety gate

**Files:**
- Create: `modules/kuraneabusinessprofile/src/Domain/PublishedProfileProvider.php`
- Create: `modules/kuraneabusinessprofile/controllers/front/manifest.php`
- Create: `modules/kuraneabusinessprofile/controllers/front/information.php`
- Modify: `modules/kuraneabusinessprofile/kuraneabusinessprofile.php`
- Modify: `themes/kuranea/templates/_partials/head.tpl`
- Modify: `themes/kuranea/templates/_partials/header.tpl`
- Modify: `themes/kuranea/templates/_partials/footer.tpl`
- Modify: `tests/business_profile/run.php`

**Interfaces:**
- `PublishedProfileProvider::forLocale(string $locale, int $shopId): ?array` returns only the active published version with a deterministic ja/en/ko locale fallback.
- Hook output for meta/title, header/footer, legal/policy pages, and email variables reads the same provider; customer output never reads draft state.
- `SalesAvailability::isEnabled(string $environment, array $profile): bool` returns false in production while seller authorization is pending, regardless of the presence of a draft/published brand record.
- PWA manifest uses only uploaded ORDENOWA assets. If absent, use no legacy icon and do not claim an installation-ready branded app.

- [ ] Add failing tests for locale fallback, draft isolation, shared storefront/mail values, anonymous access to published-only pages, and production checkout denial while approval is pending.
- [ ] Run the PHP suite and confirm the provider/integration tests fail before implementation.
- [ ] Implement front hooks/routes, SEO and email variable adapter, legal information rendering, dynamic manifest, and production safety gate without changing PrestaShop core.
- [ ] Run PHP tests and existing theme/storefront smoke tests; expected all pass and KURANEA brand references disappear from active ORDENOWA output without deleting legacy assets.
- [ ] Commit, push, verify SHA, and read back provider and theme integration.

### Task 6: Isolated PrestaShop E2E and CI persistence verification

**Files:**
- Create: `.github/workflows/business-profile.yml`
- Create: `tests/business_profile/verify_module_e2e.php`
- Create: `tests/business_profile/verify_profile_persistence.sh`
- Modify: `tests/business_profile/run.php`

**Interfaces:**
- CI uses a unique Compose project name and disposable credentials, never the developer's default `kuranea` project or existing named volumes.
- E2E installs the module, updates a TEST-only profile through the admin controller, verifies ja/en/ko customer HTML/manifest/email variables, checks publish denial without seller approval, confirms history/restore and DB persistence after restart.
- The run summary records tested surfaces and marks ORDENOWA logo/PWA visual checks blocked until the official ZIP is available.

- [ ] Add a workflow contract test for isolated project names and no volume deletion against the default project.
- [ ] Run the workflow contract and confirm it fails before the new workflow exists.
- [ ] Implement CI with separate services/volumes, module install and HTTP/DB assertions; do not execute any real payment.
- [ ] Run the local PHP contract suite and workflow contract; then trigger the isolated CI and record only observed results.
- [ ] Commit, push, verify remote SHA and read back the workflow; retain CI run URL/result in `docs/TEST_RESULTS.md`.

## Completion Notes

The attached ORDENOWA official image archive is currently inaccessible in the execution workspace. Its image replacement and browser/PWA icon QA remain blocked until the user-provided source bytes are available; no replacement logo may be generated. Live seller authorization, production payment/sales, real bank details, and real customer data remain out of scope.
