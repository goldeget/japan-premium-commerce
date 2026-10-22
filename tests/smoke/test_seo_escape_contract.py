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
            "$urls.theme_assets",
            "$urls.base_url",
        ):
            escaped = variable + "|escape:'htmlall':'UTF-8'"
            self.assertTrue(escaped in source, f"missing HTML escaping for {variable}")
            self.assertTrue("{" + variable + "}" not in source, f"raw output remains for {variable}")

    def test_structured_data_json_hex_encodes_html_tags(self):
        source = HEAD.read_text(encoding="utf-8")
        self.assertTrue(
            "{$element|@json_encode:321 nofilter}" in source,
            "JSON-LD must set JSON_HEX_TAG alongside the existing JSON flags",
        )
        self.assertTrue(
            "{$element|@json_encode:320 nofilter}" not in source,
            "JSON-LD must not emit HTML tags without JSON_HEX_TAG",
        )


if __name__ == "__main__":
    unittest.main()
