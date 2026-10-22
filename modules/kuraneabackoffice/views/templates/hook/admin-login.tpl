<div class="ordenowa-admin-login-brand">
  {if $ordenowa_backoffice_logo}
    <img
      src="{$ordenowa_backoffice_logo|escape:'htmlall':'UTF-8'}"
      alt="{$ordenowa_backoffice_brand_name|escape:'htmlall':'UTF-8'}"
      decoding="async"
    >
  {else}
    <span>{$ordenowa_backoffice_brand_name|escape:'htmlall':'UTF-8'}</span>
  {/if}
</div>

<style>
{literal}
  #login-header,
  #login-footer {
    display: none !important;
  }

  #shop-img img {
    display: none !important;
  }

  .ordenowa-admin-login-brand {
    margin: 1.25rem auto 0;
    text-align: center;
    color: #10243a;
    font: 600 1.75rem/1.2 Georgia, "Noto Serif JP", serif;
    letter-spacing: .12em;
  }

  .ordenowa-admin-login-brand img {
    display: inline-block;
    max-width: min(15rem, 70vw);
    max-height: 5rem;
    object-fit: contain;
  }

  #login .login-back .material-icons {
    font-size: 0;
  }

  #login .login-back .material-icons::before {
    content: "←";
    font-family: Arial, sans-serif;
    font-size: 1.125rem;
  }
{/literal}
</style>
