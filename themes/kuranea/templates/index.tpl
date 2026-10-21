{** KURANEA editorial home. Product output remains PrestaShop's native module markup. **}
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
              {if $language.locale == 'ja-JP'}
                {$copyEyebrow = '日本で選び抜いた品々'}
                {$copyTitle = '丁寧に選ぶ、美しい暮らし。'}
                {$copyLead = '住まいと自分、日々のひとときを豊かにする品々をご紹介します。'}
                {$copyExplore = 'コレクションを見る'}
                {$copySearch = '商品を探す'}
                {$copyApproach = 'KURANEAのこだわり'}
                {$copyValueOneTitle = '日々の暮らしに寄り添う'}
                {$copyValueOneBody = '日常に、ささやかな心地よさを添える品々。'}
                {$copyValueTwoTitle = '想いを込めて選ぶ'}
                {$copyValueTwoBody = '日本の感性を大切にしたセレクション。'}
                {$copyValueThreeTitle = '静かな個性'}
                {$copyValueThreeBody = '時を重ねても心地よい、細部へのこだわり。'}
                {$copyEdit = 'KURANEAのセレクション'}
                {$copyNote = 'あなたの暮らしに寄り添う、選び抜かれたコレクション。'}
                {$copyDiscover = '新しいアイテムを見る'}
              {elseif $language.locale == 'ko-KR'}
                {$copyEyebrow = '일본에서 엄선한 상품'}
                {$copyTitle = '정성껏 고른 아름다운 일상.'}
                {$copyLead = '집과 나, 그리고 일상의 순간을 풍요롭게 하는 상품을 소개합니다.'}
                {$copyExplore = '컬렉션 보기'}
                {$copySearch = '상품 검색'}
                {$copyApproach = 'KURANEA의 기준'}
                {$copyValueOneTitle = '매일의 일상에 함께'}
                {$copyValueOneBody = '일상에 작은 편안함을 더하는 물건.'}
                {$copyValueTwoTitle = '마음을 담아 고른'}
                {$copyValueTwoBody = '일본의 감성을 소중히 담은 셀렉션.'}
                {$copyValueThreeTitle = '차분하고 특별한'}
                {$copyValueThreeBody = '오래도록 곁에 두고 싶은 세심한 디테일.'}
                {$copyEdit = 'KURANEA 셀렉션'}
                {$copyNote = '당신의 일상에 자연스럽게 어우러지는 엄선된 컬렉션.'}
                {$copyDiscover = '새로운 상품 보기'}
              {else}
                {$copyEyebrow = 'Curated in Japan'}
                {$copyTitle = 'A thoughtful life, beautifully chosen.'}
                {$copyLead = 'Discover considered essentials for home, self, and the moments in between.'}
                {$copyExplore = 'Explore the collection'}
                {$copySearch = 'Search the store'}
                {$copyApproach = 'The KURANEA approach'}
                {$copyValueOneTitle = 'For everyday rituals'}
                {$copyValueOneBody = 'Objects that bring a little more care to the everyday.'}
                {$copyValueTwoTitle = 'Selected with intention'}
                {$copyValueTwoBody = 'A considered edit shaped by Japanese sensibility.'}
                {$copyValueThreeTitle = 'Quietly distinctive'}
                {$copyValueThreeBody = 'Timeless details, made to feel at home.'}
                {$copyEdit = 'The KURANEA edit'}
                {$copyNote = 'A considered collection for the way you live.'}
                {$copyDiscover = 'Discover what is new'}
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
                      <img src="{$urls.theme_assets}img/brand/pwa-512x512.png" width="512" height="512" alt="" fetchpriority="high">
                    </div>
                    <span class="kuranea-hero__seal">KURANEA · クラネア</span>
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

              {if !empty($HOOK_HOME)}
                <section class="kuranea-featured container" aria-label="{$copyEdit|escape:'htmlall':'UTF-8'}">
                  <p class="kuranea-eyebrow">{$copyEdit|escape:'htmlall':'UTF-8'}</p>
                  {$HOOK_HOME nofilter}
                </section>
              {/if}

              <section class="kuranea-note">
                <div class="container kuranea-note__inner">
                  <p class="kuranea-eyebrow">KURANEA / クラネア</p>
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
