from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "admin_locale" / "native_mbo_error_render.php"
ACCEPTANCE = ROOT / "tests" / "procurement" / "ci_acceptance.sh"


class NativeMboErrorRenderContractTests(unittest.TestCase):
    def test_native_probe_is_isolated_bounded_and_fail_closed(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        for guard in (
            "KURANEA_ISOLATED_CI",
            "KURANEA_CI_PROJECT_NAME",
            "GITHUB_RUN_ID",
            "PS_DOMAIN",
            "prestashop.installed_modules",
            "prestashop.active_modules",
            "'ps_mbo'",
            "'ps_facebook'",
            "config.xml",
            "LIBXML_NONET",
        ):
            with self.subTest(guard=guard):
                self.assertIn(guard, source)
        self.assertIn("'script_app_mutations' => false", source)
        self.assertIn("'bootstrap_database_side_effects_instrumented' => false", source)
        self.assertIn("'bootstrap_network_side_effects_instrumented' => false", source)
        self.assertIn("'injected_provider_http_calls' => 0", source)
        self.assertNotIn("'upstream_http_calls' => 0", source)
        self.assertNotIn("'database_writes_by_probe' => 0", source)
        self.assertNotIn("'read_only_probe' => true", source)
        self.assertIn("liteDisplaying=1", source)
        self.assertIn("headers->get('X-ORDENOWA-CI-Injected-Failure')", source)
        self.assertIn("$response->headers->get('X-ORDENOWA-CI-Injected-Failure')", source)
        self.assertIn("ServiceUnavailableHttpException", source)
        self.assertIn("ExternalContentProviderInterface", source)
        self.assertIn("new AdminKernel('prod', false)", source)
        self.assertIn("ThemeCatalogController::class", source)
        self.assertIn("@Modules/ps_mbo/views/templates/admin/error.html.twig", source)
        self.assertIn("substr_count($body, $koreanMessage) < 2", source)
        self.assertIn("str_contains($body, $sourceMessage)", source)
        self.assertNotIn("curl_exec(", source)
        self.assertNotIn("file_put_contents(", source)
        self.assertNotIn("Db::getInstance()->execute(", source)
        self.assertNotIn("Module::install(", source)
        self.assertNotIn("getTraceAsString(", source)
        self.assertNotIn("getMessage()", source)
        self.assertIn("$error->getSourceContext()?->getName()", source)
        self.assertIn("$error->getTemplateLine()", source)
        self.assertIn("PrestaShop/Admin|PrestaShopCore|Modules/ps_mbo", source)
        self.assertIn("(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+", source)

    def test_native_boundary_captures_the_bounded_module_and_render_readback(self) -> None:
        acceptance = ACCEPTANCE.read_text(encoding="utf-8")
        boundary = acceptance.split("native_boundaries() {", 1)[1].split(
            "\n}\nrun_phase native_boundary native_boundaries", 1
        )[0]
        invocation = (
            'compose exec -T -u www-data prestashop php '
            '/var/www/html/tests/admin_locale/native_mbo_error_render.php '
            '>"$QA_ARTIFACT_DIR/native-mbo-error-render.json" || return "$?"'
        )
        self.assertIn(invocation, boundary)
        self.assertLess(
            boundary.index("cache:clear --env=prod --no-debug"),
            boundary.index("native_mbo_error_render.php"),
            "render using the already warmed native production Twig/container state",
        )


if __name__ == "__main__":
    unittest.main()

