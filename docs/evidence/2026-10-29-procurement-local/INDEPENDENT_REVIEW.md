# ORDENOWA independent review

Reviewer: `/root/independent_review` (did not author customer UI).

## Latest visual status

**The v6 section supersedes earlier missing confirmation/support/policy/request/notification visual coverage.** Independently inspected all 54 actual saved v6 PNGs from source `bd1ced815093df2fadc21b521cdb01bdd546ed0a`. No new confirmed visual blocker in the visible regions. Product/customer values, message contents and policy bodies are masked, so this is review of layout/static UI rather than approval of actual business or legal content. Existing isolated DB was preserved; this is not a fresh-installation proof.

## Code review completed

- Reviewed Amazon Japan/Rakuten parsing, source URL validation, public fetch guards, plain text normalization, native product draft persistence, reviewed evidence bridge, native category ancestry, customer category tree and assignment filter.
- Confirmed a price ambiguity using actual PHP 8.3 execution: a synthetic `AggregateOffer` with JPY low 2000/high 3500 was normalized to the single value 2000. This was an intentional older minimum-price contract; the new exact reference field did not preserve range provenance.
- Reviewed the subsequent stricter parser patch and tests. Unequal or missing aggregate bounds fail before metadata fallback, equal normalized integer bounds establish a single price, and contradictory explicit price fails. Historical unequal-range fixture is preserved as a rejection case. The earlier exact import snapshot remains unchanged when a later ambiguous observation fails.
- No additional confirmed security defect found in the reviewed parser/category code. This source review does not establish general absence of defects.

## Verification gaps

- Actual Amazon Japan and Rakuten source compatibility remains unverified under the managed environment's CONNECT 403 restriction. Synthetic documents do not establish current marketplace compatibility.
- Production category selection is explicit staff review. Source breadcrumb is provenance, not an automatically trusted native taxonomy.
- Native product draft category persistence, native ancestry, recursive customer menu and own-assignment category filtering are present in code. Current local gallery fixture was already approved with Home; it cannot establish fresh parent/leaf category creation and placement. Requested native fresh fixture and browser menu/filter assertions from the CI owner.
- Parsed remote image URLs and approved native gallery publication are separate. Existing gallery acceptance uses CI-generated native local geometric images.

## Visual review (first actual batch)

Source qualifier supplied by capture owner: installed native runtime based on `a9fe3a0` with task fixes copied in, including the scoped header/signin update. This is not a clean installation of the final candidate SHA.

Accepted and actually inspected saved captures from `/tmp/ordenowa-customer-browser-evidence-20261029-v4/`:

1. `ja_320_light_assignment-gallery-static-labels.png`: approved native geometric image and two-photo strip render at 320px; card fits viewport. Dynamic product text is masked, so product copy itself is not reviewed.
2. `ja_390_light_points-top-static-labels.png`: localized points heading, balance panel and explanation are legible. **Confirmed mobile header issue:** static navigation labels are squeezed into narrow vertical character columns next to the logo. Reported to UI owner for a scoped responsive correction and new 320/390px capture.
3. `ja_1440_light_assignments-top-static-labels.png`: desktop logo/header, workspace tabs, enabled search/status controls and assignment card fit the viewport.
4. `ja_1440_light_assignment-gallery-static-labels.png`: primary image and both thumbnail images render; details, requested state and unavailable-to-request explanation are visible, with no apparent overlap in the inspected region.
5. `ja_320_light_requests-footer-static-labels.png`: enabled search/status controls, approved request card, points state and footer fit the viewport. Bottom navigation is fixed; this screenshot alone does not prove every final footer link's scroll reachability.

At the first batch, EN/KO, dark preference, remaining views and the corrected mobile header were pending; the v5 section below supersedes those portions. Confirmation is explicitly **NOT VISUALLY REVIEWED**, because there is no meaningful screenshot before the one-time request submission. Functional confirmation evidence is separate. Fresh-category navigation is still not visually reviewed.

The captures retain static labels, geometric images and native enabled states; dynamic sensitive values are masked. This allows layout and static UI inspection but not review of exact product/customer/point contents or their localization.

## Corrected actual visual batch: v5

Actually opened and inspected **all 21 saved PNGs** under `/tmp/ordenowa-customer-browser-evidence-20261029-v5/` with `view_image`:

| Step | Screen | Locale/viewport/preference | Reviewed result |
| --- | --- | --- | --- |
| 1 | Points/header (`*_points-top-static-labels.png`) | JA/EN/KO, 320/390/1440, light preference (9 captures) | Mobile header correction verified at 320/390; compact logo and account area no longer squeeze navigation into vertical columns. Desktop header remains clear. Localized static point explanations and history headings fit. |
| 2 | Existing requested assignment/gallery (`*_assignment-gallery-static-labels.png`) | JA/EN/KO, 320/390/1440, light preference (9 captures) | Main geometric photo and both native thumbnail photos render. Cards and metadata labels fit; unavailable/requested state is visible. Dynamic product wording is masked. |
| 3 | Points/header (`*_points-top-static-labels.png`) | JA/EN/KO, 390, dark preference (3 captures) | No additional visible breakage in these captures. The UI retains its light palette; this proves compatibility under the capture's emulated dark preference, not implementation of a distinct dark theme. |

**Verdict for these inspected regions:** no remaining confirmed visual blocker after the mobile header correction. This is a bounded visual review, not full platform approval.

Capture owner reports 124 actual read-only browser checks and 12 locale-policy HTTP checks in this run; those execution results belong to the capture owner's acceptance evidence, not an independently rerun test by this reviewer.

Still not visually reviewed: one-time confirmation before submission, support, published policy page contents, fresh native category/submenu/filter state, native admin pages, real marketplace products/photos, physical devices. The v4 search/request-footer captures remain bounded supplementary evidence from before the header correction. Screenshots do not establish keyboard accessibility, accurate balance content, permission isolation, network privacy or WCAG compliance.

Source remains the running native installation based on `a9fe3a0` plus task hotfixes copied in. These screenshots are not a clean installation proof of the final remote candidate SHA.

## Bounded contrast calculation

The first calculation used older, five-ancestor-bounded metadata. It was subsequently superseded by actual current native 27-cell component metadata reaching opaque surfaces, independent inspection of all 42 JA/EN/KO static component crops, and conservative mobile-nav bounds over any physical backdrop. Final observed patterns have header 15.303:1, language text 14.510:1, SVG chevron 10.908:1, footer chevron 17.029:1, mobile icons at least 15.356:1 and mobile text at least 13.800:1.

See `/workspace/scratch/ordenowa-bounded-manual-incomplete-review.md` for the separate manual adjudication of the 13 known component patterns behind `color-contrast` and mobile `label-content-name-mismatch`. Actual DOM ARIA/visible-label/source semantics were inspected; a full accessibility tree was not. The original 84 automated incomplete cells remain recorded, full WCAG compliance is not claimed, and field INP remains NOT TESTED. Source frontend is unchanged from `bd1ced8`; the backend Twig warmup correction does not change these components.

Follow-up `cc99bbb42031a03493dc2df3969d8c6caf00abd2` adds only Japanese/Korean language-selector ARIA translations. Independently reviewed those XLF files and actual safe before/after native evidence: normalized selector HTML/options/selection preserved, localized actual ARIA plus Selenium computed names correct, three keyboard transitions passed, eight other existing Global keys per locale preserved. Independently opened all three new selector crops. This closes the English-only accessible-label qualification; it does not alter the prior 42 component images or claim they already showed the new invisible ARIA labels.

Old core screenshots with broad replacement of text/removal of images and disabled controls are rejected as visual acceptance evidence. They cannot establish real layout, photo rendering or native enabled state.

No external Work Mode handoff or external browser inspection has been performed by this reviewer.

## Latest actual visual batch: v6

Capture owner supplied exact source `bd1ced815093df2fadc21b521cdb01bdd546ed0a`, rebuilt native image revision `bd1ced8`, and pre-run alignment of host/opt/webroot 1122 application files plus 1426 Push vendor files. Existing isolated database and volumes were retained. These source/alignment assertions belong to the CI owner's evidence; this reviewer independently inspected the saved PNGs.

Actually opened **all 54 PNGs** under `/tmp/ordenowa-customer-browser-evidence-20261029-v6/` with `view_image`:

| Step | Saved file pattern | Actual coverage | General health / evidence limits |
| --- | --- | --- | --- |
| 1 | `{ja,en,ko}_{320,390,1440}_confirmation-controls-static-labels.png` | 9 captures | Submit and change-quantity controls are clear and fit mobile/desktop widths. Quantity label and operator instructions are present. Exact quantity value is masked and relies on the capture owner's native assertions. No submission was performed by this reviewer. |
| 2 | `{ja,en,ko}_390_confirmation-product-static-labels.png` | 3 captures | Confirmation instructions visibly explain that submitted details cannot be changed. Main product photo and both thumbnails render; dynamic product wording is masked. |
| 3 | `{ja,en,ko}_{390,1440}_request-static-labels.png` | 6 captures | Approved request state, awarded-points state, reason/instructions block and request-specific support action fit. Dynamic request/quantity/reason values are masked. |
| 4 | `{ja,en,ko}_{390,1440}_support-static-labels.png` | 6 captures | Customer/support message roles, back link, textarea, 2000-character/no-attachment instruction and send action are visible and fit. Some mobile capture starts below the page-title top to show controls; that cropped title region is not independently reviewed there. Message contents are masked. |
| 5 | `{ja,en,ko}_{390,1440}_notifications-static-labels.png` | 6 captures | Localized point-history, review-result and request-received notifications form clear cards and fit. IDs/timestamps are masked. Screenshot inspection does not verify delivery or click destination. |
| 6 | `{ja,en,ko}_{390,1440}_policy_{operator,terms,privacy,points}-static-labels.png` | 24 captures | Policy headings, page structure and footer fit. Operator identity/contact and supplied policy content are masked, so actual legal/business text is not visually approved. The English operator heading is also fully covered by the privacy mask; exact text of that heading is not independently reviewed. |

**Result:** no new confirmed visual defect in the inspected v6 regions. The prior v4 mobile header problem was corrected and independently verified in v5. Privacy-mask rectangles covering some fixed-navigation pixels are known capture overlays; they are excluded from app-defect findings. Native bottom navigation was separately reviewed in v5.

Capture owner's retained `evidence-manifest.json`, `visual-outcome.json` and `domain-outcome.json` report 318 browser checks passing, all 12 domain-table hashes unchanged through previews/captures, customer C with zero requests/points, and original A/B state preserved. Setup added a separate C assignment through native admin UI; confirmation was shown without final submission. This reviewer read those safe outcomes but did not rerun or independently query the database.

Independent integrity manifest: `/workspace/scratch/ordenowa-independent-v6-image-manifest.json` lists SHA256, byte count and actual dimensions for every inspected PNG. Earlier 21 v5 images have a separate manifest at `/workspace/scratch/ordenowa-independent-v5-image-manifest.json`.

Still outside visual approval: fresh category/submenu/filter state, native admin pages, actual marketplace source/product/image compatibility, real legal policy/identity content, physical devices, full user interactions and assistive technology. Public-policy/meta-description source review is separate below. No production deployment, transaction or external Work Mode handoff was performed.

## Additional source review: public policy metadata

Reviewed the localized policy-page description override and corresponding controller/Smarty test seam. Verified the installed PrestaShop 9.2 native `FrontController::getTemplateVarPage()` signature by a read-only file inspection executed as `www-data`. The override preserves native parent page fields, accepts only the supported locale and section, and uses generic purpose descriptions without inventing operator identity or policy terms. No confirmed blocker in that change. The focused native public-page Lighthouse rerun remains separate execution evidence; the test's controller parent is a stub with actual Smarty rendering.
