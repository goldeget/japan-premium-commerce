{** ORDENOWA storefront home. Product output remains PrestaShop's native module markup. **}
{extends file=$layout}

{block name='breadcrumb'}{/block}

{block name='content_columns'}
  {block name='left_column'}{/block}

  {block name='content_wrapper'}
    <div id="center-column" class="center-column page kuranea-home">
      {hook h="displayContentWrapperTop"}

      {block name='content'}
        {block name='page_content_container'}
          <div id="content" class="page-content page-content--home">
            {block name='page_content_top'}{/block}

            {block name='page_content'}
              {$copyBrandName = $ordenowaBrandName|default:'ORDENOWA'}
              {$copyBrandDescription = $ordenowaBrandDescription|default:''}
              {$copyBrandSlogan = $ordenowaBrandSlogan|default:''}
              {if $language.locale == 'ja-JP'}
                {$copyEyebrow = $copyBrandDescription}
                {$copyTitle = $copyBrandSlogan}
                {$copyLead = '企業向けの商品調達と受発注を支えるサービスです。'}
                {$copyExplore = '商品を見る'}
                {$copySearch = '商品を探す'}
                {$copyApproach = $copyBrandName|cat:'のサービス'}
                {$copyValueOneTitle = '商品を探す'}
                {$copyValueOneBody = '必要な商品情報を確認できます。'}
                {$copyValueTwoTitle = '条件を確認する'}
                {$copyValueTwoBody = '商品ごとの価格や取引条件をご案内します。'}
                {$copyValueThreeTitle = '受発注をつなぐ'}
                {$copyValueThreeBody = '企業と商品をつなぐ受発注サービスです。'}
                {$copyEdit = '商品カタログ'}
                {$copyNote = $copyBrandName}
                {$copyDiscover = '商品カタログを見る'}
              {elseif $language.locale == 'ko-KR'}
                {$copyEyebrow = $copyBrandDescription}
                {$copyTitle = $copyBrandSlogan}
                {$copyLead = '기업 고객을 위한 상품 조달과 발주 서비스를 제공합니다.'}
                {$copyExplore = '상품 보기'}
                {$copySearch = '상품 검색'}
                {$copyApproach = $copyBrandName|cat:' 서비스'}
                {$copyValueOneTitle = '상품 검색'}
                {$copyValueOneBody = '필요한 상품 정보를 확인할 수 있습니다.'}
                {$copyValueTwoTitle = '거래 조건 확인'}
                {$copyValueTwoBody = '상품별 가격과 거래 조건을 안내합니다.'}
                {$copyValueThreeTitle = '주문 연결'}
                {$copyValueThreeBody = '기업과 상품을 연결하는 발주 서비스입니다.'}
                {$copyEdit = '상품 카탈로그'}
                {$copyNote = $copyBrandName}
                {$copyDiscover = '상품 카탈로그 보기'}
              {else}
                {$copyEyebrow = $copyBrandDescription}
                {$copyTitle = $copyBrandSlogan}
                {$copyLead = 'Product sourcing and purchase order services for business customers.'}
                {$copyExplore = 'Browse products'}
                {$copySearch = 'Search the store'}
                {$copyApproach = $copyBrandName|cat:' services'}
                {$copyValueOneTitle = 'Find products'}
                {$copyValueOneBody = 'Review product information for your business.'}
                {$copyValueTwoTitle = 'Review terms'}
                {$copyValueTwoBody = 'See product pricing and transaction terms.'}
                {$copyValueThreeTitle = 'Connect orders'}
                {$copyValueThreeBody = 'A purchase order service connecting businesses and products.'}
                {$copyEdit = 'Product catalog'}
                {$copyNote = $copyBrandName}
                {$copyDiscover = 'Browse the catalog'}
              {/if}

              <section class="kuranea-hero" aria-labelledby="kuranea-home-title">
                <div class="container kuranea-hero__grid">
                  <div class="kuranea-hero__copy">
                    <p class="kuranea-eyebrow">{$copyEyebrow|escape:'htmlall':'UTF-8'}</p>
                    <h1 id="kuranea-home-title">{$copyTitle|escape:'htmlall':'UTF-8'}</h1>
                    <p class="kuranea-hero__lead">{$copyLead|escape:'htmlall':'UTF-8'}</p>
                    <div class="kuranea-hero__actions">
                      <a class="btn btn-primary kuranea-button" href="{$urls.pages.new_products}">{$copyExplore|escape:'htmlall':'UTF-8'}</a>
                      <a class="kuranea-text-link" href="{$urls.pages.search}">{$copySearch|escape:'htmlall':'UTF-8'} <span aria-hidden="true">→</span></a>
                    </div>
                  </div>
                  <div class="kuranea-hero__art" aria-hidden="true">
                    <div class="kuranea-hero__frame">
                      <span class="ordenowa-hero-wordmark">{$copyBrandName|escape:'htmlall':'UTF-8'}</span>
                      <span class="ordenowa-hero-kana">{$copyBrandDescription|escape:'htmlall':'UTF-8'}</span>
                    </div>
                    <span class="kuranea-hero__seal">B2B PROCUREMENT</span>
                  </div>
                </div>
              </section>

              <section class="kuranea-values container" aria-label="{$copyApproach|escape:'htmlall':'UTF-8'}">
                <div class="kuranea-values__item">
                  <span class="kuranea-values__index">01</span>
                  <h2>{$copyValueOneTitle|escape:'htmlall':'UTF-8'}</h2>
                  <p>{$copyValueOneBody|escape:'htmlall':'UTF-8'}</p>
                </div>
                <div class="kuranea-values__item">
                  <span class="kuranea-values__index">02</span>
                  <h2>{$copyValueTwoTitle|escape:'htmlall':'UTF-8'}</h2>
                  <p>{$copyValueTwoBody|escape:'htmlall':'UTF-8'}</p>
                </div>
                <div class="kuranea-values__item">
                  <span class="kuranea-values__index">03</span>
                  <h2>{$copyValueThreeTitle|escape:'htmlall':'UTF-8'}</h2>
                  <p>{$copyValueThreeBody|escape:'htmlall':'UTF-8'}</p>
                </div>
              </section>

              <section class="kuranea-featured container" aria-label="{$copyEdit|escape:'htmlall':'UTF-8'}">
                <p class="kuranea-eyebrow">{$copyEdit|escape:'htmlall':'UTF-8'}</p>
                {$HOOK_HOME nofilter}
                <div class="kuranea-catalog-empty kuranea-catalog-empty--home" role="status" aria-live="polite">
                  {if $language.locale == 'ja-JP'}
                    <p class="kuranea-catalog-empty__message">ただいま、セレクションを準備しています。</p>
                    <a class="kuranea-catalog-empty__link" href="{$urls.pages.search}">商品を探す <span aria-hidden="true">→</span></a>
                  {elseif $language.locale == 'ko-KR'}
                    <p class="kuranea-catalog-empty__message">첫 컬렉션을 준비하고 있습니다.</p>
                    <a class="kuranea-catalog-empty__link" href="{$urls.pages.search}">상품 검색 <span aria-hidden="true">→</span></a>
                  {else}
                    <p class="kuranea-catalog-empty__message">We're preparing our first collection.</p>
                    <a class="kuranea-catalog-empty__link" href="{$urls.pages.search}">Search the store <span aria-hidden="true">→</span></a>
                  {/if}
                </div>
              </section>

              <section class="kuranea-note">
                <div class="container kuranea-note__inner">
                  <p class="kuranea-eyebrow">{$copyBrandName|escape:'htmlall':'UTF-8'}</p>
                  <p>{$copyNote|escape:'htmlall':'UTF-8'}</p>
                  <a href="{$urls.pages.new_products}" class="kuranea-text-link">{$copyDiscover|escape:'htmlall':'UTF-8'} <span aria-hidden="true">→</span></a>
                </div>
              </section>
            {/block}
          </div>
        {/block}
      {/block}

      {hook h="displayContentWrapperBottom"}
    </div>
  {/block}

  {block name='right_column'}{/block}
{/block}
