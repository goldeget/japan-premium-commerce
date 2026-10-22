"""SEO escaping contract for the active ORDENOWA Smarty head override."""
import unittest
from pathlib import Path

HEAD = Path(__file__).resolve().parents[2] / "themes" / "kuranea" / "templates" / "_partials" / "head.tpl"


class SeoEscapeContract(unittest.TestCase):
    def test_dynamic_meta_values_are_html_attribute_escaped(self):
        source = HEAD.read_text(encoding="utf-8")
        for variable in (
            "$ordenowaResolvedSeoDescription",
            "$page.meta.robots",
            "$page.canonical",
            "$pageUrl",
            "$code",
            "$ordenowaResolvedSeoTitle",
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

    def test_home_uses_brand_seo_defaults_and_other_pages_keep_prestashop_metadata(self):
        source = HEAD.read_text(encoding="utf-8")
        resolution = source.split("{if $page.page_name == 'index'}", 1)[1].split("{/if}", 1)[0]
        home, other_pages = resolution.split("{else}", 1)

        self.assertIn("{$ordenowaResolvedSeoTitle = $ordenowaSeoTitle|default:$page.meta.title}", home)
        self.assertIn("{$ordenowaResolvedSeoDescription = $ordenowaSeoDescription|default:$page.meta.description}", home)
        self.assertIn("{$ordenowaResolvedSeoTitle = $page.meta.title|default:$ordenowaSeoTitle}", other_pages)
        self.assertIn("{$ordenowaResolvedSeoDescription = $page.meta.description|default:$ordenowaSeoDescription}", other_pages)
        self.assertIn("<title>{block name='head_seo_title'}{$ordenowaResolvedSeoTitle|escape:'htmlall':'UTF-8'}{/block}</title>", source)
        self.assertIn('<meta name="description" content="{block name=\'head_seo_description\'}{$ordenowaResolvedSeoDescription|escape:\'htmlall\':\'UTF-8\'}{/block}">', source)
        self.assertEqual(1, source.count('content="{$ordenowaResolvedSeoTitle|escape:\'htmlall\':\'UTF-8\'}"'))
        self.assertEqual(1, source.count('content="{$ordenowaResolvedSeoDescription|escape:\'htmlall\':\'UTF-8\'}"'))


if __name__ == "__main__":
    unittest.main()
