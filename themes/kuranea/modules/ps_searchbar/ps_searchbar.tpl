{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
{if $language.locale == 'ja-JP'}
  {$searchLabel = '商品検索'}
  {$searchPlaceholder = '商品名・キーワードで検索'}
  {$clearLabel = '検索を消去'}
  {$resultsLabel = '検索結果'}
  {$showSearchLabel = '検索を開く'}
  {$closeSearchLabel = '検索を閉じる'}
  {$cancelLabel = 'キャンセル'}
{elseif $language.locale == 'ko-KR'}
  {$searchLabel = '상품 검색'}
  {$searchPlaceholder = '상품명 또는 키워드 검색'}
  {$clearLabel = '검색어 지우기'}
  {$resultsLabel = '검색 결과'}
  {$showSearchLabel = '검색 열기'}
  {$closeSearchLabel = '검색 닫기'}
  {$cancelLabel = '취소'}
{else}
  {$searchLabel = 'Search'}
  {$searchPlaceholder = 'Search products...'}
  {$clearLabel = 'Clear search'}
  {$resultsLabel = 'Search results'}
  {$showSearchLabel = 'Show search bar'}
  {$closeSearchLabel = 'Close search'}
  {$cancelLabel = 'Cancel'}
{/if}

<div id="_desktop_ps_searchbar" class="order-2 ms-auto col-auto d-none d-md-flex align-items-center">
  <div id="ps_searchbar" class="ps-searchbar js-search-widget" data-search-controller-url="{$search_controller_url}">
    <form class="ps-searchbar__form" method="get" action="{$search_controller_url}" role="search">
      <input type="hidden" name="controller" value="search">
      <i class="material-icons ps-searchbar__magnifier js-search-icon" aria-hidden="true">&#xE8B6;</i>
      <label for="ps_searchbar_input" class="visually-hidden">{$searchLabel|escape:'htmlall':'UTF-8'}</label>
      <input
        class="js-search-input form-control ps-searchbar__input"
        type="text"
        name="s"
        value="{$search_string|escape:'htmlall':'UTF-8'}"
        placeholder="{$searchPlaceholder|escape:'htmlall':'UTF-8'}"
        id="ps_searchbar_input"
        autocomplete="off"
        role="combobox"
        aria-haspopup="listbox"
        aria-autocomplete="list"
        aria-controls="ps_searchbar_results"
        aria-expanded="false"
      >
      <button type="button" class="ps-searchbar__clear js-search-clear btn outline outline--rounded d-none" aria-label="{$clearLabel|escape:'htmlall':'UTF-8'}">
        <i class="material-icons" aria-hidden="true">&#xE14C;</i>
      </button>
    </form>

    <div
      class="ps-searchbar__dropdown js-search-dropdown d-none"
      id="ps_searchbar_dropdown"
      aria-label="{$resultsLabel|escape:'htmlall':'UTF-8'}"
      tabindex="-1"
    >
      <div class="ps-searchbar__results js-search-results" id="ps_searchbar_results" role="listbox" tabindex="-1"></div>
    </div>
  </div>
</div>

<template id="ps_searchbar_result" class="js-search-template">
  <a data-ps-ref="searchbar-result-link" class="ps-searchbar__result-link" id="" href="">
    <img src="" alt="" class="ps-searchbar__result-image">
    <p class="ps-searchbar__result-name"></p>
  </a>
</template>

{* MOBILE SEARCH BAR *}
<div class="ps-searchbar--mobile d-md-none d-flex col-auto">
  <div class="header-block d-flex align-items-center">
    <a class="header-block__action-btn" href="#" role="button" data-bs-toggle="offcanvas" data-bs-target="#searchCanvas" aria-controls="searchCanvas" aria-label="{$showSearchLabel|escape:'htmlall':'UTF-8'}">
      <span class="material-icons header-block__icon" aria-hidden="true">&#xE8B6;</span>
    </a>
  </div>

  <div class="ps-searchbar__offcanvas js-search-offcanvas offcanvas offcanvas-top h-auto" tabindex="-1" id="searchCanvas" aria-labelledby="offcanvasTopLabel">
    <div class="offcanvas-header">
      <div id="_mobile_ps_searchbar" class="ps-searchbar__container"></div>
      <button type="button" class="btn btn-link" data-bs-dismiss="offcanvas" aria-label="{$closeSearchLabel|escape:'htmlall':'UTF-8'}">{$cancelLabel|escape:'htmlall':'UTF-8'}</button>
    </div>
  </div>
</div>
