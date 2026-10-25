{**
 * Checkout/product reassurance labels are catalog text from the module.
 * The stock module seeds these labels together with an administrator editing
 * hint. Keep configured copy and markup, but never show that hint to shoppers.
 *}
{if isset($blocks) && !empty($blocks)}
  {assign var=visibleBlockCount value=0}
  {foreach from=$blocks item=$block key=$key}
    {assign var=cleanedDescription value=$block['description']|default:''}
    {assign var=cleanedDescription value=$cleanedDescription|replace:'(edit with the Customer Reassurance module)':''}
    {assign var=descriptionText value=$cleanedDescription|strip_tags|replace:'&nbsp;':' '|replace:'&#160;':' '|trim}
    {assign var=titleText value=$block['title']|strip_tags|trim}
    {assign var=isDefaultTitle value=false}
    {if $block['title'] == 'Security policy' || $block['title'] == 'Delivery policy' || $block['title'] == 'Return policy'}
      {assign var=isDefaultTitle value=true}
    {/if}
    {if !($isDefaultTitle && $descriptionText == '') && ($titleText != '' || $descriptionText != '' || !empty($block['custom_icon']) || !empty($block['icon']))}
      {assign var=visibleBlockCount value=$visibleBlockCount+1}
    {/if}
  {/foreach}

  {if $visibleBlockCount > 0}
    <div class="blockreassurance blockreassurance--{$page.page_name}">
      {foreach from=$blocks item=$block key=$key}
        {assign var=cleanedDescription value=$block['description']|default:''}
        {assign var=cleanedDescription value=$cleanedDescription|replace:'(edit with the Customer Reassurance module)':''}
        {assign var=descriptionText value=$cleanedDescription|strip_tags|replace:'&nbsp;':' '|replace:'&#160;':' '|trim}
        {assign var=titleText value=$block['title']|strip_tags|trim}
        {assign var=isDefaultTitle value=false}
        {if $block['title'] == 'Security policy' || $block['title'] == 'Delivery policy' || $block['title'] == 'Return policy'}
          {assign var=isDefaultTitle value=true}
        {/if}
        {if !($isDefaultTitle && $descriptionText == '') && ($titleText != '' || $descriptionText != '' || !empty($block['custom_icon']) || !empty($block['icon']))}
          {if $block['type_link'] !== $LINK_TYPE_NONE && !empty($block['link'])}
            <a class="reassurance reassurance--link" href="{$block['link']|escape:'htmlall':'UTF-8'}">
          {else}
            <div class="reassurance">
          {/if}

            <span class="reassurance__image">
              {if $block['custom_icon']}
                <img class="{if $block['is_svg']}svg invisible{/if} img-fluid" src="{$block['custom_icon']}" alt="">
              {elseif $block['icon']}
                <img class="svg img-fluid invisible" src="{$block['icon']}" alt="">
              {/if}
            </span>

            <span class="reassurance__content">
              <span class="reassurance__title">
                {if $block['title'] == 'Security policy'}
                  {l s='Security policy' d='Modules.Blockreassurance.Shop'}
                {elseif $block['title'] == 'Delivery policy'}
                  {l s='Delivery policy' d='Modules.Blockreassurance.Shop'}
                {elseif $block['title'] == 'Return policy'}
                  {l s='Return policy' d='Modules.Blockreassurance.Shop'}
                {else}
                  {$block['title']|escape:'htmlall':'UTF-8'}
                {/if}
              </span>
              {if $descriptionText != ''}
                <br/>
                <small class="reassurance__desc">{$cleanedDescription nofilter}</small>
              {/if}
            </span>

          {if !empty($block['link']) && $block['type_link'] !== $LINK_TYPE_NONE}
            </a>
          {else}
            </div>
          {/if}
        {/if}
      {/foreach}
    </div>
  {/if}
{/if}
