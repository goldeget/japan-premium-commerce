# Release automation evidence — 2026-10-29

The user authorized GPT to complete prelaunch implementation and tests autonomously, select marketplace URLs itself, and use parallel agents. Actual production deployment/DB changes, paid services and real transactions remain outside this authorization.

## Candidate identity and scope

Application/QA candidate: `ae370bbb3a8aab98e3da7f33419b843618c5e508`.
Archive protocol/source candidate: `7de7538a2242a1fd9dc7595208718384f2637e29`.
GitHub comparison confirmed that the only changed file between these two commits is the native MBO QA fixture (exception arguments, admin path and native request/legacy context initialization). They are still separate source identities and are not represented as one immutable promotion artifact.

The local F: checkout was left at its existing commit. GitHub connector operations updated only remote work with expected-head leases. Main remains `ee02a3657448d563508687614a246e05ac61eecd`.

## Automated archive preparation

[Run 40798367714](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798367714) succeeded on 7de7538. It ran 16 protocol tests and a real Docker build, image-ID export, archive/config digest inspection, removal of only the newly built source tag, load without rebuilding, loaded image-ID/label inspection, and offline release-manifest validation.

Proof ZIP [12864368687](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798367714/artifacts/12864368687) was downloaded and its SHA-256 verified as `068f722afdde1ecec51a68f8fd159d3756447c3f47d7ca4fa688b7229183df93`. It contains only two JSON records. They report archive SHA-256 `ae8f8f2a1bf3d430a8c53dde36a109f4e8836cfa1616240f3f9c99fb2b0327fd` and Docker config/image digest `sha256:8f660bbf44f870523b42765a0889ddf2ea8911d64c5d04658c479e6e2e1431fd`.

This is same-daemon archive-load evidence, not an independent host test, registry manifest digest or runtime acceptance. Only JSON proofs are retained; the Docker archive was ephemeral on the runner. Migrations/evidence lists are empty and completeness is explicitly unchecked. No registry publish or deployment occurred. The mutable Dockerfile syntax frontend is recorded; reproducible build output is not claimed. Source build paths now trigger this workflow automatically.

## Scheduler preparation

[Run 40798061866](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798061866), candidate ae2990f, passed all 13 tests without the Windows skips, plus real Linux `systemd-analyze verify` on CLI-generated service/timer units. One required Compose project + shop pair has one timer; generated commands explicitly name Docker context, Compose project/directory/file, non-root container user, channels and batch size. No service was installed, enabled or started. Host accounts/secrets are not invented.

## Full isolated platform acceptance

[Run 40800924097](https://github.com/goldeget/japan-premium-commerce/actions/runs/40800924097), candidate ae370bbb3a8aab98e3da7f33419b843618c5e508, succeeded with **39/39 unique phases**, aggregate passed=true and cleanup=success. There are 40 phase PASS log lines because restart_readback executes twice. Proof ZIP [12866995280](https://github.com/goldeget/japan-premium-commerce/actions/runs/40800924097/artifacts/12866995280) was downloaded and its SHA-256 verified as `17c3c254e636dcf0d2762eb7122de38cf2a07fbce6461e1b8b026da607d9d533`; it contains 15 JSON records and 24 redacted PNG captures.

- Native MBO error proof: installed/active ps_mbo 5.3.2 and ps_facebook 1.38.19; actual installed controller + native error Twig/light parent rendered status 503, injected header verified, Korean message exactly twice and English source absent. Eight actual request context subscriber classes executed ten callbacks, plus one native legacy controller context callback. The test uses an in-memory empty session and a test-only provider; no authenticated HTTP, full default admin chrome, external Addons/Facebook availability or visual screenshot acceptance is claimed.
- Notification health: actual PHP/MariaDB behavior tests passed, including shop isolation, read-only row hashes, stale/unqueued/future-retry distinctions, low disk cases, status/exit mapping, bootstrap premature-exit guarding and redaction. Real native CLI returned ok/exit0 for the disposable shop; schema/exit validation retained only safe aggregate fields. This does not assert production health or an approved SLA.
- Encrypted restore: actual age 1.1.1 encrypted/decrypted SQL bytes matched, tampered ciphertext and a wrong identity were rejected before import, independent MariaDB restore/domain readback passed. Private identities/dumps/plaintext/ciphertext are removed by the trap and not uploaded. This is database-snapshot CI evidence, not production full-volume backup, retention, key custody or RPO/RTO acceptance.
- Existing customer request/points, concurrency/isolation, native accounts/ACL, mail and mock Push, browser/quality/PWA, restart/source and durable readback phases also passed in this candidate.


## Failure history retained

- ae2990f / [40798061767](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798061767): preflight failed because the fake Docker protocol matched command fragments as exact argv elements. Real readback uses a full path and dump uses a sh command string. Fixed test-only routing; cleanup succeeded. No runtime acceptance was claimed.
- ffff55c / [40798225813](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798225813): health phase passed including real native CLI collection, but native MBO probe failed with TypeError at provider invocation. Symfony's fourth constructor argument is integer code, headers are fifth. Fixed the fixture with explicit code 0, preserving response/header/Korean assertions. Cleanup succeeded; later phases were not run.

- 2b4bc8 / [40798713117](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798713117): native light layout failed before admin path constants were initialized. Defined only the verified existing native admin directory before bootstrap.
- 6a94cd / [40799543433](https://github.com/goldeget/japan-premium-commerce/actions/runs/40799543433): native language context builder had no language ID. Added actual native request context callbacks rather than inventing a context object.
- 3459f7 / [40800196779](https://github.com/goldeget/japan-premium-commerce/actions/runs/40800196779): native HeadTag component required the legacy context synchronization layer. Added the real LegacyContextSubscriber and project Korean locale subscriber plus the native controller context callback, preserving the real templates and assertions. All four runtime partial runs passed 14 phases, failed native_boundary and left 24 phases not run; their cleanup succeeded. Final ae370 full result above supersedes these failures without discarding them.

## Available environment discovery and remaining real-world acceptance

Docker Desktop is installed and its engine now answers 29.8.2. Read-only container inventory found existing unrelated Supabase containers; none were modified. ORDENOWA acceptance ran in owned disposable GitHub environments.

Connected Cloudflare read-only discovery found no ORDENOWA/KURANEA/japan-premium-commerce name/repository matches in visible zones, Pages projects and Worker scripts. This does not prove that no deployment exists elsewhere. GitHub deployments could not be inspected through the connector's allowed endpoints. No hosting resource, secret or DNS configuration was created.

The native MBO proof is a direct controller/Twig call using a test-only failed provider and in-memory session. It is not authenticated HTTP/ACL/full-admin browser acceptance, external Addons availability, or Facebook service availability. Bootstrap DB/network side effects are not instrumented. Local CUA reported no available browser and IAB creation unavailable; an app panel queued response is not browser access evidence.

GPT selected/investigated Amazon JP and Rakuten candidates. Amazon B0H4V3GT4J has source title/breadcrumb/gallery metadata but no exact current JPY price, and the captured page metadata is old. Amazon B0F3GZBZ9R has older price/multiple-offer information without current buy-box/availability confirmation. Official Rakuten MUJI 4550723058445 yielded title/specification/category data without accepted exact price/options. No real product import or affirmative image-reuse permission was established.

Actual operator identity/policy approval, approved HTTPS/SMTP/secret and hosting targets, live Push delivery, physical iOS/Android acceptance, persistent backup destination/retention and independent production staging promotion/rollback remain unverified. These facts are not fabricated and are not a renewed broad input questionnaire. GPT owns further technical preparation and uses existing approved business/brand materials; only irreducible real-world acceptance/authority remains separate.
