{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}

{$ordenowaSearchActionTarget = '--search_term_string--'|str_replace:'{search_term_string}':$link->getPageLink('search', true, null, ['search_query' => '--search_term_string--'])}

<script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": {$ordenowaBrandName|@json_encode:321 nofilter},
    "url": {$urls.pages.index|@json_encode:321 nofilter}
    {if $ordenowaLogoDesktop},
    "logo": {
      "@type": "ImageObject",
      "url": {$ordenowaLogoDesktop|@json_encode:321 nofilter}
    }
    {/if}
  }
</script>

<script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "isPartOf": {
      "@type": "WebSite",
      "url": {$urls.pages.index|@json_encode:321 nofilter},
      "name": {$ordenowaBrandName|@json_encode:321 nofilter}
    },
    "name": {$page.meta.title|@json_encode:321 nofilter},
    "url": {$urls.current_url|@json_encode:321 nofilter}
  }
</script>

{if $page.page_name == 'index'}
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "url": {$urls.pages.index|@json_encode:321 nofilter},
      "name": {$ordenowaBrandName|@json_encode:321 nofilter},
      {if $ordenowaLogoDesktop}
      "image": {
        "@type": "ImageObject",
        "url": {$ordenowaLogoDesktop|@json_encode:321 nofilter}
      },
      {/if}
      "potentialAction": {
        "@type": "SearchAction",
        "target": {$ordenowaSearchActionTarget|@json_encode:321 nofilter},
        "query-input": "required name=search_term_string"
      }
    }
  </script>
{/if}

{if isset($breadcrumb.links[1])}
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {foreach from=$breadcrumb.links item=path name=breadcrumb}
          {
            "@type": "ListItem",
            "position": {$smarty.foreach.breadcrumb.iteration|@json_encode:321 nofilter},
            "name": {$path.title|@json_encode:321 nofilter},
            "item": {$path.url|@json_encode:321 nofilter}
          }{if !$smarty.foreach.breadcrumb.last},{/if}
        {/foreach}
      ]
    }
  </script>
{/if}
