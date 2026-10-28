{if $showGallery|default:false}<div class="ow-media-panel">{/if}
<div class="ow-product-media">
  {if $product.image}
    <img src="{$product.image|escape:'htmlall':'UTF-8'}" alt="{$product.name|escape:'htmlall':'UTF-8'}" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="560" height="440">
  {else}
    <div class="ow-image-placeholder" role="img" aria-label="{$ow.copy.no_image|escape:'htmlall':'UTF-8'}"><span aria-hidden="true">◇</span><span>{$ow.copy.no_image|escape:'htmlall':'UTF-8'}</span></div>
  {/if}
</div>
{if $showGallery|default:false}
  {if $product.image_count > 1}
    <details open class="ow-gallery" data-testid="product-gallery" data-image-count="{$product.image_count|escape:'htmlall':'UTF-8'}">
      <summary>{$ow.copy.photos|escape:'htmlall':'UTF-8'} ({$product.image_count|escape:'htmlall':'UTF-8'})</summary>
      <div class="ow-gallery-images">
        {foreach from=$product.images item=photo name=productPhotos}
          <a href="{$photo|escape:'htmlall':'UTF-8'}" data-testid="product-photo"><img src="{$photo|escape:'htmlall':'UTF-8'}" alt="{$product.name|escape:'htmlall':'UTF-8'} · {$ow.copy.photo|escape:'htmlall':'UTF-8'} {$smarty.foreach.productPhotos.iteration|escape:'htmlall':'UTF-8'}" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="160" height="160"></a>
        {/foreach}
      </div>
    </details>
  {/if}
</div>
{/if}
