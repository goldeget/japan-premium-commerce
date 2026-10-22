{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
{if !empty($linkBlocks)}
  {foreach $linkBlocks as $linkBlock}
    <nav
      class="ps-linklist footer-block col-md-6 col-lg-3"
      aria-labelledby="footer_title_{$linkBlock.id}"
    >
      <p
        id="footer_title_{$linkBlock.id}"
        class="footer-block__title footer-block__title--toggle"
      >
        {$linkBlock.title}
        <button
          class="stretched-link collapsed d-md-none"
          type="button"
          aria-expanded="false"
          aria-controls="footer_linklist_{$linkBlock.id}"
          data-bs-target="#footer_linklist_{$linkBlock.id}"
          data-bs-toggle="collapse"
        >
          <span class="visually-hidden">
            {if $language.locale == 'ja-JP'}
              {if $linkBlock.title == '商品'}商品リンクを開閉
              {elseif $linkBlock.title == '当社について'}会社情報リンクを開閉
              {else}リンク一覧を開閉{/if}
            {elseif $language.locale == 'ko-KR'}
              {if $linkBlock.title == '상품'}상품 링크 열기/닫기
              {elseif $linkBlock.title == '우리 회사'}회사 정보 링크 열기/닫기
              {else}{$linkBlock.title} 링크 열기/닫기{/if}
            {else}
              {l s='Toggle %s links' sprintf=[$linkBlock.title|lower] d='Shop.Theme.Global'}
            {/if}
          </span>
          <i class="material-icons" aria-hidden="true">&#xE313;</i>
        </button>
      </p>

      <div class="footer-block__content collapse" id="footer_linklist_{$linkBlock.id}">
        <ul class="footer-block__list">
          {foreach $linkBlock.links as $link}
            {$footerLinkTitle = $link.title}
            {$footerLinkDescription = $link.description}
            {if $language.locale == 'ja-JP'}
              {if $link.id == 'link-product-page-prices-drop'}
                {$footerLinkTitle = '値下げ商品'}
                {$footerLinkDescription = '値下げ商品一覧です。'}
              {elseif $link.id == 'link-product-page-new-products'}
                {$footerLinkTitle = '新着商品'}
                {$footerLinkDescription = '新着商品一覧です。'}
              {elseif $link.id == 'link-product-page-best-sales'}
                {$footerLinkTitle = 'ベストセラー'}
                {$footerLinkDescription = '人気商品一覧です。'}
              {elseif $link.id == 'link-cms-page-1'}
                {$footerLinkDescription = '配送と送料についてご案内します。'}
              {elseif $link.id == 'link-cms-page-2'}
                {$footerLinkDescription = '特定商取引法に基づく販売者情報です。'}
              {elseif $link.id == 'link-cms-page-3'}
                {$footerLinkDescription = 'KURANEAのご利用規約です。'}
              {elseif $link.id == 'link-cms-page-4'}
                {$footerLinkDescription = 'KURANEAの会社概要です。'}
              {elseif $link.id == 'link-cms-page-5'}
                {$footerLinkDescription = 'ご利用いただけるお支払い方法をご案内します。'}
              {elseif $link.id == 'link-static-page-contact'}
                {$footerLinkDescription = 'お問い合わせフォームからご連絡ください。'}
              {elseif $link.id == 'link-static-page-sitemap'}
                {$footerLinkDescription = 'サイト内のページ一覧をご覧いただけます。'}
              {/if}
            {elseif $language.locale == 'ko-KR'}
              {if $link.id == 'link-product-page-prices-drop'}
                {$footerLinkTitle = '할인 상품'}
                {$footerLinkDescription = '할인 중인 상품을 확인하세요.'}
              {elseif $link.id == 'link-product-page-new-products'}
                {$footerLinkTitle = '신상품'}
                {$footerLinkDescription = '새로 등록된 상품을 확인하세요.'}
              {elseif $link.id == 'link-product-page-best-sales'}
                {$footerLinkTitle = '베스트셀러'}
                {$footerLinkDescription = '인기 상품을 확인하세요.'}
              {elseif $link.id == 'link-cms-page-1'}
                {$footerLinkTitle = '배송 안내'}
                {$footerLinkDescription = '배송 방법과 요금을 안내합니다.'}
              {elseif $link.id == 'link-cms-page-2'}
                {$footerLinkTitle = '특정상거래법상 표시'}
                {$footerLinkDescription = '일본 특정상거래법에 따른 판매자 정보입니다.'}
              {elseif $link.id == 'link-cms-page-3'}
                {$footerLinkTitle = '이용약관'}
                {$footerLinkDescription = 'KURANEA 이용약관을 확인하세요.'}
              {elseif $link.id == 'link-cms-page-4'}
                {$footerLinkTitle = '회사 소개'}
                {$footerLinkDescription = 'KURANEA 회사 소개입니다.'}
              {elseif $link.id == 'link-cms-page-5'}
                {$footerLinkTitle = '안전한 결제'}
                {$footerLinkDescription = '이용 가능한 결제 방법을 안내합니다.'}
              {elseif $link.id == 'link-static-page-contact'}
                {$footerLinkTitle = '문의하기'}
                {$footerLinkDescription = '문의 양식으로 연락해 주세요.'}
              {elseif $link.id == 'link-static-page-sitemap'}
                {$footerLinkTitle = '사이트맵'}
                {$footerLinkDescription = '사이트의 페이지 목록을 확인하세요.'}
              {/if}
            {/if}
            <li>
              <a
                id="{$link.id}-{$linkBlock.id}"
                class="{$link.class}"
                href="{$link.url}"
                {if !empty($link.target)} target="{$link.target}" {/if}
                {if !empty($footerLinkDescription)} aria-describedby="desc-{$link.id}-{$linkBlock.id}" {/if}
              >
                {$footerLinkTitle}
              </a>
              {if !empty($footerLinkDescription)}
                <span id="desc-{$link.id}-{$linkBlock.id}" class="visually-hidden">
                  {$footerLinkDescription}
                </span>
              {/if}
            </li>
          {/foreach}
        </ul>
      </div>
    </nav>
  {/foreach}
{/if}
