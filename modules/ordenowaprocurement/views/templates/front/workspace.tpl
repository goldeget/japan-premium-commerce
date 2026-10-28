{extends file='page.tpl'}

{block name='head_seo_title'}{$ow.copy.title|escape:'htmlall':'UTF-8'} | ORDENOWA{/block}
{block name='head_seo_robots'}noindex, nofollow, noarchive{/block}
{block name='page_title'}{$ow.copy.title|escape:'htmlall':'UTF-8'}{/block}

{block name='page_content'}
<div class="ow-workspace" data-testid="workspace" data-csrf-token="{$ow.token|escape:'htmlall':'UTF-8'}">
  <header class="ow-intro">
    <p class="ow-eyebrow">ORDENOWA</p>
    <p>{$ow.copy.intro|escape:'htmlall':'UTF-8'}</p>
    <div class="ow-account-links"><a href="{$ow.account_url|escape:'htmlall':'UTF-8'}">{$ow.copy.account|escape:'htmlall':'UTF-8'}</a><a href="{$ow.support_url|escape:'htmlall':'UTF-8'}">{$ow.copy.support|escape:'htmlall':'UTF-8'}</a></div>
  </header>
  <nav class="ow-tabs" aria-label="{$ow.copy.title|escape:'htmlall':'UTF-8'}">
    {foreach from=$ow.nav key=tab item=url}
      <a href="{$url|escape:'htmlall':'UTF-8'}" {if $ow.view == $tab || ($tab == 'assignments' && ($ow.view == 'assignment' || $ow.view == 'confirm')) || ($tab == 'requests' && $ow.view == 'request')}aria-current="page"{/if}>{$ow.copy[$tab]|escape:'htmlall':'UTF-8'}</a>
    {/foreach}
  </nav>

  {if !$ow.error && ($ow.view == 'assignments' || $ow.view == 'requests')}
    <form method="get" action="{$ow.url|escape:'htmlall':'UTF-8'}" class="ow-search" role="search">
      {foreach from=$ow.search_hidden key=field item=value}{if $field != 'view' && $field != 'q' && $field != 'status' && $field != 'category' && $field != 'before_id'}<input type="hidden" name="{$field|escape:'htmlall':'UTF-8'}" value="{$value|escape:'htmlall':'UTF-8'}">{/if}{/foreach}
      <input type="hidden" name="view" value="{$ow.view|escape:'htmlall':'UTF-8'}"><input type="hidden" name="category" value="{$ow.category|escape:'htmlall':'UTF-8'}">
      <div class="ow-search-query"><label for="ow-query">{$ow.copy.search|escape:'htmlall':'UTF-8'}</label><input id="ow-query" type="search" name="q" value="{$ow.q|escape:'htmlall':'UTF-8'}" maxlength="100" data-testid="workspace-search"></div>
      <div><label for="ow-status">{$ow.copy.filter_status|escape:'htmlall':'UTF-8'}</label><select id="ow-status" name="status"><option value="">{$ow.copy.all_statuses|escape:'htmlall':'UTF-8'}</option>{foreach from=$ow.statuses item=status}<option value="{$status|escape:'htmlall':'UTF-8'}" {if $ow.status == $status}selected{/if}>{$ow.copy[$status]|escape:'htmlall':'UTF-8'}</option>{/foreach}</select></div>
      <button class="ow-button ow-button-secondary" type="submit">{$ow.copy.search_button|escape:'htmlall':'UTF-8'}</button>
    </form>
  {/if}

  {if $ow.error}
    <section class="ow-error" role="alert" data-testid="error" data-status="{$ow.error_status|escape:'htmlall':'UTF-8'}"><h2>{$ow.copy.error_title|escape:'htmlall':'UTF-8'}</h2><p>{$ow.error|escape:'htmlall':'UTF-8'}</p><a class="ow-button" href="{$ow.nav.assignments|escape:'htmlall':'UTF-8'}">{$ow.copy.back|escape:'htmlall':'UTF-8'}</a></section>
  {elseif $ow.view == 'assignments'}
    <h2>{$ow.copy.assignments|escape:'htmlall':'UTF-8'}</h2>
    {if $ow.categories}
      <nav class="ow-categories" aria-label="{$ow.copy.categories|escape:'htmlall':'UTF-8'}" data-testid="category-navigation">
        <a href="{$ow.nav.assignments|escape:'htmlall':'UTF-8'}" {if !$ow.category}aria-current="page"{/if}>{$ow.copy.all_categories|escape:'htmlall':'UTF-8'}</a>
        {include file='module:ordenowaprocurement/views/templates/front/categories.tpl' categoryNodes=$ow.categories}
      </nav>
    {/if}
    <div class="ow-product-grid">
    {foreach from=$ow.items item=product}
      <article class="ow-card" data-testid="assignment-card" data-assignment-id="{$product.id|escape:'htmlall':'UTF-8'}">
        {include file='module:ordenowaprocurement/views/templates/front/product.tpl' product=$product showGallery=false}
        <div class="ow-card-body"><span class="ow-status" data-status="{$product.status|escape:'htmlall':'UTF-8'}">{$product.status_label|escape:'htmlall':'UTF-8'}</span><h3><a href="{$product.url|escape:'htmlall':'UTF-8'}">{$product.name|escape:'htmlall':'UTF-8'}</a></h3>
          {if $product.categories}<p class="ow-meta">{foreach from=$product.categories item=category name=categories}{if !$smarty.foreach.categories.first} / {/if}{$category.name|escape:'htmlall':'UTF-8'}{/foreach}</p>{/if}
          {if $product.reference_price}<p class="ow-reference-price">{$ow.copy.reference_price|escape:'htmlall':'UTF-8'}: {$product.reference_price|escape:'htmlall':'UTF-8'}</p>{/if}
          {if $product.deadline}<p class="ow-meta">{$ow.copy.deadline|escape:'htmlall':'UTF-8'}: <time>{$product.deadline|escape:'htmlall':'UTF-8'} UTC</time></p>{/if}
          <a class="ow-button ow-button-secondary" href="{$product.url|escape:'htmlall':'UTF-8'}">{$ow.copy.details|escape:'htmlall':'UTF-8'}</a>
        </div>
      </article>
    {foreachelse}<p class="ow-empty">{if $ow.q || $ow.status || $ow.category || $ow.before_id}{$ow.copy.empty_search|escape:'htmlall':'UTF-8'}{else}{$ow.copy.empty_assignments|escape:'htmlall':'UTF-8'}{/if}</p>{/foreach}
    </div>

  {elseif $ow.view == 'assignment' || $ow.view == 'confirm'}
    <a class="ow-back" href="{$ow.nav.assignments|escape:'htmlall':'UTF-8'}">← {$ow.copy.back|escape:'htmlall':'UTF-8'}</a>
    {if $ow.view == 'confirm'}<h2>{$ow.copy.confirm_title|escape:'htmlall':'UTF-8'}</h2><p class="ow-confirm-help">{$ow.copy.confirm_help|escape:'htmlall':'UTF-8'}</p>{/if}
    <article class="ow-product-detail" data-testid="{if $ow.view == 'confirm'}confirm-request{else}assignment-detail{/if}" data-assignment-id="{$ow.item.id|escape:'htmlall':'UTF-8'}">
      {include file='module:ordenowaprocurement/views/templates/front/product.tpl' product=$ow.item showGallery=true}
      <div><span class="ow-status">{$ow.item.status_label|escape:'htmlall':'UTF-8'}</span><h2>{$ow.item.name|escape:'htmlall':'UTF-8'}</h2>
        {if $ow.item.categories}<p class="ow-meta">{foreach from=$ow.item.categories item=category name=detailCategories}{if !$smarty.foreach.detailCategories.first} / {/if}{$category.name|escape:'htmlall':'UTF-8'}{/foreach}</p>{/if}
        <dl class="ow-facts">
          {if $ow.item.reference}<dt>{$ow.copy.reference|escape:'htmlall':'UTF-8'}</dt><dd>{$ow.item.reference|escape:'htmlall':'UTF-8'}</dd>{/if}
          {if $ow.item.variant}<dt>{$ow.copy.variant|escape:'htmlall':'UTF-8'}</dt><dd>{$ow.item.variant|escape:'htmlall':'UTF-8'}</dd>{/if}
          {if $ow.item.reference_price}<dt>{$ow.copy.reference_price|escape:'htmlall':'UTF-8'}</dt><dd>{$ow.item.reference_price|escape:'htmlall':'UTF-8'}</dd>{/if}
          {if $ow.item.deadline}<dt>{$ow.copy.deadline|escape:'htmlall':'UTF-8'}</dt><dd><time>{$ow.item.deadline|escape:'htmlall':'UTF-8'} UTC</time></dd>{/if}
          <dt>{$ow.copy.max_quantity|escape:'htmlall':'UTF-8'}</dt><dd>{$ow.item.max_quantity|escape:'htmlall':'UTF-8'}</dd>
        </dl>
        {if $ow.item.instructions}<div class="ow-instructions"><h3>{$ow.copy.instructions|escape:'htmlall':'UTF-8'}</h3><p class="ow-preserve">{$ow.item.instructions|escape:'htmlall':'UTF-8'}</p></div>{/if}
        {if $ow.item.available}
          <form method="post" action="{$ow.url|escape:'htmlall':'UTF-8'}" class="ow-request-form">
            <input type="hidden" name="token" value="{$ow.token|escape:'htmlall':'UTF-8'}">
            <input type="hidden" name="id_assignment" value="{$ow.item.id|escape:'htmlall':'UTF-8'}">
            <input type="hidden" name="version" value="{$ow.item.version|escape:'htmlall':'UTF-8'}">
            {if $ow.view == 'confirm'}
              <input type="hidden" name="action" value="submit"><input type="hidden" name="quantity" value="{$ow.quantity|escape:'htmlall':'UTF-8'}"><input type="hidden" name="idempotency_key" value="{$ow.idempotency_key|escape:'htmlall':'UTF-8'}">
              <p class="ow-quantity-summary">{$ow.copy.quantity|escape:'htmlall':'UTF-8'} <strong data-testid="confirmed-quantity">{$ow.quantity|escape:'htmlall':'UTF-8'}</strong></p>
              <div class="ow-actions"><button type="submit" class="ow-button" data-testid="submit-request">{$ow.copy.submit|escape:'htmlall':'UTF-8'}</button><a href="{$ow.edit_url|escape:'htmlall':'UTF-8'}">{$ow.copy.edit|escape:'htmlall':'UTF-8'}</a></div>
            {else}
              <input type="hidden" name="action" value="confirm"><label for="ow-quantity">{$ow.copy.quantity|escape:'htmlall':'UTF-8'}</label><input id="ow-quantity" data-testid="quantity" name="quantity" type="number" min="1" max="{$ow.item.max_quantity|escape:'htmlall':'UTF-8'}" step="1" value="{$ow.item.default_quantity|escape:'htmlall':'UTF-8'}" required inputmode="numeric" aria-describedby="ow-quantity-help"><small id="ow-quantity-help">{$ow.copy.max_quantity|escape:'htmlall':'UTF-8'}: {$ow.item.max_quantity|escape:'htmlall':'UTF-8'}</small><button type="submit" class="ow-button" data-testid="review-request">{$ow.copy.continue|escape:'htmlall':'UTF-8'}</button>
            {/if}
          </form>
        {else}<p class="ow-empty">{$ow.copy.unavailable|escape:'htmlall':'UTF-8'}</p>{/if}
      </div>
      {if $ow.item.description}<section class="ow-description"><h3>{$ow.copy.description|escape:'htmlall':'UTF-8'}</h3><p class="ow-preserve">{$ow.item.description|escape:'htmlall':'UTF-8'}</p></section>{/if}
    </article>

  {elseif $ow.view == 'requests'}
    <h2>{$ow.copy.requests|escape:'htmlall':'UTF-8'}</h2><div class="ow-history">
    {foreach from=$ow.items item=request}
      <article class="ow-history-row" data-testid="request-row" data-request-id="{$request.id|escape:'htmlall':'UTF-8'}"><div><p class="ow-meta">{$ow.copy.request_number|escape:'htmlall':'UTF-8'} #{$request.id|escape:'htmlall':'UTF-8'} · <time>{$request.submitted_at|escape:'htmlall':'UTF-8'} UTC</time></p><h3><a href="{$request.url|escape:'htmlall':'UTF-8'}">{$request.name|escape:'htmlall':'UTF-8'}</a></h3><p>{$ow.copy.quantity|escape:'htmlall':'UTF-8'}: {$request.quantity|escape:'htmlall':'UTF-8'}</p></div><div><span class="ow-status" data-status="{$request.status|escape:'htmlall':'UTF-8'}">{$request.status_label|escape:'htmlall':'UTF-8'}</span><p class="ow-meta">{$request.point_status|escape:'htmlall':'UTF-8'}</p><a href="{$request.url|escape:'htmlall':'UTF-8'}">{$ow.copy.request_details|escape:'htmlall':'UTF-8'} →</a></div></article>
    {foreachelse}<p class="ow-empty">{if $ow.q || $ow.status || $ow.before_id}{$ow.copy.empty_search|escape:'htmlall':'UTF-8'}{else}{$ow.copy.empty_requests|escape:'htmlall':'UTF-8'}{/if}</p>{/foreach}</div>

  {elseif $ow.view == 'request'}
    <h2>{$ow.copy.request_details|escape:'htmlall':'UTF-8'}</h2><article class="ow-panel" data-testid="request-detail" data-request-id="{$ow.item.id|escape:'htmlall':'UTF-8'}"><p class="ow-meta">{$ow.copy.request_number|escape:'htmlall':'UTF-8'} #{$ow.item.id|escape:'htmlall':'UTF-8'}</p><h3>{$ow.item.name|escape:'htmlall':'UTF-8'}</h3><span class="ow-status" data-status="{$ow.item.status|escape:'htmlall':'UTF-8'}">{$ow.item.status_label|escape:'htmlall':'UTF-8'}</span><dl class="ow-facts"><dt>{$ow.copy.quantity|escape:'htmlall':'UTF-8'}</dt><dd>{$ow.item.quantity|escape:'htmlall':'UTF-8'}</dd><dt>{$ow.copy.submitted_at|escape:'htmlall':'UTF-8'}</dt><dd><time>{$ow.item.submitted_at|escape:'htmlall':'UTF-8'} UTC</time></dd><dt>{$ow.copy.points|escape:'htmlall':'UTF-8'}</dt><dd>{$ow.item.point_status|escape:'htmlall':'UTF-8'}</dd></dl>{if $ow.item.instructions}<h4>{$ow.copy.instructions|escape:'htmlall':'UTF-8'}</h4><p class="ow-preserve">{$ow.item.instructions|escape:'htmlall':'UTF-8'}</p>{/if}{if $ow.item.review_reason}<div class="ow-instructions"><h4>{$ow.copy.reason|escape:'htmlall':'UTF-8'}</h4><p class="ow-preserve">{$ow.item.review_reason|escape:'htmlall':'UTF-8'}</p>{if $ow.item.reviewed_at}<time class="ow-meta">{$ow.item.reviewed_at|escape:'htmlall':'UTF-8'} UTC</time>{/if}</div>{/if}<div class="ow-actions"><a href="{$ow.nav.requests|escape:'htmlall':'UTF-8'}">{$ow.copy.requests|escape:'htmlall':'UTF-8'} →</a><a class="ow-button ow-button-secondary" data-testid="request-support" href="{$ow.support_url|escape:'htmlall':'UTF-8'}">{$ow.copy.request_support|escape:'htmlall':'UTF-8'}</a></div></article>

  {elseif $ow.view == 'points'}
    <section class="ow-balance"><h2>{$ow.copy.balance|escape:'htmlall':'UTF-8'}</h2><p><strong data-testid="points-balance" data-balance="{$ow.balance|escape:'htmlall':'UTF-8'}">{$ow.balance|escape:'htmlall':'UTF-8'}</strong> <span>P</span></p><p class="ow-balance-help">{$ow.copy.point_help|escape:'htmlall':'UTF-8'}</p></section>
    <h2>{$ow.copy.point_history|escape:'htmlall':'UTF-8'}</h2><div class="ow-history">
    {foreach from=$ow.ledger item=entry}<article class="ow-history-row" id="ow-entry-{$entry.id|escape:'htmlall':'UTF-8'}" data-testid="ledger-entry" data-ledger-id="{$entry.id|escape:'htmlall':'UTF-8'}" data-delta="{$entry.delta|escape:'htmlall':'UTF-8'}" data-request-id="{$entry.request_id|escape:'htmlall':'UTF-8'}"><div><p class="ow-meta"><time>{$entry.created_at|escape:'htmlall':'UTF-8'} UTC</time> · {$ow.copy.entry|escape:'htmlall':'UTF-8'} #{$entry.id|escape:'htmlall':'UTF-8'}</p><h3>{$entry.type|escape:'htmlall':'UTF-8'}</h3><p class="ow-preserve">{$entry.reason|escape:'htmlall':'UTF-8'}</p><a href="{$entry.request_url|escape:'htmlall':'UTF-8'}">{$ow.copy.request_number|escape:'htmlall':'UTF-8'} #{$entry.request_id|escape:'htmlall':'UTF-8'}</a>{if $entry.original_entry}<p class="ow-meta"><a href="{$entry.original_url|escape:'htmlall':'UTF-8'}">{$ow.copy.original_entry|escape:'htmlall':'UTF-8'} #{$entry.original_entry|escape:'htmlall':'UTF-8'}</a></p>{/if}</div><strong class="ow-point-delta">{if $entry.delta > 0}+{/if}{$entry.delta|escape:'htmlall':'UTF-8'} P</strong></article>{foreachelse}<p class="ow-empty">{$ow.copy.empty_points|escape:'htmlall':'UTF-8'}</p>{/foreach}</div>

  {elseif $ow.view == 'notifications'}
    <h2>{$ow.copy.notifications|escape:'htmlall':'UTF-8'}</h2><div class="ow-history">{foreach from=$ow.notifications item=notification}<article class="ow-history-row" data-testid="notification"><div><p class="ow-meta"><time>{$notification.created_at|escape:'htmlall':'UTF-8'} UTC</time></p><h3><a href="{$notification.url|escape:'htmlall':'UTF-8'}">{$notification.label|escape:'htmlall':'UTF-8'}</a></h3></div></article>{foreachelse}<p class="ow-empty">{$ow.copy.empty_notifications|escape:'htmlall':'UTF-8'}</p>{/foreach}</div>
  {/if}
  {if !$ow.error && ($ow.next_url || $ow.before_id)}<nav class="ow-pagination" aria-label="{$ow.copy.pagination|escape:'htmlall':'UTF-8'}">{if $ow.before_id}<a href="{$ow.first_url|escape:'htmlall':'UTF-8'}">← {$ow.copy.first_page|escape:'htmlall':'UTF-8'}</a>{/if}{if $ow.next_url}<a class="ow-button ow-button-secondary" href="{$ow.next_url|escape:'htmlall':'UTF-8'}" rel="next" data-testid="next-page">{$ow.copy.next_page|escape:'htmlall':'UTF-8'} →</a>{/if}</nav>{/if}
</div>
{/block}
