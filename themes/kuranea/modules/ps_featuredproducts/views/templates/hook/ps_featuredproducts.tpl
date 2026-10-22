{** KURANEA empty catalog copy; product cards remain Hummingbird's native output. **}
{extends file="components/module-products.tpl"}

{block name='module_products_name'}ps-featuredproducts{/block}

{block name='module_products_title'}
  {if $language.locale == 'ja-JP'}
    {include file='components/section-title.tpl' title='KURANEAのセレクション'}
  {elseif $language.locale == 'ko-KR'}
    {include file='components/section-title.tpl' title='KURANEA 셀렉션'}
  {else}
    {include file='components/section-title.tpl' title='The KURANEA edit'}
  {/if}
{/block}

{block name='module_products_list'}
  {if $products}
    <div class="module-products__list">
      {include file='catalog/_partials/productlist.tpl' products=$products}
    </div>
  {else}
    <div class="kuranea-catalog-empty" role="status" aria-live="polite">
      {if $language.locale == 'ja-JP'}
        <p class="kuranea-catalog-empty__message">ただいま、セレクションを準備しています。</p>
        <a class="kuranea-catalog-empty__link" href="{$urls.pages.search}">商品を探す <span aria-hidden="true">→</span></a>
      {elseif $language.locale == 'ko-KR'}
        <p class="kuranea-catalog-empty__message">첫 컬렉션을 준비하고 있습니다.</p>
        <a class="kuranea-catalog-empty__link" href="{$urls.pages.search}">상품 검색 <span aria-hidden="true">→</span></a>
      {else}
        <p class="kuranea-catalog-empty__message">We're preparing our first collection.</p>
        <a class="kuranea-catalog-empty__link" href="{$urls.pages.search}">Search the store <span aria-hidden="true">→</span></a>
      {/if}
    </div>
  {/if}
{/block}

{block name='module_products_footer'}
  {if $products}
    <a class="btn btn-outline-primary" href="{$allProductsLink}">
      {if $language.locale == 'ja-JP'}すべての商品を見る{elseif $language.locale == 'ko-KR'}모든 상품 보기{else}View all products{/if}
      <i class="material-icons" aria-hidden="true">&#xE315;</i>
    </a>
  {/if}
{/block}
