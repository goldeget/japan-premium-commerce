{* Functional labels are source-controlled; seller notice is escaped plain text. *}
{assign var=push_locale value=$ordenowa_push_locale|default:'ja'}
{if $push_locale == 'en'}
  {assign var=push_title value='Browser notifications'}
  {assign var=push_consent value='I agree to the notice above and want to enable browser notifications.'}
  {assign var=push_enable value='Enable notifications'}
  {assign var=push_disable value='Revoke on all devices'}
  {assign var=push_unavailable value='New notification subscriptions are currently unavailable.'}
  {assign var=push_saved value='A notification subscription is saved for this account.'}
  {assign var=push_setup value='Notification settings are being prepared.'}
{elseif $push_locale == 'ko'}
  {assign var=push_title value='브라우저 알림'}
  {assign var=push_consent value='위 안내에 동의하고 브라우저 알림을 사용합니다.'}
  {assign var=push_enable value='알림 사용'}
  {assign var=push_disable value='모든 기기에서 동의 철회'}
  {assign var=push_unavailable value='현재 새 알림 구독을 사용할 수 없습니다.'}
  {assign var=push_saved value='이 계정에 저장된 알림 구독이 있습니다.'}
  {assign var=push_setup value='알림 설정을 준비 중입니다.'}
{else}
  {assign var=push_locale value='ja'}
  {assign var=push_title value='ブラウザー通知'}
  {assign var=push_consent value='上記の案内に同意し、ブラウザー通知を有効にします。'}
  {assign var=push_enable value='通知を有効にする'}
  {assign var=push_disable value='すべての端末で同意を取り消す'}
  {assign var=push_unavailable value='現在、新しい通知の登録は利用できません。'}
  {assign var=push_saved value='このアカウントには通知の登録が保存されています。'}
  {assign var=push_setup value='通知の設定を準備しています。'}
{/if}
<section class="ordenowa-push" data-ordenowa-push
  data-status-url="{$ordenowa_push_status_url|escape:'htmlall':'UTF-8'}"
  data-subscription-url="{$ordenowa_push_subscription_url|escape:'htmlall':'UTF-8'}"
  data-token="{$ordenowa_push_token|escape:'htmlall':'UTF-8'}"
  data-locale="{$push_locale|escape:'htmlall':'UTF-8'}"
  data-can-subscribe="{if $ordenowa_push_can_subscribe}1{else}0{/if}"
  data-active="{if $ordenowa_push_active}1{else}0{/if}"
  {if isset($ordenowa_push_application_server_key)}data-application-server-key="{$ordenowa_push_application_server_key|escape:'htmlall':'UTF-8'}"{/if}
  lang="{$push_locale|escape:'htmlall':'UTF-8'}">
  <h2 class="ordenowa-push__title">{$push_title|escape:'htmlall':'UTF-8'}</h2>
  {if $ordenowa_push_consent_notice != ''}
    <p class="ordenowa-push__notice" data-push-notice>{$ordenowa_push_consent_notice|escape:'htmlall':'UTF-8'}</p>
    <label class="ordenowa-push__consent">
      <input type="checkbox" data-push-consent autocomplete="off">
      <span>{$push_consent|escape:'htmlall':'UTF-8'}</span>
    </label>
  {else}
    <p class="ordenowa-push__notice">{$push_setup|escape:'htmlall':'UTF-8'}</p>
    <label class="ordenowa-push__consent">
      <input type="checkbox" data-push-consent autocomplete="off" disabled>
      <span>{$push_consent|escape:'htmlall':'UTF-8'}</span>
    </label>
  {/if}
  <p class="ordenowa-push__status" data-push-status role="status" aria-live="polite" aria-atomic="true">{if $ordenowa_push_active}{$push_saved|escape:'htmlall':'UTF-8'} {/if}{$push_unavailable|escape:'htmlall':'UTF-8'}</p>
  <div class="ordenowa-push__actions">
    <button class="btn btn-primary" type="button" data-push-enable disabled>{$push_enable|escape:'htmlall':'UTF-8'}</button>
    <button class="btn btn-outline-secondary" type="button" data-push-disable{if !$ordenowa_push_active} disabled{/if}>{$push_disable|escape:'htmlall':'UTF-8'}</button>
  </div>
</section>
