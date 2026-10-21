# KURANEA Phase 0: PrestaShop and Hummingbird Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a reproducible PrestaShop 9.2.0 development shop with the official Hummingbird 2.1.2 parent theme and a KURANEA child theme.

**Architecture:** Run the official PrestaShop image with a persistent MariaDB service in Compose. Pin the official Hummingbird source to its verified `v2.1.2` commit and add a KURANEA child theme; keep application changes in the child theme and independent modules, with no PrestaShop core edits. Official brand-image processing and the PWA module follow as separate stages.

**Tech Stack:** PrestaShop 9.2.0, official `prestashop/prestashop:9.2.0` image, MariaDB 10.11, Docker Compose, Hummingbird 2.1.2, Node 24/npm 11 for upstream theme builds.

**Spec:** `docs/PROJECT_ARCHITECTURE.md`, `docs/KURANEA_MASTER_DEVELOPMENT_DIRECTIVE.md`, and `docs/ADMIN_KOREAN_REQUIREMENTS.md`.

## Global Constraints

- Work only on `work`; preserve the initial `main` branch.
- Use official PrestaShop 9.2.0 tag SHA `84db6bd3a3c1612535b15b9df934afd609085423`.
- Use official Hummingbird `v2.1.2` tag SHA `4e52b64d3c772f19d9974409b73d55fb532e9e22`.
- Do not edit PrestaShop core files or generate a replacement brand logo.
- Keep database data in a persistent named volume; do not set `PS_ERASE_DB=1`.
- Keep credentials in ignored local `.env`; commit only placeholders in `.env.example`.
- Keep the customer shop in Japanese by default; English and Korean are required additional languages, and Back Office acceptance remains Korean 100%.
- After each task, run its checks, commit, push to `work`, and confirm remote SHA and files.

## Review Focus

- **Language-pack download:** PrestaShop's installer must fetch its selected language pack over verified HTTPS from `i18n.prestashop-project.org`; no TLS bypass is allowed. Test: complete auto-install with the configured proxy and verify the shop default language is Japanese.
- **Shop URL:** Auto-install must persist `localhost:8080` so requests through the host port do not redirect to a container address. Test: fetch the homepage and confirm its canonical URL/redirect stays on `localhost:8080`.
- **Persistent database:** Restarting the stack must preserve the installed shop. Test: restart the services and confirm the same shop can load and the database volume remains attached.
- **Theme pin:** Hummingbird must resolve to the verified `v2.1.2` commit. Test: check `git submodule status` against the recorded SHA and validate `config/theme.yml` reports 2.1.2.
- **Child-theme boundary:** KURANEA changes must inherit Hummingbird and leave upstream files untouched. Test: validate the child `parent` value and compare the Hummingbird submodule working tree before and after theme checks.

---

### Task 1: Reproducible local PrestaShop runtime

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `docs/LOCAL_DEVELOPMENT.md`

**Interfaces:**
- Compose services: `shop` uses `prestashop/prestashop:9.2.0`, `db` uses MariaDB `10.11`.
- `.env.example` defines non-secret local defaults for `DB_NAME`, `DB_USER`, `DB_PASSWD`, `MARIADB_ROOT_PASSWORD`, `ADMIN_MAIL`, and `ADMIN_PASSWD`.
- Compose must set `PS_INSTALL_AUTO=1`, `PS_LANGUAGE=ja`, `PS_DOMAIN=localhost:8080`, and `PS_ERASE_DB=0`; expose host port `8080` and use persistent database and shop volumes.

- [ ] Create Compose services with a MariaDB health check and `shop` dependency on `db` health.
- [ ] Keep `.env` and generated runtime data ignored; document copying `.env.example` to `.env`.
- [ ] Run `docker compose config --quiet`; expected: exit 0 with no rendered secrets.
- [ ] Run `docker compose pull` and `docker compose up -d --wait`; expected: `db` healthy and `shop` running.
- [ ] Run `curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:8080/`; expected: HTTP 200 after auto-install.
- [ ] Restart with `docker compose restart` and repeat the HTTP check; expected: same installed shop remains available.
- [ ] Commit the runtime, push `work`, then verify the remote SHA and `compose.yaml` contents.

### Task 2: Pin Hummingbird and create the child-theme shell

**Files:**
- Create: `.gitmodules`
- Add submodule: `themes/hummingbird` at Hummingbird `v2.1.2` SHA `4e52b64d3c772f19d9974409b73d55fb532e9e22`
- Create: `themes/kuranea/config/theme.yml`
- Create: `themes/kuranea/assets/css/theme.css`
- Create: `docs/THEME_DEVELOPMENT.md`

**Interfaces:**
- `themes/kuranea/config/theme.yml` sets `parent: hummingbird`, name `kuranea`, display name `KURANEA`, and child-theme compatibility `~9.2.0`.
- `themes/kuranea/assets/css/theme.css` contains only KURANEA overrides; upstream theme assets remain in the submodule.

- [ ] Add the official Hummingbird remote as a submodule and check out the exact verified tag commit.
- [ ] Add the minimal child-theme manifest and stylesheet; do not add placeholder logos.
- [ ] Validate the child manifest YAML and assert its top-level `parent` value is `hummingbird` and Hummingbird SHA matches the spec.
- [ ] Run the official Hummingbird `npm ci`, `npm test`, and `npm run build` using Node 24 and npm 11; expected: Jest tests and production asset build complete successfully.
- [ ] Confirm PrestaShop lists and activates the child theme, then request the storefront homepage; expected: HTTP 200 and child-theme CSS is served.
- [ ] Commit the submodule pin and child theme, push `work`, then compare remote SHA and submodule entry.

### Task 3: Save and exercise reusable cloud startup instructions

**Files:**
- Update: cloud environment `start_skill` with the exact checkout path, Compose startup command, and HTTP readiness check.
- Update: cloud environment `install_script` only if a missing reproducible tool or dependency is demonstrated.

**Interfaces:**
- Start command: `docker compose up -d --wait` from `/workspace/japan-premium-commerce`.
- Readiness command: HTTP request to `http://127.0.0.1:8080/`; report service logs from `docker compose logs --tail=100 shop db` on failure.

- [ ] Exercise the startup command and HTTP check in the current cloud machine.
- [ ] Read the current environment draft, preserve unrelated settings, and save complete tested startup instructions.
- [ ] Verify the saved draft reports success; distinguish the saved draft from publication and current runtime state.

### Task 4: First storefront verification

**Files:**
- Create: `tests/smoke/test_storefront.py`
- Create: `docs/QA_BOOTSTRAP.md`

**Interfaces:**
- Smoke test base URL: `http://127.0.0.1:8080`.
- Test assertions: homepage is HTTP 200, `lang="ja"` is present, and the active theme is `kuranea`.

- [ ] Add the smoke test with assertions for HTTP 200, `lang="ja"`, and a response asset path under `/themes/kuranea/`.
- [ ] Run the test against the live Compose stack; expected: all assertions pass.
- [ ] Save results and screenshot only after the browser renders the page at desktop and mobile widths.
- [ ] Commit the test and QA note, push `work`, and verify the remote SHA and test file.

## Out of scope for this bootstrap plan

The official logo derivatives, manifest/service-worker implementation, email and Back Office logo hooks, full Korean Back Office translation coverage, and cross-device PWA browser QA are follow-up plans. They must use the supplied official binary logo assets and be validated against a running shop before completion.
