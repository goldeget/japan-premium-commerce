{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
{capture name="footer_before"}{hook h='displayFooterBefore'}{/capture}
{if $smarty.capture.footer_before}
  {block name='hook_footer_before'}
    <div class="footer footer__before">
      {$smarty.capture.footer_before nofilter}
    </div>
  {/block}
{/if}

{block name='footer_main'}
  <div class="footer footer__main">
    <div class="container">
      {capture name="footer_main_top"}{hook h='displayFooter'}{/capture}
      {if $smarty.capture.footer_main_top}
        {block name='hook_footer_main'}
          <div class="footer__main-top row">
            {$smarty.capture.footer_main_top nofilter}
          </div>
        {/block}
      {/if}

      {capture name="footer_main_bottom"}{hook h='displayFooterAfter'}{/capture}
      {if isset($smarty.capture.footer_main_bottom) && $smarty.capture.footer_main_bottom}
        {block name='hook_footer_after'}
          <div class="footer__main-bottom row">
            {$smarty.capture.footer_main_bottom nofilter}
          </div>
        {/block}
      {/if}

      {include file='_partials/copyright.tpl'}
    </div>
  </div>
{/block}

{if $language.locale == 'ja-JP'}
  {$mobileNavLabel = 'ストアメニュー'}
  {$mobileHome = 'ホーム'}
  {$mobileSearch = '検索'}
  {$mobileAccount = 'マイページ'}
  {$mobileCart = 'カート'}
{elseif $language.locale == 'ko-KR'}
  {$mobileNavLabel = '쇼핑 메뉴'}
  {$mobileHome = '홈'}
  {$mobileSearch = '검색'}
  {$mobileAccount = '내 계정'}
  {$mobileCart = '장바구니'}
{else}
  {$mobileNavLabel = 'Store navigation'}
  {$mobileHome = 'Home'}
  {$mobileSearch = 'Search'}
  {$mobileAccount = 'Account'}
  {$mobileCart = 'Cart'}
{/if}
<nav class="kuranea-mobile-nav" aria-label="{$mobileNavLabel|escape:'htmlall':'UTF-8'}">
  <a href="{$urls.pages.index}" class="kuranea-mobile-nav__item" aria-label="{$mobileHome|escape:'htmlall':'UTF-8'}">
    <i class="material-icons" aria-hidden="true">&#xe88a;</i>
    <span>{$mobileHome|escape:'htmlall':'UTF-8'}</span>
  </a>
  <a href="{$urls.pages.search}" class="kuranea-mobile-nav__item" aria-label="{$mobileSearch|escape:'htmlall':'UTF-8'}">
    <i class="material-icons" aria-hidden="true">&#xe8b6;</i>
    <span>{$mobileSearch|escape:'htmlall':'UTF-8'}</span>
  </a>
  <a href="{$urls.pages.my_account}" class="kuranea-mobile-nav__item" aria-label="{$mobileAccount|escape:'htmlall':'UTF-8'}">
    <i class="material-icons" aria-hidden="true">&#xe853;</i>
    <span>{$mobileAccount|escape:'htmlall':'UTF-8'}</span>
  </a>
  <a href="{$urls.pages.cart}" class="kuranea-mobile-nav__item" aria-label="{$mobileCart|escape:'htmlall':'UTF-8'}">
    <i class="material-icons" aria-hidden="true">&#xe8cc;</i>
    <span>{$mobileCart|escape:'htmlall':'UTF-8'}</span>
  </a>
</nav>
