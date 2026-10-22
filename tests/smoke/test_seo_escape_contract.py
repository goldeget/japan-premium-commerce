"""SEO escaping contract for the active ORDENOWA Smarty head override."""
import html
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEMES = ROOT / "themes"
HEAD = THEMES / "kuranea" / "templates" / "_partials" / "head.tpl"
LEGACY_JSONLD = (
    THEMES
    / "kuranea"
    / "templates"
    / "_partials"
    / "microdata"
    / "head-jsonld.tpl"
)
PRODUCT_JSONLD = THEMES / "kuranea" / "templates" / "_partials" / "microdata" / "product-jsonld.tpl"
PRODUCT_LIST_JSONLD = THEMES / "kuranea" / "templates" / "_partials" / "microdata" / "product-list-jsonld.tpl"
PRODUCT_TEMPLATE = THEMES / "hummingbird" / "templates" / "catalog" / "product.tpl"
CHILD_PRODUCT_TEMPLATE = THEMES / "kuranea" / "templates" / "catalog" / "product.tpl"
PRODUCT_LIST_TEMPLATE = THEMES / "kuranea" / "templates" / "catalog" / "listing" / "product-list.tpl"
CHILD_THEME_CONFIG = THEMES / "kuranea" / "config" / "theme.yml"
SEO_WORKFLOW = ROOT / ".github" / "workflows" / "seo-escape.yml"
SEO_WORKFLOW_PATHS = (
    ".github/workflows/seo-escape.yml",
    "tests/smoke/test_seo_escape_contract.py",
    "themes/kuranea/templates/_partials/head.tpl",
    "themes/kuranea/templates/_partials/microdata/head-jsonld.tpl",
    "themes/kuranea/templates/_partials/microdata/product-jsonld.tpl",
    "themes/kuranea/templates/_partials/microdata/product-list-jsonld.tpl",
    "themes/kuranea/templates/catalog/product.tpl",
    "themes/kuranea/templates/catalog/listing/product-list.tpl",
    "themes/kuranea/config/theme.yml",
    "themes/hummingbird",
    ".gitmodules",
)


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

    def test_legacy_jsonld_fallback_uses_child_override_and_json_encodes_dynamic_values(self):
        head_source = HEAD.read_text(encoding="utf-8")
        self.assertIn(
            "{include file='_partials/microdata/head-jsonld.tpl'}",
            head_source,
            "the child head override must continue to use the legacy fallback when core structured data is empty",
        )
        self.assertTrue(LEGACY_JSONLD.is_file(), "the child theme must override the inherited raw JSON-LD fallback")
        source = LEGACY_JSONLD.read_text(encoding="utf-8")

        for variable in (
            "$ordenowaBrandName",
            "$urls.pages.index",
            "$ordenowaLogoDesktop",
            "$page.meta.title",
            "$urls.current_url",
            "$ordenowaSearchActionTarget",
            "$smarty.foreach.breadcrumb.iteration",
            "$path.title",
            "$path.url",
        ):
            escaped = "{" + variable + "|@json_encode:321 nofilter}"
            self.assertIn(escaped, source, f"missing script-safe JSON encoding for {variable}")
            self.assertNotIn("{" + variable + "}", source, f"raw JSON-LD value remains for {variable}")

    def test_product_and_listing_jsonld_overrides_encode_every_dynamic_output(self):
        for path in (PRODUCT_JSONLD, PRODUCT_LIST_JSONLD):
            self.assertTrue(path.is_file(), f"the child theme must override {path.name}")
            source = path.read_text(encoding="utf-8")
            expressions = [match.strip() for match in re.findall(r"\{([^{}]+)\}", source)]
            dynamic_outputs = []
            for expression in expressions:
                if not expression.startswith(("$", "(")):
                    continue
                if re.match(r"^\$[A-Za-z_][A-Za-z0-9_.]*\s*=", expression):
                    continue
                dynamic_outputs.append(expression)

            self.assertTrue(dynamic_outputs, f"{path.name} should contain checked dynamic JSON output")
            for expression in dynamic_outputs:
                self.assertRegex(
                    expression,
                    r"\|@json_encode:321\s+nofilter\s*$",
                    f"dynamic JSON output is not script-safe in {path.name}: {{{expression}}}",
                )

    def test_product_and_listing_templates_resolve_child_jsonld_overrides(self):
        theme_config = CHILD_THEME_CONFIG.read_text(encoding="utf-8")
        child_head = HEAD.read_text(encoding="utf-8")
        product_template = PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        product_list_template = PRODUCT_LIST_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("parent: hummingbird", theme_config)
        self.assertIn("{block name='head_microdata_special'}{/block}", child_head)
        self.assertIn(
            "{include file='_partials/microdata/product-jsonld.tpl'}",
            product_template,
            "the pinned Hummingbird product template must render product JSON-LD",
        )
        self.assertIn(
            "{block name='head_microdata_special'}",
            product_list_template,
            "the child listing template must render its page-specific structured data block",
        )
        self.assertIn(
            "{include file='_partials/microdata/product-list-jsonld.tpl' listing=$listing}",
            product_list_template,
        )
        self.assertTrue(
            PRODUCT_JSONLD.is_file(),
            "Smarty should resolve the inherited product partial path from the child theme",
        )
        self.assertTrue(
            PRODUCT_LIST_JSONLD.is_file(), "Smarty should resolve the listing include from the child theme"
        )

    def test_product_attribute_translations_escape_persisted_catalog_names(self):
        parent_source = PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        manufacturer_parent_block = parent_source.split(
            "{block name='product_header_manufacturer'}", 1
        )[1].split("{/block}", 1)[0]
        attachment_parent_block = parent_source.split(
            "{block name='product_attachments'}", 1
        )[1].split("{/block}", 1)[0]

        manufacturer_translation = (
            "{l s='Product brand: %brand_name%' "
            "sprintf=['%brand_name%' => $product_manufacturer->name] d='Shop.Theme.Catalog'}"
        )
        attachment_translation = (
            "{l s='Download %attachment_name%' "
            "sprintf=['%attachment_name%' => $attachment.name] d='Shop.Theme.Actions'}"
        )
        self.assertIn(manufacturer_translation, manufacturer_parent_block)
        self.assertIn(attachment_translation, attachment_parent_block)

        self.assertTrue(CHILD_PRODUCT_TEMPLATE.is_file(), "child product override is missing")
        child_source = CHILD_PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{extends file='parent:catalog/product.tpl'}", child_source)
        manufacturer_child_block = child_source.split(
            "{block name='product_header_manufacturer'}", 1
        )[1].split("{/block}", 1)[0]
        attachment_child_block = child_source.split(
            "{block name='product_attachments'}", 1
        )[1].split("{/block}", 1)[0]
        self.assertIn(
            "{capture assign='manufacturer_aria_label'}" + manufacturer_translation + "{/capture}",
            manufacturer_child_block,
        )
        self.assertIn(
            "{capture assign='attachment_aria_label'}" + attachment_translation + "{/capture}",
            attachment_child_block,
        )
        self.assertIn(
            "aria-label=\"{$manufacturer_aria_label|escape:'htmlall':'UTF-8' nofilter}\"",
            manufacturer_child_block,
        )
        self.assertIn(
            "aria-label=\"{$attachment_aria_label|escape:'htmlall':'UTF-8' nofilter}\"",
            attachment_child_block,
        )
        self.assertNotIn('aria-label="{l', manufacturer_child_block)
        self.assertNotIn('aria-label="{l', attachment_child_block)

        hostile_name = 'Brand" onmouseover="alert(1)'
        escaped_label = html.escape(f"Product brand: {hostile_name}", quote=True)
        rendered_anchor = f'<a aria-label="{escaped_label}">'
        self.assertIn("&quot; onmouseover=&quot;alert(1)", rendered_anchor)
        self.assertNotIn(' onmouseover="alert(1)"', rendered_anchor)
        self.assertNotIn('aria-label="Product brand: Brand" onmouseover=', rendered_anchor)

    def test_product_scalar_attributes_and_text_are_explicitly_escaped(self):
        source = CHILD_PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        manufacturer_block = source.split("{block name='product_header_manufacturer'}", 1)[1].split("{/block}", 1)[0]
        attachment_block = source.split("{block name='product_attachments'}", 1)[1].split("{/block}", 1)[0]

        self.assertIn(
            'href="{$product_manufacturer->url|escape:\'htmlall\':\'UTF-8\'}"',
            manufacturer_block,
            "manufacturer URLs must be escaped for an HTML attribute",
        )
        self.assertIn(
            "{$product_manufacturer->name|escape:'htmlall':'UTF-8'}",
            manufacturer_block,
            "manufacturer names must be escaped for an HTML text node",
        )
        self.assertIn("{block name='page_title'}{$product.name|escape:'htmlall':'UTF-8'}{/block}", source)
        for variable in ("$attachment.name", "$attachment.description", "$attachment.file_size_formatted"):
            self.assertIn(
                "{" + variable + "|escape:'htmlall':'UTF-8'}",
                attachment_block,
                f"plain attachment field {variable} must be escaped in its HTML text context",
            )

        # Product descriptions are curated rich HTML and must keep their current rendering path.
        parent_source = PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{$product.description_short nofilter}", parent_source)
        self.assertIn("{$product.description nofilter}", parent_source)

    def test_inherited_product_metadata_does_not_bypass_prestashop_html_autoescaping(self):
        source = PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        head_block = source.split("{block name='head' append}", 1)[1].split("{/block}", 1)[0]
        for variable in (
            "$product.url",
            "$product.cover.large.url",
            "$product.price_tax_exc",
            "$currency.iso_code",
            "$product.price_amount",
            "$product.weight",
            "$product.weight_unit",
        ):
            output = "{" + variable + "}"
            self.assertIn(output, head_block, f"expected inherited product metadata output {output}")
            self.assertNotIn(output + " nofilter", head_block, f"must not disable PrestaShop 9 HTML autoescape for {output}")

    def test_seo_contract_workflow_triggers_for_every_template_dependency(self):
        source = SEO_WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"uses: actions/checkout@v4\s+with:\s+submodules: recursive",
            "the SEO contract workflow must check out the pinned Hummingbird submodule",
        )
        for trigger, next_trigger in (("push", "pull_request"), ("pull_request", "workflow_dispatch")):
            section = source.split(f"  {trigger}:", 1)[1].split(f"  {next_trigger}:", 1)[0]
            configured_paths = tuple(re.findall(r"^      - '([^']+)'$", section, flags=re.MULTILINE))
            self.assertEqual(
                SEO_WORKFLOW_PATHS,
                configured_paths,
                f"{trigger} path filters must cover every child/parent SEO template dependency, the contract, and workflow configuration",
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
