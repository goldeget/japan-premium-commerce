# ORDENOWA remaining prelaunch execution plan

> **For agentic workers:** Execute with superpowers:subagent-driven-development. The user explicitly selected autonomous parallel execution and opted out of repeated preparation/approval questions for already-authorized prelaunch work.

**Goal:** Close remaining independently executable prelaunch defects and verify the actual release artifact, while preserving real-world acceptance boundaries.

**Architecture:** Reuse the current PrestaShop 9.2.0 procurement platform and its 39-phase acceptance. Separate catalog, admin HTTP and artifact/runtime lanes; root owns policy protection, integration, commits and final verification.

**Tech stack:** Existing PHP modules, MariaDB, Docker Compose, Python, native browser acceptance and GitHub Actions.

**Spec:** ../specs/2026-10-29-ordenowa-procurement-points-platform-design.md and ../../RELEASE_REQUIREMENTS_MATRIX.md.

## Global constraints

- Preserve main, the original checkout, user changes and existing DB/volumes. Work from the fresh clean 8c0ada0 clone on work.
- No core/parent-theme edits, production deployment/DB mutation, real order/payment, paid service or outgoing real-recipient message.
- Preserve ownership, CSRF, concurrency, privacy, aggregate and cleanup assertions. Do not fabricate operator identity, policy approval, image rights or physical-device evidence.
- Reuse approved brand/assets, Japanese description, JPY tax-inclusive and supported-region material; GPT selects source URLs.
- Run focused checks per changed lane; integrate a stable candidate before its necessary full acceptance.

## Tasks

1. **Policy placeholder defect (root).** Add a failing standalone PHP regression and actual MariaDB cases to policies behavior. Reject unresolved template markers before policy/audit writes. Treat legacy unresolved rows as unpublished while preserving administrator read/edit access. Preserve partial drafts, valid policy text and version/rollback behavior.
2. **Artifact runtime rehearsal (release agent).** Bind clean source SHA, tar byte hash and Docker config ID to an archive-loaded image. Run the unchanged fresh/restart/restore domain acceptance from that exact image without rebuilding or application hot-copy. Keep legacy source-build mode. Retain only redacted proofs and verify mismatch rejection.
3. **Authenticated admin error path (admin agent).** Reuse actual native login/browser and a strictly isolated test-only failure provider to verify native authenticated HTTP status and Korean error content. Restore all fixture overrides and preserve the direct-controller baseline. Record external normal availability separately.
4. **Live source acceptance (catalog agent).** Select explicit current Amazon/Rakuten sources, inspect actual title/JPY price/options/category/photos, and fix supported parser defects with regression evidence. Never convert unavailable/ambiguous/cache-only data into an accepted current SKU. Keep image permission/publication separate.
5. **Integration and review (root).** Review disjoint patches and exact remote head, run focused checks, commit/push work, run required integrated acceptance on the stable candidate, independently inspect outcomes/artifacts and update evidence/handoff. Record actual unresolved external acceptance without returning a generic preparation questionnaire.

## Review focus

- A policy with nonempty unresolved template markers must not become public or create a new saved/audited revision.
- A changed archive, source SHA, loaded image ID or Compose image reference must fail before deployment to disposable containers.
- Artifact-mode acceptance must not silently rebuild or replace application files with checkout hot-copies.
- Admin fixture state must not escape the exact run-owned isolated environment or convert upstream outage into a normal-availability pass.
- Live source option/price ambiguity and photo permission must remain visible rather than being inferred.

## Execution ledger

- Baseline: ae370bbb full #40800924097 passed 39 phases, aggregate and cleanup. 8c0ada0 adds docs only; no unchanged baseline test rerun is needed.
- Ruling: use a separate recursive clone after the app worktree tool rejected the F: source path. Existing F: checkout remains untouched.
- Ruling: proceed without plan/workspace confirmation because the user explicitly authorized autonomous execution and rejected repeated preparation questions.
- Policy regression: PHP 8.4.27 standalone test failed on the original nonempty-placeholder publication path, then passed after the guard. The new invalid-save cases prove zero database calls; existing unresolved rows remain readable/unpublished and ordinary single braces remain valid. Actual MariaDB append/audit checks are included in the existing policies_behavior phase and await the stable integrated candidate.
- Local test runtime: official PHP Windows 8.4.27-1 NTS x64 archive, SHA-256 dbae154a0a89791f36c3d48e68bae797878333e7d6cb5721e74617de59b63ab7, verified before extraction under the thread work/runtime directory. No system installation or PATH change. Docker Hub image retrieval failed with EOF; no proxy/CA workaround was applied.
- Windows Docker defect: the fresh checkout materialized Linux entrypoint/CI scripts with CRLF under core.autocrlf=true. Real Git checkout-index regression failed before attributes (four current entry scripts plus future script rule), then all three tests passed with '*.sh text eol=lf'; binary assets stayed byte-identical. Local shell bytes were normalized only in the isolated clone; Git confirmed no shell source-content delta.
