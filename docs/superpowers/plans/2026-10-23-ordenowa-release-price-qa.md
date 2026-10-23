# ORDENOWA Release Price Policy QA Plan

> **For agentic workers:** Follow the existing work branch and in-flight implementation. This plan records integration and verification work; it does not authorize production deployment, real transactions, paid services, destructive cleanup, or changes to `main`.

**Goal:** Verify in an isolated GitHub Actions shop that customer-facing sale prices reconcile through cart, checkout, order history, and admin, while supported Japanese destinations always receive ¥0 shipping and taxable products retain truthful configured tax.

**Architecture:** Keep code analysis and lightweight contracts in Codex Cloud. Run PrestaShop, MariaDB, and Chromium only in run-scoped GitHub Actions Compose projects. Use synthetic CI-only tax rules to verify included tax arithmetic without asserting a legal Japanese rate; use no-rule fixtures only to test explicitly unassigned tax behavior.

**Tech Stack:** PrestaShop 9.2, PHP, Python unittest, Docker Compose in GitHub Actions, Selenium Chromium, MariaDB.

**Spec:** User's ORDENOWA release price policy and preceding in-flight final development QA request in conversation.

**Current checkpoint:** The code and workflow baseline is `29766718481a2c594ab7aa7896bb563de784c856` on `work`; the new QA changes correct the Osaka fixture shape, add field-level synthetic-order diagnostics, reconcile amounts on the order-confirmation screen, and keep independent browser suites running after postcode fixture failures. Full isolated fresh-install run `39940305885` failed at postcode import; its independent tax fixture also failed to reconcile. Browser and free-shipping steps were skipped in that run. This run does not establish browser price-policy behavior. Keep runtime tasks open until a corrected Actions run passes.

## Global Constraints

- Work only on `work`; preserve `main`, prior feature work, brand originals, and untracked user data.
- Do not mutate production databases, activate real payment, deploy, add paid services, or build PrestaShop Docker images in Codex Cloud.
- Shipping remains ¥0 for supported Japanese regions across quantities and coupons.
- Do not label an unassigned tax group as a legal exemption or record actual tax as zero.
- Do not claim CI/browser behavior passed without fresh GitHub Actions evidence.

## Review Focus

- A configured taxable product must show tax-included sale price consistently at product, cart, checkout, order history, and admin.
- Free-shipping carrier configuration must be restricted to the Japan-only QA zone and survive a fresh admin readback.
- Quantity, Tokyo/Osaka address, and coupon variation must not introduce shipping charges.
- CI fixtures and browser scripts must reject non-isolated or external shop endpoints before writing or sending credentials.
- Workflow aggregate status and uploaded screenshots/logs must include every newly wired test.

---

## Task 1: Isolated price and tax fixtures

**Files:** `tests/catalog/verify_product_tax_price.php`, `tests/catalog/setup_ci_variant_product.php`, `tests/smoke/test_product_tax_rules_contract.py`, `tests/smoke/test_variant_fixture_contract.py`

- [ ] Validate run-scoped synthetic tax arithmetic and unpaid native order persistence; restore changed shop config even on failure. Run `39940305885` found an order mismatch; rerun with field-level diagnostics before choosing a correction.
- [ ] Validate explicit combination selection, stock, and gross/net price fixture contracts.

## Task 2: Free-shipping browser and native order QA

**Files:** `tests/postcode/prepare_ci_japan_shipping_zone.php`, `tests/postcode/seed_ci_shipping_coupon.php`, `tests/postcode/verify_ci_free_shipping_order.php`, `tests/e2e/verify_ci_free_shipping_browser.py`, `tests/smoke/test_free_shipping_e2e_contract.py`

- [ ] Create or reuse only a run-scoped Japan-only shipping zone and coupon fixtures.
- [ ] Verify Tokyo/Osaka, mobile/desktop, quantities, coupon, persisted order totals, and admin readback with ¥0 shipping.

## Task 3: Wire CI browser evidence

**Files:** `.github/workflows/fresh-install.yml`, `tests/e2e/verify_cart_controls_browser.py`, existing product/customer browser scripts

- [ ] Run tax and variant fixtures, export their IDs, and execute product, variant/cart, taxable-price, customer, and free-shipping browser paths in isolated Compose.
- [ ] Preserve unpaid-only checkout; aggregate all outcomes and upload screenshots/logs.

## Task 4: Preserve and verify in-flight account, brand, security, PWA, and SEO work

**Files:** existing account/brand/security/PWA browser tests, smoke contracts, and workflow paths

- [x] Verify each browser script guards the isolated run and loopback endpoints before writes or credentials.
- [x] Keep approved ORDENOWA assets intact and run the corresponding contracts.

## Task 5: Verify, document, commit, and push

**Files:** `docs/DEVELOPMENT_STATUS.md`, `docs/WORK_LOG.md`, `docs/TEST_RESULTS.md`

- [x] Run focused and full offline contracts, static syntax checks, and diff checks.
- [x] Commit independent verified features and push each to `work`; confirm remote SHA after each push.
- [ ] Run the GitHub Actions Docker/browser suite and report actual results and artifacts; latest run `39940305885` failed before browser QA. Leave production and real payments disabled.
