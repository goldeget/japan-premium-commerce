{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
<section id="content" class="page-content page-content--not-found">
  {block name='page_content'}
    {block name='error_content'}
      {if isset($errorContent)}
        {$errorContent nofilter}

        <a href="{$urls.pages.index}" class="btn btn-primary">
          <i class="material-icons" aria-hidden="true">&#xE5C4;</i>
          {if $language.locale == 'ja-JP'}ホームへ戻る
          {elseif $language.locale == 'ko-KR'}홈으로 돌아가기
          {else}{l s='Back to Home page' d='Shop.Theme.Catalog'}{/if}
        </a>
      {else}
        {if $language.locale == 'ja-JP'}
          <h1 class="h2">お探しのページはご利用いただけません。</h1>
          <p>ページが見つかりませんでした。トップページから商品をご覧ください。</p>
          <a class="btn btn-primary" href="{$urls.pages.index}">商品を見る<i class="material-icons" aria-hidden="true">&#xE5C8;</i></a>
        {elseif $language.locale == 'ko-KR'}
          <h1 class="h2">요청하신 페이지를 찾을 수 없습니다.</h1>
          <p>페이지가 더 이상 제공되지 않습니다. 홈에서 상품을 둘러보세요.</p>
          <a class="btn btn-primary" href="{$urls.pages.index}">상품 둘러보기<i class="material-icons" aria-hidden="true">&#xE5C8;</i></a>
        {else}
          <h1 class="h2">{l s='The page you are looking for is no longer available' d='Shop.Theme.Catalog'}</h1>
          <p>{l s='It can not be reached anymore. Can we still attract you into our shop?' d='Shop.Theme.Catalog'}</p>
          <a class="btn btn-primary" href="{$urls.pages.index}">
            {l s='Go shopping' d='Shop.Theme.Catalog'}
            <i class="material-icons" aria-hidden="true">&#xE5C8;</i>
          </a>
        {/if}
      {/if}
    {/block}

    {block name='hook_not_found'}
      {hook h='displayNotFound'}
    {/block}
  {/block}
</section>
