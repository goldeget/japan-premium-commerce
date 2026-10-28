{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}

{$headerBanner = 'header-banner'}
{$headerTop = 'header-top'}
{$headerBottom = 'header-bottom'}
{$headerNavFullWidth = 'header-nav-full-width'}

{capture name="header_banner"}{hook h='displayBanner'}{/capture}
{block name='header_banner'}
  {if !empty($smarty.capture.header_banner)}
    <div class="{$headerBanner}">
      {$smarty.capture.header_banner nofilter}
    </div>
  {/if}
{/block}

{capture name="header_nav_1"}{hook h='displayNav1'}{/capture}
{capture name="header_nav_2"}{hook h='displayNav2'}{/capture}
{block name='header_nav'}
  {if !empty($smarty.capture.header_nav_1) || !empty($smarty.capture.header_nav_2)}
    <div class="{$headerTop} d-none d-md-block">
      <div class="container-md">
        <div class="row">
          <div class="{$headerTop}__left col-md-4">
            {$smarty.capture.header_nav_1 nofilter}
          </div>

          <div class="{$headerTop}__right col-md-8">
            {$smarty.capture.header_nav_2 nofilter}
          </div>
        </div>
      </div>
    </div>
  {/if}
{/block}

{block name='header_bottom'}
  <div class="{$headerBottom}">
    <div class="{$headerBottom}__container container-md">
      <div class="{$headerBottom}__row row gx-2 gx-md-4 align-items-stretch">
        <div class="{$headerBottom}__logo d-flex align-items-center col-auto me-auto me-md-0">
          <a class="navbar-brand kuranea-brand d-block" href="{$urls.pages.index}" aria-label="{$ordenowaBrandName|default:$shop.name|escape:'htmlall':'UTF-8'}">
            {if $ordenowaLogoDesktop}
              <picture>
                {if $ordenowaLogoMobile}<source media="(max-width: 767.98px)" srcset="{$ordenowaLogoMobile|escape:'htmlall':'UTF-8'}">{/if}
                <img class="logo img-fluid kuranea-brand__image" src="{$ordenowaLogoDesktop|escape:'htmlall':'UTF-8'}" alt="{$ordenowaBrandName|default:$shop.name|escape:'htmlall':'UTF-8'}" fetchpriority="high">
              </picture>
            {else}
              <span class="ordenowa-brand__text">{$ordenowaBrandName|default:$shop.name|escape:'htmlall':'UTF-8'}</span>
            {/if}
          </a>
        </div>

        {if !empty($ordenowaProcurementEnabled)}
          <nav class="col d-flex align-items-center justify-content-end" aria-label="{$ordenowaWorkspaceLabel|escape:'htmlall':'UTF-8'}">
            <a class="btn btn-link ordenowa-workspace-link" href="{$ordenowaWorkspaceUrl|escape:'htmlall':'UTF-8'}">{$ordenowaWorkspaceLabel|escape:'htmlall':'UTF-8'}</a>
            <a class="btn btn-link" href="{$urls.pages.my_account}">{l s='Your account' d='Shop.Theme.Customeraccount'}</a>
          </nav>
        {else}
          {hook h='displayTop'}
        {/if}

        <div id="_mobile_ps_customersignin" class="d-md-none d-flex col-auto">
          {* JUST PLACEHOLDER FOR RESPONSIVE COMPONENT TO LOAD REAL ONE *}
          <div class="header-block">
            <a href="{$urls.pages.my_account}" class="header-block__action-btn">
              <i class="material-icons header-block__icon" aria-hidden="true">&#xE853;</i>
            </a>
          </div>
          {* JUST PLACEHOLDER FOR RESPONSIVE COMPONENT TO LOAD REAL ONE *}
        </div>

        {if !$configuration.is_catalog && empty($ordenowaProcurementEnabled)}
          <div id="_mobile_ps_shoppingcart" class="d-md-none d-flex col-auto">
            {* JUST PLACEHOLDER FOR RESPONSIVE COMPONENT TO LOAD REAL ONE *}
            <div class="header-block">
              <a href="{$urls.pages.cart}" class="header-block__action-btn">
                <i class="material-icons header-block__icon" aria-hidden="true">&#xE8CC;</i>
                <span class="header-block__badge">{$cart.products_count}</span>
              </a>
            </div>
            {* JUST PLACEHOLDER FOR RESPONSIVE COMPONENT TO LOAD REAL ONE *}
          </div>
        {/if}
      </div>
    </div>
  </div>

  {capture name="nav_full_width"}{if empty($ordenowaProcurementEnabled)}{hook h='displayNavFullWidth'}{/if}{/capture}
  {if !empty($smarty.capture.nav_full_width)}
    <div class="{$headerNavFullWidth}">
      {$smarty.capture.nav_full_width nofilter}
    </div>
  {/if}
{/block}
