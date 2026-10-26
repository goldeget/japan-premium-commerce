{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
{block name='head_charset'}
  <meta charset="utf-8">
{/block}

{block name='head_ie_compatibility'}
  <meta http-equiv="x-ua-compatible" content="ie=edge">
{/block}

{block name='head_seo'}
  {if $page.page_name == 'index'}
    {$ordenowaResolvedSeoTitle = $ordenowaSeoTitle|default:$page.meta.title}
    {$ordenowaResolvedSeoDescription = $ordenowaSeoDescription|default:$page.meta.description}
  {else}
    {$ordenowaResolvedSeoTitle = $page.meta.title|default:$ordenowaSeoTitle}
    {$ordenowaResolvedSeoDescription = $page.meta.description|default:$ordenowaSeoDescription}
  {/if}

  {block name='head_preload'}
    {include file='_partials/preload.tpl'}
  {/block}

  <title>{block name='head_seo_title'}{$ordenowaResolvedSeoTitle|escape:'htmlall':'UTF-8'}{/block}</title>

  {block name='hook_after_title_tag'}
    {hook h='displayAfterTitleTag'}
  {/block}

  <meta name="description" content="{block name='head_seo_description'}{$ordenowaResolvedSeoDescription|escape:'htmlall':'UTF-8'}{/block}">

  {if $page.meta.robots !== 'index'}
    <meta name="robots" content="{$page.meta.robots|escape:'htmlall':'UTF-8'}">
  {/if}

  {block name='head_pagination_seo'}
    {include file='_partials/pagination-seo.tpl'}
  {/block}

  {if $page.canonical}
    <link rel="canonical" href="{$page.canonical|escape:'htmlall':'UTF-8'}">
  {/if}

  {block name='head_hreflang'}
    {foreach from=$urls.alternative_langs item=pageUrl key=code}
      <link rel="alternate" href="{$pageUrl|escape:'htmlall':'UTF-8'}" hreflang="{$code|escape:'htmlall':'UTF-8'}">
    {/foreach}
  {/block}

  {** Render structured data from the core. Available since PrestaShop 9.2 **}
  {if !empty($structured_data)}
    {foreach from=$structured_data item="element"}
      {** 321 means JSON_HEX_TAG (1) + JSON_UNESCAPED_SLASHES (64) + JSON_UNESCAPED_UNICODE (256); protects embedded structured data from literal </script> delimiters **}
    <script type="application/ld+json">{$element|@json_encode:321 nofilter}</script>
    {/foreach}

  {** Or render them in a legacy, manual way. This will be removed in future versions of this theme. **}
  {else}
    {block name='head_microdata'}
      {include file='_partials/microdata/head-jsonld.tpl'}
    {/block}
    {block name='head_microdata_special'}{/block}
  {/if}

  {block name='head_open_graph'}
    <meta property="og:title" content="{$ordenowaResolvedSeoTitle|escape:'htmlall':'UTF-8'}">
    <meta property="og:description" content="{$ordenowaResolvedSeoDescription|escape:'htmlall':'UTF-8'}">
    <meta property="og:url" content="{$urls.current_url|escape:'htmlall':'UTF-8'}">
    <meta property="og:site_name" content="{$ordenowaBrandName|default:$shop.name|escape:'htmlall':'UTF-8'}">
    {if !isset($product) && $page.page_name != 'product'}<meta property="og:type" content="website">{/if}
  {/block}
{/block}

{block name='head_viewport'}
  <meta name="viewport" content="width=device-width, initial-scale=1">
{/block}

{block name='head_icons'}
  <script defer src="{$urls.theme_assets|escape:'htmlall':'UTF-8'}js/pwa-register.js" data-service-worker="{$urls.base_url|escape:'htmlall':'UTF-8'}sw.js" data-scope="{$urls.base_url|escape:'htmlall':'UTF-8'}"></script>
  <script defer src="{$urls.theme_assets|escape:'htmlall':'UTF-8'}js/skip-to-main.js"></script>
{/block}

{block name='stylesheets'}
  {include file='_partials/stylesheets.tpl' stylesheets=$stylesheets}
{/block}

{block name='javascript_head'}
  {include file='_partials/javascript.tpl' javascript=$javascript.head vars=$js_custom_vars}
{/block}

{block name='hook_header'}
  {$HOOK_HEADER nofilter}
{/block}

{block name='hook_extra'}{/block}
