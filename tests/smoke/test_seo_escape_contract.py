"""SEO escaping contract for the active ORDENOWA Smarty head override."""
import unittest
from pathlib import Path

HEAD = Path(__file__).resolve().parents[2] / "themes" / "kuranea" / "templates" / "_partials" / "head.tpl"

class SeoEscapeContract(unittest.TestCase):
    def test_dynamic_meta_values_are_html_attribute_escaped(self):
        source = HEAD.read_text(encoding="utf-8")
        for variable in (
            "$ordenowaSeoDescription|default:$page.meta.description",
            "$page.meta.robots",
            "$page.canonical",
            "$pageUrl",
            "$code",
            "$ordenowaSeoTitle|default:$page.meta.title",
            "$urls.current_url",
            "$ordenowaBrandName|default:$shop.name",
        ):
            self.assertIn(variable + "|escape:'htmlall':'UTF-8'", source)
            self.assertNotIn("{" + variable + "}", source)

    def test_structured_data_json_hex_encodes_html_tags(self):
        source = HEAD.read_text(encoding="utf-8")
        self.assertIn("{$element|@json_encode:321 nofilter}", source)
        self.assertNotIn("{$element|@json_encode:320 nofilter}", source)

if __name__ == "__main__":
    unittest.main()
