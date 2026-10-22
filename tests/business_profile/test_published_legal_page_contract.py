from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules/kuraneabusinessprofile"


class PublishedLegalPageContractTests(unittest.TestCase):
    def test_builder_has_localized_published_disclosure_sections_and_closed_gate(self):
        builder = MODULE / "src/Customer/PublishedLegalPageBuilder.php"
        self.assertTrue(builder.is_file(), "The public legal page builder must exist.")
        source = builder.read_text(encoding="utf-8")
        for value in (
            "class PublishedLegalPageBuilder",
            "commerceEnabled",
            "company_profile",
            "specified_commercial_act",
            "customer_support",
            "payment",
            "shipping",
            "refund",
            "terms",
            "privacy",
            "ENT_QUOTES",
            "ENT_SUBSTITUTE",
        ):
            with self.subTest(value=value):
                self.assertIn(value, source)

    def test_front_controller_reads_published_module_profile_and_external_gate(self):
        controller = MODULE / "controllers/front/legal.php"
        self.assertTrue(controller.is_file(), "A public module legal page route must exist.")
        source = controller.read_text(encoding="utf-8")
        self.assertIn("$this->module->publicProfile()", source)
        self.assertIn("CommerceGate::isEnabled", source)
        self.assertIn("ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED", source)
        self.assertIn("PublishedLegalPageBuilder::build", source)
        self.assertIn("views/templates/front/legal.tpl", source)
        self.assertNotIn("loadDraft", source, "Customer output must never use draft settings.")

    def test_published_footer_links_customers_to_the_legal_page(self):
        module = MODULE / "kuraneabusinessprofile.php"
        source = module.read_text(encoding="utf-8")
        builder = MODULE / "src/Customer/PublishedLegalPageBuilder.php"
        builder_source = builder.read_text(encoding="utf-8")
        self.assertIn("PublishedLegalPageBuilder::footerLink", source)
        self.assertIn("getModuleLink($this->name, 'legal')", source)
        self.assertIn("function footerLink", builder_source)


if __name__ == "__main__":
    unittest.main()
