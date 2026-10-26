"""Static access-challenge guard; PHP behavior remains pending Actions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CatalogAccessChallengeContract(unittest.TestCase):
    def test_static_guard_runs_in_catalog_parser_workflow(self):
        workflow = (ROOT / '.github/workflows/catalog-parser.yml').read_text()
        self.assertIn('tests.smoke.test_catalog_access_challenge_contract', workflow)

    def test_successful_html_is_checked_for_access_challenges_before_return(self):
        source = (ROOT / 'modules/kuraneacatalog/src/Fetching/PublicProductFetcher.php').read_text()
        return_position = source.index('return new FetchedProduct(')
        self.assertIn('validateCaptcha|captchaContainer', source, 'HTTP 200 access challenges must be classified before returning HTML.')
        challenge_position = source.index('validateCaptcha|captchaContainer')
        self.assertLess(challenge_position, return_position)
        challenge_branch = source[challenge_position:return_position]
        self.assertIn('FetchException::FAILURE_ACCESS_BLOCKED', challenge_branch)

    def test_challenge_fixture_retains_parseable_product_metadata(self):
        source = (ROOT / 'tests/catalog/fixtures/amazon-jp-access-challenge.synthetic.html').read_text()
        self.assertIn('validateCaptcha', source)
        self.assertIn('property="og:title"', source)
        self.assertIn('property="product:price:amount"', source)
        self.assertIn('property="product:price:currency" content="JPY"', source)
