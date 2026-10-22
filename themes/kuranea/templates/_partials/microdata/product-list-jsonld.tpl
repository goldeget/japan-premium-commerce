{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
<script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "itemListElement": [
    {$needsComma = false}
    {$position = 0}
    {foreach from=$listing.products item=item name=productsForJsonLd}
      {if $item.show_price}
        {$position = $position + 1}
        {if $needsComma},{/if}
        {$needsComma = true}
        {
          "@type": "ListItem",
          "position": {$position|@json_encode:321 nofilter},
          "item": {
            "@type": "Product",
            "name": {$item.name|@json_encode:321 nofilter},
            "url": {$item.url|@json_encode:321 nofilter}
            {if !empty($item.cover) && isset($item.cover.bySize.default_md.url)},
            "image": {$item.cover.bySize.default_md.url|@json_encode:321 nofilter}
            {/if}
            {if !empty($item.description_short)},
            "description": {$item.description_short|strip_tags|@json_encode:321 nofilter}
            {/if}
            {if !empty($item.manufacturer_name)},
            "brand": {
              "@type": "Brand",
              "name": {$item.manufacturer_name|@json_encode:321 nofilter}
            }
            {/if},
            "offers": {
              "@type": "Offer",
              "url": {$item.url|@json_encode:321 nofilter},
              "priceCurrency": {$currency.iso_code|@json_encode:321 nofilter},
              "price": {$item.price_amount|@json_encode:321 nofilter},
              "availability": {$item.seo_availability|@json_encode:321 nofilter}
            }
          }
        }
      {/if}
    {/foreach}
    ]
  }
</script>
