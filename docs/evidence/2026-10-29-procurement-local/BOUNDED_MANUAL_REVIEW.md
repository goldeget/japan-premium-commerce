# Bounded manual review of axe incomplete findings

Source: `bd1ced815093df2fadc21b521cdb01bdd546ed0a`, actual native isolated runtime after the CI owner's source alignment. Reviewer: `/root/independent_review`.

## Scope and retained automated result

The full quality3 artifact reports zero automated axe violations across 84 cells, while retaining incomplete findings for `color-contrast` and mobile `label-content-name-mismatch`. This manual review does not edit those results, disable either rule, or assert full WCAG compliance. Field INP remains **NOT TESTED**.

Actual safe current metadata: `/tmp/ordenowa-customer-static-incomplete-bd1/static-incomplete-outcome.json`. Final collection contains **27 representative cells**: JA seven routes at 320/390/1440, plus EN and KO assignments at those widths. The collector's final aggregate is true with zero violations and 13 known incomplete-node patterns. An earlier collection stopped at KO 320 because its screenshot public-label allowlist omitted the actual official translation `당신의 계정`. That was a diagnostic guard failure, not an established app failure. The final JSON retains `previous_diagnostic_failure`, and `initial-allowlist-failure-event.json` records the earlier actual false outcome (25 collected cells/28 crops), classification and KO-only resolution. The original raw partial JSON was overwritten by the resumed collector; the event record is not represented as recovery of that original file.

Independently opened all **42 JA/EN/KO static component crops** in that directory, including the 14 additional KO captures after the runtime owner reported healthy cache and gave the capture owner permission to resume. No browser or API requests were initiated by this reviewer. Native account icons, four mobile navigation symbols, footer account chevron, language selector and closed/open PWA guidance were visible without masking of public static labels or symbols. No app source changes were required for these manual findings.

## Manual adjudication of observed patterns

| Incomplete pattern | Actual evidence and manual result |
| --- | --- |
| Header account icon contrast | Material Icons face available; actual person glyph renders. Current ancestor chain reaches solid white with no background image/filter and unit opacity. RGB(20,38,60) on white gives **15.303:1**, exceeding 3:1 for the symbol and 4.5:1 for normal text. No contrast defect in the observed state. |
| Footer account chevron contrast | Actual chevron renders on solid navy; RGB(255,255,255) on RGB(7,27,61) gives **17.029:1**. The icon is `aria-hidden=true`; the native button has a separate localized accessible toggle label and expanded/controls attributes. No defect in the observed state. |
| Four mobile navigation icons | Actual home/clipboard/star/account glyphs render; decorative icons are `aria-hidden=true` and links have visible localized text. Foreground RGB(7,27,61), surface RGBA(248,251,254,0.97), no image/filter on that surface except backdrop blur. Rather than treating a DOM ancestor as the physical backdrop, computed a conservative bound over **any** underlying sRGB color: darkest surface RGB(240.56,243.47,246.38), contrast **at least 15.356:1**. No contrast defect in the observed state. |
| Mobile navigation text | Same arbitrary-backdrop bound with RGB(20,38,60) text gives **at least 13.800:1**, exceeding the normal-text threshold despite its small 10.56px font. JA/EN/KO labels are actually legible in the inspected static crops. |
| Desktop language selector | Text RGB(20,38,60) on solid RGB(247,249,252) gives **14.510:1**. Native inline SVG uses only `#343a40`; that arrow on the same surface gives **10.908:1**. Actual JA/EN/KO crops show selected language text and chevron separated. No background photo or text obstruction is present in the inspected state. The native selector's accessible label remains English `Change language` in the observed locales; selected options are localized. This is a localization-coverage qualification, not the reported contrast defect. |
| Mobile account label-content-name mismatch | Current mobile account button presents a person **symbol**, not visible text or an image of text. Its icon is `aria-hidden=true`; the native button has a generic localized account `aria-label`. Therefore a mismatch between visible textual label and accessible name is not applicable to this icon-only state. Desktop crops visibly show the same public account wording as the actual DOM `aria-label`; source uses the same translation for both. This conclusion uses actual ARIA attributes, visible labels and native button semantics; the reviewer did not inspect a full accessibility tree or separately request a computed accessible name. No confirmed label-in-name defect in the observed state. |

PWA guidance was also inspected closed and open at 320/390/1440 in JA/EN/KO. The native summary marker, localized guidance and wrapping are clear. This does not test platform installation or a physical device.

**Bounded outcome:** the observed 13 component patterns underlying the known `color-contrast` and mobile `label-content-name-mismatch` incompletes are manually adjudicated with no confirmed defect in the inspected states. The 84 automated incomplete cells remain in the automated artifact; they are not relabeled as automated passes or represented as 84 independently inspected browser states.

## Limits

- Results above apply to the observed component patterns and states, not every possible control state, browser, assistive technology or all WCAG criteria.
- The original 84 automated incomplete cells remain recorded as automated incompletes. This is separate bounded manual adjudication of their observed component patterns, not a claim that this reviewer independently opened 84 browser states.
- These captures confirm all three locales for the listed static components; they do not establish comprehensive localization of all platform strings.
- No app source was changed for this review. No production mutation, external Work Mode handoff, physical-device test or field INP observation occurred.

Calculation artifact: `/workspace/scratch/ordenowa-independent-static-contrast-calculations.json`.

## Follow-up: language selector accessible label localized

The English-only native selector label noted above is resolved by commit `cc99bbb42031a03493dc2df3969d8c6caf00abd2`. Independently reviewed the two child-theme `Shop.Theme.Global` XLF files: each adds only the `Change language` translation, with Japanese `言語を変更` and Korean `언어 변경`. Parent/core templates and native language options are unchanged.

Independently read and compared safe actual `native-before.json` and `native-after.json` under `/tmp/ordenowa-language-selector-localization/`: all three locales preserve the normalized selector outer-HTML hash after excluding the changed ARIA attribute, as well as the exact options and selection. Actual DOM ARIA labels and the capture owner's Selenium **computed accessible name** now both report Japanese `言語を変更`, English `Change language`, and Korean `언어 변경`. The three actual keyboard language transitions passed. `native-catalog-parity.json` records preservation of eight pre-existing Global keys in all three locales; `source-sync.json` records matching host/opt/webroot files.

Also independently opened the three new `ja/en/ko-native-language-label.png` crops. Visible selected-language labels and chevrons remain unchanged. Their pixels do not prove an invisible accessible name; the new focused DOM/computed-name evidence supplies that proof. This supersedes the earlier English-label qualification, without changing the original contrast-incomplete records or claiming a full accessibility-tree audit. No new browser run was initiated by this reviewer. The earlier 14 Lighthouse reports measure the unchanged geometry and rendering; the localization change is covered by its focused native evidence.
