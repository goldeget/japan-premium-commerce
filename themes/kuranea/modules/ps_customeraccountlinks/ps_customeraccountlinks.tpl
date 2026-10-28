{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
<nav
  class="ps-customeraccountlinks footer-block col-md-6 col-lg-3"
  role="navigation"
  aria-labelledby="footer_customeraccount_title">
  <p
    id="footer_customeraccount_title"
    class="footer-block__title footer-block__title--toggle"
  >
    <a href="{$urls.pages.my_account}" rel="nofollow">
      {if $language.locale == 'ja-JP'}アカウント
      {elseif $language.locale == 'ko-KR'}내 계정
      {else}{l s='Your account' d='Shop.Theme.Customeraccount'}{/if}
    </a>
    <button
      class="stretched-link collapsed d-md-none"
      type="button"
      aria-expanded="false"
      aria-controls="footer_customeraccountlinks"
      data-bs-target="#footer_customeraccountlinks"
      data-bs-toggle="collapse"
    >
      <span class="visually-hidden">
        {if $language.locale == 'ja-JP'}アカウントリンクを開閉
        {elseif $language.locale == 'ko-KR'}계정 링크 열기/닫기
        {else}{l s='Toggle your account links' d='Shop.Theme.Customeraccount'}{/if}
      </span>
      <i class="material-icons" aria-hidden="true">&#xE313;</i>
    </button>
  </p>

  <div class="footer-block__content collapse" id="footer_customeraccountlinks">
    <ul class="footer-block__list">
      {if $customer.is_logged}
        <li>
          <a href="{$urls.pages.identity}" rel="nofollow">
            {l s='Information' d='Shop.Theme.Customeraccount'}
          </a>
        </li>

        {if empty($ordenowaProcurementEnabled)}
        {if $customer.addresses|count}
          <li>
            <a href="{$urls.pages.addresses}" rel="nofollow">
              {l s='Addresses' d='Shop.Theme.Customeraccount'}
            </a>
          </li>
        {else}
          <li>
            <a href="{$urls.pages.address}" rel="nofollow">
              {l s='Add first address' d='Shop.Theme.Customeraccount'}
            </a>
          </li>
        {/if}

        {if !$configuration.is_catalog}
          <li>
            <a href="{$urls.pages.history}" rel="nofollow">
              {l s='Orders' d='Shop.Theme.Customeraccount'}
            </a>
          </li>
        {/if}

        {if !$configuration.is_catalog}
          <li>
            <a href="{$urls.pages.order_slip}" rel="nofollow">
              {l s='Credit slips' d='Shop.Theme.Customeraccount'}
            </a>
          </li>
        {/if}

        {if $configuration.voucher_enabled && !$configuration.is_catalog}
          <li>
            <a href="{$urls.pages.discount}" rel="nofollow">
              {l s='Vouchers' d='Shop.Theme.Customeraccount'}
            </a>
          </li>
        {/if}

        {if $configuration.return_enabled && !$configuration.is_catalog}
          <li>
            <a href="{$urls.pages.order_follow}" rel="nofollow">
              {l s='Merchandise returns' d='Shop.Theme.Customeraccount'}
            </a>
          </li>
        {/if}

        {/if}
        {hook h='displayMyAccountBlock'}

        <li>
          <a class="logout text-danger-on-dark" href="{$urls.actions.logout}" rel="nofollow">
            {l s='Sign out' d='Shop.Theme.Actions'}
          </a>
        </li>

      {else}
        {if empty($ordenowaProcurementEnabled)}
        <li>
          <a href="{$urls.pages.guest_tracking}" rel="nofollow">
            {if $language.locale == 'ja-JP'}注文状況の確認
            {elseif $language.locale == 'ko-KR'}주문 조회
            {else}{l s='Order tracking' d='Shop.Theme.Customeraccount'}{/if}
          </a>
        </li>
        {/if}
        <li>
          <a href="{$urls.pages.my_account}" rel="nofollow">
            {if $language.locale == 'ja-JP'}サインイン
            {elseif $language.locale == 'ko-KR'}로그인
            {else}{l s='Sign in' d='Shop.Theme.Actions'}{/if}
          </a>
        </li>
        <li>
          <a href="{$urls.pages.register}" rel="nofollow">
            {if $language.locale == 'ja-JP'}アカウントを作成
            {elseif $language.locale == 'ko-KR'}회원가입
            {else}{l s='Create an account' d='Shop.Theme.Customeraccount'}{/if}
          </a>
        </li>

        {hook h='displayMyAccountBlock'}
      {/if}
    </ul>
  </div>
</nav>
