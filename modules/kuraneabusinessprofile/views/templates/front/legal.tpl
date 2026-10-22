{extends file='page.tpl'}

{block name='page_content'}
  <div class="container ordenowa-legal-page__container">
    <h1 class="page-title">{$ordenowaLegalPageTitle|escape:'htmlall':'UTF-8'}</h1>
    {$ordenowaLegalPageContent nofilter}
  </div>
{/block}
