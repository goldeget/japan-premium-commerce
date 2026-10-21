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
              <section class="kuranea-hero" aria-labelledby="kuranea-home-title">
                <div class="container kuranea-hero__grid">
                  <div class="kuranea-hero__copy">
                    <p class="kuranea-eyebrow">{l s='Curated in Japan' d='Shop.Theme.Kuranea'}</p>
                    <h1 id="kuranea-home-title">{l s='A thoughtful life, beautifully chosen.' d='Shop.Theme.Kuranea'}</h1>
                    <p class="kuranea-hero__lead">{l s='Discover considered essentials for home, self, and the moments in between.' d='Shop.Theme.Kuranea'}</p>
                    <div class="kuranea-hero__actions">
                      <a class="btn btn-primary kuranea-button" href="{$urls.pages.new_products}">{l s='Explore the collection' d='Shop.Theme.Kuranea'}</a>
                      <a class="kuranea-text-link" href="{$urls.pages.search}">{l s='Search the store' d='Shop.Theme.Kuranea'} <span aria-hidden="true">→</span></a>
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

              <section class="kuranea-values container" aria-label="{l s='The KURANEA approach' d='Shop.Theme.Kuranea'}">
                <div class="kuranea-values__item">
                  <span class="kuranea-values__index">01</span>
                  <h2>{l s='For everyday rituals' d='Shop.Theme.Kuranea'}</h2>
                  <p>{l s='Objects that bring a little more care to the everyday.' d='Shop.Theme.Kuranea'}</p>
                </div>
                <div class="kuranea-values__item">
                  <span class="kuranea-values__index">02</span>
                  <h2>{l s='Selected with intention' d='Shop.Theme.Kuranea'}</h2>
                  <p>{l s='A considered edit shaped by Japanese sensibility.' d='Shop.Theme.Kuranea'}</p>
                </div>
                <div class="kuranea-values__item">
                  <span class="kuranea-values__index">03</span>
                  <h2>{l s='Quietly distinctive' d='Shop.Theme.Kuranea'}</h2>
                  <p>{l s='Timeless details, made to feel at home.' d='Shop.Theme.Kuranea'}</p>
                </div>
              </section>

              {if !empty($HOOK_HOME)}
                <section class="kuranea-featured container" aria-label="{l s='The KURANEA edit' d='Shop.Theme.Kuranea'}">
                  <p class="kuranea-eyebrow">{l s='The KURANEA edit' d='Shop.Theme.Kuranea'}</p>
                  {$HOOK_HOME nofilter}
                </section>
              {/if}

              <section class="kuranea-note">
                <div class="container kuranea-note__inner">
                  <p class="kuranea-eyebrow">KURANEA / クラネア</p>
                  <p>{l s='A considered collection for the way you live.' d='Shop.Theme.Kuranea'}</p>
                  <a href="{$urls.pages.new_products}" class="kuranea-text-link">{l s='Discover what is new' d='Shop.Theme.Kuranea'} <span aria-hidden="true">→</span></a>
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
