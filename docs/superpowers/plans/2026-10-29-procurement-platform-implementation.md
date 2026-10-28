# ORDENOWA Procurement Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver assigned-product requests, manual reviews, manual points, and parsed-product integration with verified customer ownership and durable readback.

**Architecture:** One PrestaShop module `ordenowaprocurement`, native identity/product adapters, dedicated transactional MariaDB domain tables. Keep legacy commerce closed and preserve existing data. Six agents own disjoint subsystems; root integrates/reviews and manages commits/CI.

**Tech Stack:** PrestaShop9.2/PHP8.3, Hummingbird child theme, MariaDB10.11, isolated Actions, Python/Selenium.

**Spec:** `docs/superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md`

## Global Constraints

No core/parent edits, no production DB/volumes/deployment/payment/trade/paid services. Work fast-forward only. Customer JA/EN/KO, native admin KO. No shipping/payment requirements. Points explicit manual approval then award; no automatic rewards, cash conversion, withdrawals. Latest user explicitly adds complete product parsing as release scope: preserve allowed source/rights and distinguish synthetic vs approved real samples. Existing parser/fetcher reused, never fabricate source data or bypass access blocks.

## Review Focus

- A/B ownership on every detail, mutation, image and point endpoint; denied request preserves session and owner data.
- Stale/revoked/expired assignment and product-option/shop mismatch cannot submit.
- Different idempotency keys and simultaneous employees cannot double-award one request.
- Ledger/account/audit/outbox partial writes rollback and customer relogin/restart agrees with ledger sum.
- Parser missing/hostile/multi-variant source data and blocked pages fail accurately; native private product stays non-orderable.

## Shared interfaces (fixed integration contract)

Namespace `Ordenowa\Procurement`, module root `modules/ordenowaprocurement`.

- `Infrastructure\Database(object $connection, string $prefix)` wraps native Db or PDO; `table(string $suffix):string`, `quote(string):string`, `execute(string):void`, `all(string):array`, `one(string):?array`, `value(string):mixed`, `insertId():int`, `transaction(callable):mixed`. Native read uses executeS with cache disabled; no getRow implicit LIMIT. Caller SQL controls locking/limit order.
- `Infrastructure\Schema::install(Database):void`; suffixes assignment, request, review, point_account, point_award, point_ledger, activity, notification. Additive InnoDB, unique assignment->request and request->base award, append records, idempotency payload hashes.
- `Security\Actor::customer(int $shop,int $customer):Actor`, `Actor::employee(int $shop,int $employee,array $permissions):Actor`; public shopId/id/type; `require(string):void`; employee permissions procurement.read/manage/review, points.read/award/correct, audit.read. Only trusted Runtime creates actors from native sessions/access.
- `Requests\RequestService(Database)`: `createAssignment(Actor,int $customerId,array $trustedProduct,array $input):array`, `revokeAssignment(Actor,int $id,int $version,string $reason):array`, `customerAssignments(Actor):array`, `assignment(Actor,int $id):array`, `submit(Actor,int $id,int $version,int $quantity,string $key):array`, `customerRequests(Actor):array`, `adminRequests(Actor):array`, `request(Actor,int $id):array`, `review(Actor,int $id,int $version,string $decision,string $reason):array`.
- Assignment input default_quantity/max_quantity/instructions/deadline nullable. Product adapter snapshot: shop_id, id_product, id_product_attribute, names[ja/en/ko], descriptions[ja/en/ko], image_url approved public only or '', reference, source_url provenance or ''. No client snapshots accepted. Returned assignment includes id_assignment/customer/product snapshot/default_quantity/max_quantity/instructions/deadline/status/version. Request includes id_request/id_assignment/id_customer/product snapshot/quantity/status/version; review final decisions APPROVED/REJECTED/CANCELLED.
- `Infrastructure\Recorder(Database)::audit(Actor,string $action,string $type,int $id,array $safe=[]):void`, `notify(int $shop,int $customer,string $event,string $targetType,int $targetId):void`; both on caller transaction.
- `Points\PointService(Database)`: `award(Actor,int $requestId,int $amount,string $reason,string $key):array`, `correct(Actor,int $awardId,int $delta,string $reason,string $key):array`, `account(Actor,?int $customerId=null):array`, `ledger(Actor,?int $customerId=null):array`, `awards(Actor):array`, `reconcile(Actor,?int $customerId=null):array`. No external settlement state/deduction.
- `Integration\Runtime::database():Database`, `requests():RequestService`, `points():PointService`, `customerActor():Actor`, `employeeActor():Actor`, `productReference(int $productId,int $attributeId=0):array`; adapters validate same shop/native customer/product/variant.
- Module front `workspace` controller handles customer GET and named POST submit action, token getToken(false), login session, same-origin links/private no-store/noindex. Module link `getModuleLink('ordenowaprocurement','workspace', params)`.
- Admin tabs: AdminOrdenowaProcurement(manage), AdminOrdenowaProcurementReviews(review), AdminOrdenowaProcurementPoints(award ADD/correct EDIT), AdminOrdenowaProcurementAudit(READ). Preserve native token + native permissions and action-specific Actor permissions.

## Task 1 — Assignments/requests/reviews and shared persistence
Files owned: src/Infrastructure/{Database,Schema,Recorder}.php, src/Security/Actor.php, src/Requests/**, tests/procurement/requests*.php and supporting PHP test bootstrap.
- [x] Write real behavioral tests for ownership, quantity/version/revoke/expiry, immutable snapshot, unique submit, final review and audit/outbox rollback.
- [x] Implement shared interfaces and dedicated indexed schema. Communicate concrete fields/any necessary signature corrections to peers immediately.
- [x] Run PHP syntax and isolated DB tests, report actual results, no production target.

## Task 2 — Points
Files owned: src/Points/**, tests/procurement/points*.php.
- [x] Test approved-only manual award, different/same-key duplicates, concurrent award, correction limits, integer overflow, A/B isolation, rollback and sum readback.
- [x] Implement PointService against shared Database/Schema. Request unique anchor, request->account lock order; base/correction hashes; ledger/account/audit/notification atomic.
- [x] Test against isolated MariaDB/PHP, report results and no cash semantics.

## Task 3 — Customer UI
Files owned: controllers/front/**, views/templates/front/**, views/css/**, views/js/**, src/Presentation/**.
- [x] Implement assigned product cards/detail/quantity/confirmation, requests, points and notification history with JA/EN/KO.
- [x] Use Runtime/RequestService/PointService contracts; native session/token and no-store/noindex; no raw product/recipient/point inputs trusted.
- [x] Verify escaping, customer isolation and mobile/keyboard interaction with relevant checks (actual Smarty/native A-B GET+POST; 10-width/keyboard and bounded independent visuals).

## Task 4 — Module/native integration/admin
Files owned: ordenowaprocurement.php, autoload.php, src/Integration/**, controllers/admin/**, docker install wiring, compose mode config, scoped businessprofile gate changes.
- [x] Module install schema/tabs/permissions, Runtime actors/native product snapshots and module settings.
- [x] Korean admin assignment, review, points award/correction/audit with native CSRF/ACL; safe rendering and fresh reads.
- [x] Decouple member/work entry from seller validation without enabling retail; hide/deny old checkout/address/bank/returns route and link new workspace in child theme via owned narrowly scoped integration.
- [x] Preserve legacy mode and existing data; explicit platform mode; actual owned disposable native boundary test plus offline legacy preflight. Historical full retail QA remains separate.

## Task 5 — Parsing
Files owned: modules/kuraneacatalog parser/fetch integration and tests/catalog/**, relevant parser browser locale drift correction; dedicated procurement parser adapter may live src/Catalog/**.
- [x] Audit existing AmazonJapan/Rakuten structured/HTML variants; meaningful fixtures for supported prices/options/images/descriptions, missing/hostile/blocked/locale cases.
- [x] Fix observed parser or catalog verification defects, preserve safety bounds/provenance/rights; do not manufacture values.
- [x] Connect reviewed native inactive products as trusted procurement references; no customer retail flags required.
- [ ] Record source support matrix and actual approved source evidence; real sample limitations remain explicit.

## Task 6 — New CI/runtime acceptance
Files owned: .github/workflows/procurement-platform.yml, tests/procurement/CI seed/runtime/browser files, backup smoke extension as isolated new scripts. No legacy workflow assertion weakening.
- [ ] Run behavioral DB tests and fresh install+module/runtime browser flow with exact run synthetic identity.
- [x] Local focused evidence: admin assign A, B GET/POST deny with identity+owner preservation, A confirm/submit, admin review0P then explicit100P, relogin100P, correction-20P/80P; domain rejected/unapproved/revoked tests and actual retail boundary. Immutable fresh execution remains unchecked above.
- [ ] Concurrency/rollback/restart/new-domain restore checks; parser/native reference connection; redacted artifacts and actual outcome aggregate/cleanup.
- [x] Add new workflow push scope only relevant files, reuse free installed runner tools; no duplicate full acceptance.


## Execution evidence checkpoint — 2026-10-29 KST

Committed checkpoints: `887b256` domain, `d994c99` parser/provider, `100e8b7` native/UI, `a9fe3a0` atomic native ACL, `0236afc` strict masked POST CSRF/status, `bd1ced8` full CI harness, `bc4769c` Korean native CAS, `e7513c4` bounded Twig warmup, `cc99bbb` accessible language selector, `6f9c301` portable hosted build configuration, `1aca9e9` native account routes, `ad51cff` awaited native form POST + expanded admin KO/13CAS/scoped copy-language labels.

Checked boxes mean their stated focused scope. Actual local native core/3-language account+Mailpit, restart+independent restored DB, official ACL six audited edits, source1140/vendor1426 alignment, default512M warmup, quality3 (84 layout/axe +14 Lighthouse) and independent120 safe images have passed. Local image bd1ced8 plus verified later source overlays is distinct from an immutable fresh candidate. Three hosted attempts failed before Dockerfile/app execution; actual Bake entitlement cause fixed6f9c301. Two subsequent runs passed28phases but failed native browser entry/save synchronization; native routes and old-form replacement waits fix those confirmed causes. Expanded69menu-node audit led to69KO translations/13CAS/scoped native raw labels, with19affected native checks passing. Current source cheap24groups/nativeforms62/CAS33/locale60/audit13/CI9 pass. ad51cff full #40755121454 passed3 phases then failed exact13Tab bootstrap metadata; class/cause missing from original logs. Original assertions remain unchanged while8663e96/#40756263392 collects bounded13-class status evidence (app unchanged), in progress. See TEST_RESULTS and durable evidence README; never infer full PASS from local results.

Real marketplace original pages are blocked at managed CONNECT403. Remote image URL collection is distinct from rights-reviewed native image publication. Original-source compatibility/rights and approved operational inputs/physical-device checks remain open; synthetic fixtures do not close them. No production action is authorized or performed.

## Integration and release
- [x] Root reviews interfaces/diffs, source lint and focused behavioral tests; observed source defects repaired with focused evidence. Final fresh gate remains open.
- [x] Preserve work in cohesive commits, verify remote SHA; run one candidate CI at a time after focused preflight. Exact current run8663e96/#40756263392 remains in progress; ad51cff seed failure retained.
- [ ] Fix first runtime failures via focused evidence; never assertion bypass/timeout-only fix.
- [ ] Update architecture/matrix/status/tests/handoff with actual SHA/outcomes/artifacts, parsing supported boundaries, external operational inputs. Do not claim live production release absent approved environment and completed acceptance.
