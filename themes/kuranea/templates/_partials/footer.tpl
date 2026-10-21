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

<nav class="kuranea-mobile-nav" aria-label="{l s='Store navigation' d='Shop.Theme.Kuranea'}">
  <a href="{$urls.pages.index}" class="kuranea-mobile-nav__item" aria-label="{l s='Home' d='Shop.Theme.Kuranea'}">
    <i class="material-icons" aria-hidden="true">&#xe88a;</i>
    <span>{l s='Home' d='Shop.Theme.Kuranea'}</span>
  </a>
  <a href="{$urls.pages.search}" class="kuranea-mobile-nav__item" aria-label="{l s='Search' d='Shop.Theme.Kuranea'}">
    <i class="material-icons" aria-hidden="true">&#xe8b6;</i>
    <span>{l s='Search' d='Shop.Theme.Kuranea'}</span>
  </a>
  <a href="{$urls.pages.my_account}" class="kuranea-mobile-nav__item" aria-label="{l s='Account' d='Shop.Theme.Kuranea'}">
    <i class="material-icons" aria-hidden="true">&#xe853;</i>
    <span>{l s='Account' d='Shop.Theme.Kuranea'}</span>
  </a>
  <a href="{$urls.pages.cart}" class="kuranea-mobile-nav__item" aria-label="{l s='Cart' d='Shop.Theme.Kuranea'}">
    <i class="material-icons" aria-hidden="true">&#xe8cc;</i>
    <span>{l s='Cart' d='Shop.Theme.Kuranea'}</span>
  </a>
</nav>
