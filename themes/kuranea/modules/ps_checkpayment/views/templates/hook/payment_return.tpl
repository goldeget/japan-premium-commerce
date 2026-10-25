{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}

<div class="card border-1 mb-3">
  <div class="card-body">
    <h2>{l s='Payment information' d='Shop.Theme.Kuranea'}</h2>

    <p class="h3 card-subtitle text-secondary mb-3">{l s='Pay by Check' d='Shop.Theme.Kuranea'}</p>

    {if $status === 'ok'}
      <p>
        {l s='You have chosen payment by check.' d='Shop.Theme.Kuranea'}<br/>
        {l s='Your check must include following details:' d='Shop.Theme.Kuranea'}
      </p>

      <dl class="dl-list mb-3">
        <dt>{l s='Payment amount' d='Shop.Theme.Kuranea'}</dt>
        <dd>{$total_to_pay}</dd>
        <dt>{l s='Payable to the order of' d='Shop.Theme.Kuranea'}</dt>
        <dd>{if $checkName}{$checkName}{else}___________{/if}</dd>
        <dt>{l s='Mail to' d='Shop.Theme.Kuranea'}</dt>
        <dd>{if $checkAddress}{$checkAddress nofilter}{else}___________{/if}</dd>
      </dl>

      <p class="mb-0">
        {if !isset($reference)}
            {l s='Do not forget to insert your order number #%d.' sprintf=[$id_order] d='Shop.Theme.Kuranea'}<br aria-hidden="true">
        {else}
            {l s='Do not forget to insert your order reference %s.' sprintf=[$reference] d='Shop.Theme.Kuranea'}<br aria-hidden="true">
        {/if}
        {l s='An email has been sent to you with this information.' d='Shop.Theme.Kuranea'}<br aria-hidden="true">
        {l s='Your order will be sent as soon as we receive your payment.' d='Shop.Theme.Kuranea'}
      </p>
    {else}
      <div class="alert alert-warning mb-0" role="alert">
        {l s='We have noticed that there is a problem with your order. If you think this is an error, you can contact our' d='Shop.Theme.Kuranea'}
        <a class="alert-link" href="{$link->getPageLink('contact', true)|escape:'html'}">{l s='customer service department.' d='Shop.Theme.Kuranea'}</a>
      </div>
    {/if}
  </div>

  {if $status === 'ok'}
    <div class="card-footer p-3 border-1">
      {l s='For any questions or for further information, please contact our' d='Shop.Theme.Kuranea'}
      <a href="{$link->getPageLink('contact', true)|escape:'html'}">{l s='customer service department.' d='Shop.Theme.Kuranea'}</a>
    </div>
  {/if}
</div>
