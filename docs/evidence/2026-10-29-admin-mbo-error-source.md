# Admin MBO error Korean overlay

This is an isolated integration bundle for the release-prep work branch, not a write to the shared checkout.

## Patch scope

- Registers the exact Modules.Mbo.Errors Symfony catalogue domain in the project-owned kuraneabackoffice overlay loader.
- Adds one project-owned Korean XLIFF entry for the verified upstream Addons connectivity error.
- Leaves PrestaShop core and ps_mbo vendor/module files untouched.
- Adds a focused Python contract test. The full current locale lifecycle harness is staged with explicit-locale and default-locale MBO error translation assertions.

## Source evidence

- Target work revision: 9c80e4006f9a59df7ed638db1d4f4870b124739f. The current AdminLocaleSubscriber.php source blob fetched from that ref is 66705f9fcba2dca972dc43529d358a1a7afc09be.
- Upstream module snapshot: [PrestaShopCorp/ps_mbo commit 7f694df47340d1399dd4ad8cb395bc4fc91d2ab1](https://github.com/PrestaShopCorp/ps_mbo/tree/7f694df47340d1399dd4ad8cb395bc4fc91d2ab1), version 5.3.3.
- Upstream source catalogue: [translations/en-US/ModulesMboErrors.en-US.xlf](https://github.com/PrestaShopCorp/ps_mbo/blob/7f694df47340d1399dd4ad8cb395bc4fc91d2ab1/translations/en-US/ModulesMboErrors.en-US.xlf). It establishes source ID 8a5560b05facacdbc10e870b1152e41b and the exact source text.
- Upstream template: [views/templates/admin/error.html.twig](https://github.com/PrestaShopCorp/ps_mbo/blob/7f694df47340d1399dd4ad8cb395bc4fc91d2ab1/views/templates/admin/error.html.twig), which uses the Modules.Mbo.Errors domain for the same message in both image alt text and the visible error paragraph.
- The project subscriber normalizes each configured domain, registers its XLIFF with addResource, and merges module-owned catalogues after database catalogues.

## Validation boundaries

Run the focused Python contract from this bundle with:

    python work/admin-ko-fix/tests/admin_locale/test_mbo_errors_korean_overlay.py

The PHP lifecycle patch adds explicit-locale and default-locale Symfony Translator assertions. It was not executed in this workspace because PHP/PrestaShop runtime dependencies are unavailable here. No browser/native MBO page rendering was performed; this bundle proves the project catalogue mapping and translation resource, not the remaining end-to-end route acceptance.

