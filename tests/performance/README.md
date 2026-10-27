# Storefront performance and accessibility acceptance

The isolated browser acceptance run uses Lighthouse 13.5.0 and axe-core 4.14.0 from the exact versions and dependency integrity values in `package-lock.json`.

The axe scan requests the supported `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, and `wcag22aa` tags. axe-core 4.14.0 does not publish a `wcag22a` tag; the run checks its requested tag inventory before scanning and fails with a safe diagnostic if a configured tag is unsupported. The resulting checks are automated rule coverage, not a complete WCAG 2.2 AA conformance claim. axe `incomplete` rule IDs are included in the sanitized artifact and require manual review.

The browser artifact contains route labels, Lighthouse scores and metrics, a separately labeled scripted interaction lab proxy, and sanitized axe rule IDs, impact, and node counts. It omits raw Lighthouse reports, URLs, DOM text, selectors, and node details.
