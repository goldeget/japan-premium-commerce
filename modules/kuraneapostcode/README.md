# KURANEA Japan Postcode Lookup

First-party PrestaShop 9 module for Japanese postcode and address candidates.
The customer form keeps PrestaShop's native `id_state`, `city`, `address1`,
`address2`, and `postcode` fields. Selecting a candidate fills prefecture,
municipality, town area, and postcode. Customers can still edit every native
field; building and room details are never overwritten.

## Install

New empty Compose installations bundle this module in the application image
and install it during the first KURANEA bootstrap. For an already-installed
shop, deploy this directory to `modules/kuraneapostcode/` and install **KURANEA
Japan Postcode Lookup** from **Modules > Module Manager**.

The module creates its own `kuraneapostcode_address` table with
   `CREATE TABLE IF NOT EXISTS`, enables the Japan state selector if needed,
   and idempotently adds missing `JP-01` through `JP-47` state records.
   It does not download or fabricate postcode records at installation.
4. Until a CSV has been imported, the search returns no candidates and the
   address form remains manually editable.

The module does not remove its table or prefecture state rows on uninstall.
Existing orders can refer to those states, so module removal does not delete
them.

## Import or update official data

1. Obtain and extract the current KEN_ALL archive from Japan Post's official
   download page: <https://www.post.japanpost.jp/service/search/zipcode/download/>.
2. Keep the downloaded archive and extracted CSV outside the public document
   root. The importer reads an operator-supplied local file and makes no network
   request.
3. From the PrestaShop root, run:

   ```sh
   php modules/kuraneapostcode/bin/import-ken-all.php --file=/absolute/path/to/KEN_ALL.CSV
   ```

The command first parses into the module-owned staging table, then replaces
only the module's postcode rows in an InnoDB transaction after at least one
valid row has been staged. If the file cannot be read, parsing/import fails, or
the input contains no valid addresses, the current postcode table is left as
is. Run one import at a time. Exact duplicate rows are deduplicated; duplicate
postcodes with different town areas remain separate selectable candidates.

KEN_ALL fields are read from columns 0, 2, 6, 7, and 8: JIS municipality code,
postcode, prefecture, municipality, and town area. UTF-8 and CP932/Windows-31J
are supported. The local domain importer can also be called with a persistence
callback for a different operator-managed import workflow.

## Address form and candidate endpoint

The module uses `additionalCustomerAddressFields` to add a multilingual search
widget to PrestaShop customer address forms. It is shown for Japan, searches
through a public read-only GET endpoint at
`/module/kuraneapostcode/candidates?q=...`, and uses the selected candidate to
fill native address fields. Japanese address substring search and normalized
seven-digit / `NNN-NNNN` postcode search are supported. The public endpoint
returns only the public postal address data and has `Cache-Control: no-store`.

The frontend normalizes ASCII/full-width digits and supported hyphens before
native PrestaShop postcode validation. The server also normalizes the posted
postcode before that core validation, so the accepted seven-digit input works
without JavaScript. Search failure never blocks manual address entry.
When official postcode candidates are available, the server validates the
selected native prefecture, municipality, and town area against the postcode
before saving. Building and room fields remain customer-editable. If the
postcode index has no rows or cannot be queried, manual entry remains enabled.

Widget and validation strings are provided in Japanese, English, and Korean.
Because saved orders use the same native PrestaShop address fields, the
municipality and town area remain visible through native order address views.

## Tests and evidence

Run the synthetic domain suite inside the existing PrestaShop container without
installing the module in that shop's database:

```sh
tar -cf - modules/kuraneapostcode tests/postcode \
  | docker compose exec -T prestashop sh -c 'mkdir -p /tmp/kuraneapostcode-test && tar -xf - -C /tmp/kuraneapostcode-test'
docker compose exec -T prestashop sh -lc \
  'find /tmp/kuraneapostcode-test/modules/kuraneapostcode /tmp/kuraneapostcode-test/tests/postcode -name "*.php" -print0 | xargs -0 -n1 php -l && php /tmp/kuraneapostcode-test/tests/postcode/run.php'
```

The fixtures named `ken_all_synthetic` are fabricated test records, not Japan
Post addresses. The isolated GitHub Actions fresh-install job downloads the
official KEN_ALL archive, imports it into its disposable database, checks the
real `1000004` lookup, and saves a native PrestaShop address with a manually
edited building field. The live developer shop is not modified by that test.
`tests/postcode/verify_live_address_validation.php` is a read-only integration
check for the running developer shop: it verifies the official `1000004`
candidate, address mismatch rejection, and manual fallback without creating
customers, addresses, orders, or other database records.
Browser checkout, linked order creation, and admin order display remain
separate QA items until a full browser checkout is exercised.
