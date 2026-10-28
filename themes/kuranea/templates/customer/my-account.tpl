{extends file='parent:customer/my-account.tpl'}

{block name='page_content'}
  {if !empty($ordenowaProcurementEnabled)}
    <div class="account-menu account-menu--main">
      <a class="account-menu__link ordenowa-workspace-link" href="{$ordenowaWorkspaceUrl|escape:'htmlall':'UTF-8'}">{$ordenowaWorkspaceLabel|escape:'htmlall':'UTF-8'}</a>
      <a class="account-menu__link" id="identity_main_link" href="{$urls.pages.identity}">{l s='Information' d='Shop.Theme.Customeraccount'}</a>
      <a class="account-menu__link" href="{$urls.pages.contact}">{l s='Contact us' d='Shop.Theme.Global'}</a>
      {hook h='displayCustomerAccount' mod='kuraneapush'}
      <a class="account-menu__link account-menu__link--signout" href="{$urls.actions.logout}">{l s='Sign out' d='Shop.Theme.Actions'}</a>
    </div>
  {else}
    {$smarty.block.parent}
  {/if}
{/block}
