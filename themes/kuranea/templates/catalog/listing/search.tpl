{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
{extends file='catalog/listing/product-list.tpl'}

{block name='product_list'}
  {include file='catalog/_partials/products.tpl' listing=$listing}
{/block}

{block name='error_content'}
  {if $language.locale == 'ja-JP'}
    <p>検索条件に一致する商品が見つかりませんでした。</p>
    <ul>
      <li>検索語の入力をご確認ください。</li>
      <li>別のキーワードでお試しください。</li>
    </ul>
    <a class="btn btn-primary" href="{$urls.pages.index}">トップページへ戻る</a>
  {elseif $language.locale == 'ko-KR'}
    <p>검색 조건에 맞는 상품을 찾을 수 없습니다.</p>
    <ul>
      <li>검색어의 철자를 확인해 주세요.</li>
      <li>더 일반적이거나 다른 키워드로 검색해 주세요.</li>
    </ul>
    <a class="btn btn-primary" href="{$urls.pages.index}">홈으로 돌아가기</a>
  {else}
    <p>{l s='We couldn\'t find any matching products.' d='Shop.Theme.Catalog'}</p>
    <ul>
      <li>{l s='Check the spelling of your search term.' d='Shop.Theme.Catalog'}</li>
      <li>{l s='Try a more general or different keyword.' d='Shop.Theme.Catalog'}</li>
    </ul>
    <a class="btn btn-primary" href="{$urls.pages.index}">{l s='Back to home' d='Shop.Theme.Catalog'}</a>
  {/if}
{/block}

{block name='product_list_header'}
  {capture assign='title'}
    {if empty($search_string)}
      {if $language.locale == 'ja-JP'}検索キーワードを入力してください
      {elseif $language.locale == 'ko-KR'}검색어를 입력해 주세요
      {else}{l s='Nothing to search for' d='Shop.Theme.Catalog'}{/if}
    {elseif $listing.products|count}
      {if $language.locale == 'ja-JP'}「{$search_string|escape:'htmlall':'UTF-8'}」の検索結果
      {elseif $language.locale == 'ko-KR'}「{$search_string|escape:'htmlall':'UTF-8'}」검색 결과
      {else}{l s='Search results for "%search_term%"' sprintf=['%search_term%' => $search_string] d='Shop.Theme.Catalog'}{/if}
    {else}
      {if $language.locale == 'ja-JP'}「{$search_string|escape:'htmlall':'UTF-8'}」の商品は見つかりませんでした
      {elseif $language.locale == 'ko-KR'}「{$search_string|escape:'htmlall':'UTF-8'}」검색 결과가 없습니다
      {else}{l s='No search results for "%search_term%"' sprintf=['%search_term%' => $search_string] d='Shop.Theme.Catalog'}{/if}
    {/if}
  {/capture}

  <div id="js-product-list-header">
    {include file='components/page-title-section.tpl' title=$title}
  </div>
{/block}
