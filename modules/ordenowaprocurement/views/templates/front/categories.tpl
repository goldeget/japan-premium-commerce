<ul class="ow-category-list">
  {foreach from=$categoryNodes item=category}
    <li><a href="{$category.url|escape:'htmlall':'UTF-8'}" {if $ow.category == $category.id}aria-current="page"{/if}>{$category.name|escape:'htmlall':'UTF-8'}</a>
      {if $category.children}{include file='module:ordenowaprocurement/views/templates/front/categories.tpl' categoryNodes=$category.children}{/if}
    </li>
  {/foreach}
</ul>
