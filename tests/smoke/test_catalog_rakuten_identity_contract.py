"""Static Rakuten identity guard; PHP parser behavior is checked in catalog-parser Actions."""
from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CatalogRakutenIdentityContract(unittest.TestCase):
    def test_url_identity_precedes_merchant_identifiers(self):
        parser = (ROOT / 'modules/kuraneacatalog/src/Parsing/RakutenHtmlParser.php').read_text()
        self.assertLess(
            parser.index("return $segments[count($segments) - 2] . ':' . $segments[count($segments) - 1];"),
            parser.index("foreach (['productID', 'productCode', 'sku', 'mpn'] as $key)"),
            'Canonical path identity must be preferred to merchant JSON-LD identifiers.',
        )

    def test_synthetic_regression_has_distinct_merchant_identifiers(self):
        fixture = (ROOT / 'tests/catalog/fixtures/rakuten-merchant-identifiers.synthetic.html').read_text()
        product = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', fixture, re.S).group(1))
        self.assertNotEqual('fixture-shop:synthetic-case-b', product['productID'])
        self.assertNotEqual('fixture-shop:synthetic-case-b', product['sku'])
        self.assertEqual(2480, int(product['offers']['lowPrice']))
        runner = (ROOT / 'tests/catalog/run.php').read_text()
        service_test = (ROOT / 'tests/catalog/catalog_import_service.php').read_text()
        self.assertIn("fixture('rakuten-merchant-identifiers.synthetic.html')", runner)
        self.assertIn("'/fixtures/rakuten-merchant-identifiers.synthetic.html'", service_test)
