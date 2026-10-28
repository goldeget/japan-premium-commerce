# ORDENOWA independent review

Reviewer: `/root/independent_review` (did not author customer UI).

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

Independently calculated WCAG relative-luminance ratios for the safe computed color pairs supplied by the customer/quality reviewers: header RGB(20,38,60) on white 15.30:1; language select on RGB(247,249,252) 14.51:1; white footer on RGB(7,27,61) 17.03:1; mobile nav text RGB(7,27,61) on 97%-opaque RGB(248,251,254) over navy 15.46:1. These pairs exceed text/non-text contrast thresholds. The supplied metadata was bounded to five ancestors and from an older cache state; it does not prove every actual background, SVG overlap, icon state or all automated incomplete findings. No full WCAG claim.

Old core screenshots with broad replacement of text/removal of images and disabled controls are rejected as visual acceptance evidence. They cannot establish real layout, photo rendering or native enabled state.

No external Work Mode handoff or external browser inspection has been performed by this reviewer.
