{**
 * For the full copyright and license information, please view the
 * LICENSE.md file that was distributed with this source code.
 *}
{extends file='parent:catalog/product.tpl'}

{block name='page_title'}{$product.name|escape:'htmlall':'UTF-8'}{/block}

{block name='product_header_manufacturer'}
  {if isset($product_manufacturer->id) && $product_manufacturer->active}
    <div class="product__manufacturer">
      {capture assign='manufacturer_aria_label'}{l s='Product brand: %brand_name%' sprintf=['%brand_name%' => $product_manufacturer->name] d='Shop.Theme.Catalog'}{/capture}
      <a href="{$product_manufacturer->url|escape:'htmlall':'UTF-8'}" aria-label="{$manufacturer_aria_label|escape:'htmlall':'UTF-8'}">
        {$product_manufacturer->name|escape:'htmlall':'UTF-8'}
      </a>
    </div>
  {/if}
{/block}

{block name='product_attachments'}
  {if $product.attachments}
    <div class="info accordion-item" id="product_attachments">
      <h2 class="accordion-header" id="product_attachments_heading">
        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#product_attachments_collapse" aria-expanded="false" aria-controls="product_attachments_collapse">
          {l s='Download' d='Shop.Theme.Actions'}
        </button>
      </h2>

      <div id="product_attachments_collapse" class="accordion-collapse collapse" aria-labelledby="product_attachments_heading">
        <div class="accordion-body">
          <div class="product__attachments">
            {foreach from=$product.attachments item=attachment}
              <div class="attachment">
                <p class="attachment__name">
                  {$attachment.name|escape:'htmlall':'UTF-8'}
                </p>

                {if $attachment.description}
                  <p class="attachment__description">
                    {$attachment.description|escape:'htmlall':'UTF-8'}
                  </p>
                {/if}

                {capture assign='attachment_aria_label'}{l s='Download %attachment_name%' sprintf=['%attachment_name%' => $attachment.name] d='Shop.Theme.Actions'}{/capture}
                <a class="attachment__link stretched-link"
                  href="{url entity='attachment' params=['id_attachment' => $attachment.id_attachment]}"
                  aria-label="{$attachment_aria_label|escape:'htmlall':'UTF-8'}"
                >
                  <i class="material-icons" aria-hidden="true">&#xE2C4;</i> {l s='Download' d='Shop.Theme.Actions'} ({$attachment.file_size_formatted|escape:'htmlall':'UTF-8'})
                </a>
              </div>
            {/foreach}
          </div>
        </div>
      </div>
    </div>
  {/if}
{/block}
