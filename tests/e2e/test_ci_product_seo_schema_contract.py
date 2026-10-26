"""Schema.org context contract for the isolated synthetic product Offer check."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests/e2e/verify_ci_product_seo_browser.py"
PRODUCT_JSONLD = ROOT / "themes/kuranea/templates/_partials/microdata/product-jsonld.tpl"


class CiProductSeoSchemaContractTests(unittest.TestCase):
    def test_schema_context_validator_accepts_only_root_schema_org_contexts(self) -> None:
        source = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        validator = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "has_schema_org_context"
        )
        isolated = ast.Module(body=[validator], type_ignores=[])
        namespace = {"urlparse": urlparse}
        exec(compile(isolated, str(SCRIPT), "exec"), namespace)
        check = namespace["has_schema_org_context"]

        for context in ("https://schema.org", "https://schema.org/", "http://schema.org/"):
            with self.subTest(valid_context=context):
                self.assertTrue(check({"@context": context}))
        for context in (
            "https://not-schema.org/",
            "https://schema.org.example.invalid/",
            "https://user@schema.org/",
            "https://schema.org:443/",
            "https://schema.org/vocab",
            "https://schema.org/?query=bad",
            "javascript://schema.org/",
            {},
            ["https://schema.org/"],
        ):
            with self.subTest(invalid_context=context):
                self.assertFalse(check({"@context": context}))

    def test_browser_acceptance_requires_schema_org_context_for_the_matching_product(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)

        for required in (
            "def has_schema_org_context(",
            '"schema_org_context_matches_product":',
            "has_schema_org_context(product)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_product_template_emits_schema_org_context_at_product_root(self) -> None:
        source = PRODUCT_JSONLD.read_text(encoding="utf-8")
        self.assertIn('"@context": "https://schema.org/"', source)
        self.assertIn('"@type": "Product"', source)
        self.assertIn('"offers":', source)


if __name__ == "__main__":
    unittest.main()
