<div class="kuranea-admin-login-brand" style="margin: 1.25rem auto 0; text-align: center;">
  <img
    src="{$kuranea_backoffice_logo|escape:'htmlall':'UTF-8'}"
    width="240"
    height="66"
    alt="KURANEA"
    decoding="async"
    style="display: inline-block; object-fit: cover; object-position: center 51%;"
  >
</div>

<style>
{literal}
  #login-header,
  #login-footer {
    display: none !important;
  }

  #shop-img img {
    content: url("{/literal}{$kuranea_backoffice_logo|escape:'htmlall':'UTF-8'}{literal}");
    width: 240px !important;
    height: 66px !important;
    object-fit: cover;
    object-position: center 51%;
  }

  .kuranea-admin-login-brand {
    display: none !important;
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
