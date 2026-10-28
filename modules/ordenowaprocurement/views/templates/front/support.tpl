{extends file='page.tpl'}
{block name='page_title'}{$ordenowa_support.copy.title|escape:'htmlall':'UTF-8'}{/block}
{block name='page_content'}
<section class="ordenowa-support container" data-testid="support-thread">
  {if $ordenowa_support.error}
    <p class="alert alert-danger" role="alert" data-testid="support-error">{$ordenowa_support.error|escape:'htmlall':'UTF-8'}</p>
  {/if}
  {if $ordenowa_support.allowed}
    <p><a href="{$ordenowa_support.back_url|escape:'htmlall':'UTF-8'}">{$ordenowa_support.copy.back|escape:'htmlall':'UTF-8'}</a></p>
    <p>{$ordenowa_support.copy.intro|escape:'htmlall':'UTF-8'}</p>
    <p class="text-muted">{$ordenowa_support.copy.latest|escape:'htmlall':'UTF-8'}</p>
    <div aria-live="polite">
      {foreach from=$ordenowa_support.messages item=message}
        <article class="card mb-3">
          <div class="card-body">
            <p><strong>{if $message.sender == 'operator'}{$ordenowa_support.copy.operator|escape:'htmlall':'UTF-8'}{else}{$ordenowa_support.copy.you|escape:'htmlall':'UTF-8'}{/if}</strong> <time>{$message.date|escape:'htmlall':'UTF-8'}</time></p>
            <p class="text-break" style="white-space:pre-wrap" data-testid="support-message-body">{$message.body|escape:'htmlall':'UTF-8'}</p>
          </div>
        </article>
      {foreachelse}
        <p>{$ordenowa_support.copy.empty|escape:'htmlall':'UTF-8'}</p>
      {/foreach}
    </div>
    <form method="post" action="{$ordenowa_support.url|escape:'htmlall':'UTF-8'}">
      <input type="hidden" name="action" value="message">
      <input type="hidden" name="id_request" value="{$ordenowa_support.id_request|escape:'htmlall':'UTF-8'}">
      <input type="hidden" name="token" value="{$ordenowa_support.token|escape:'htmlall':'UTF-8'}">
      <input type="hidden" name="idempotency_key" value="{$ordenowa_support.idempotency_key|escape:'htmlall':'UTF-8'}">
      <label for="ordenowa-support-message">{$ordenowa_support.copy.message|escape:'htmlall':'UTF-8'}</label>
      <textarea class="form-control" id="ordenowa-support-message" name="message" rows="6" maxlength="2000" required aria-describedby="ordenowa-support-limit" data-testid="support-message"></textarea>
      <p id="ordenowa-support-limit">{$ordenowa_support.copy.limit|escape:'htmlall':'UTF-8'}</p>
      <button class="btn btn-primary" type="submit" data-testid="support-send">{$ordenowa_support.copy.send|escape:'htmlall':'UTF-8'}</button>
    </form>
  {/if}
</section>
{/block}
