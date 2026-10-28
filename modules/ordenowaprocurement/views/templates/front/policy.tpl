{extends file='page.tpl'}
{block name='head_seo_title'}{$ordenowa_policy_title|escape:'htmlall':'UTF-8'} | ORDENOWA{/block}
{block name='page_title'}{$ordenowa_policy_title|escape:'htmlall':'UTF-8'}{/block}
{block name='page_content'}
  <article class="ordenowa-service-policy" data-testid="procurement-public-policy">
    {if $ordenowa_policy_ready}
      {if !empty($ordenowa_policy_operator)}
        <p>{$ordenowa_policy_operator.operator_name|escape:'htmlall':'UTF-8'}</p>
        <p><a href="mailto:{$ordenowa_policy_operator.support_email|escape:'htmlall':'UTF-8'}">{$ordenowa_policy_operator.support_email|escape:'htmlall':'UTF-8'}</a></p>
        {if $ordenowa_policy_operator.support_phone}<p>{$ordenowa_policy_operator.support_phone|escape:'htmlall':'UTF-8'}</p>{/if}
        {if $ordenowa_policy_operator.support_url}<p><a href="{$ordenowa_policy_operator.support_url|escape:'htmlall':'UTF-8'}" rel="noopener noreferrer">{$ordenowa_policy_operator.support_url|escape:'htmlall':'UTF-8'}</a></p>{/if}
      {else}
        <div style="white-space:pre-wrap;overflow-wrap:anywhere">{$ordenowa_policy_text|escape:'htmlall':'UTF-8'}</div>
      {/if}
    {else}
      <p role="status">{$ordenowa_policy_unavailable|default:''|escape:'htmlall':'UTF-8'}</p>
    {/if}
  </article>
{/block}
