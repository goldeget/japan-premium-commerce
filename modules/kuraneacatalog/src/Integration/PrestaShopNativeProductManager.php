<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Integration;

use InvalidArgumentException;
use Kuranea\Catalog\Domain\ProductAdminDraft;
use PrestaShop\PrestaShop\Adapter\SymfonyContainer;
use PrestaShop\PrestaShop\Core\Domain\AttributeGroup\Attribute\Command\AddAttributeCommand;
use PrestaShop\PrestaShop\Core\Domain\AttributeGroup\Command\AddAttributeGroupCommand;
use RuntimeException;

/**
 * Persists Korean Back Office product drafts through PrestaShop's native models.
 * Products managed here are deliberately hidden, inactive, and non-orderable.
 */
final class PrestaShopNativeProductManager
{
    private const REFERENCE_PREFIX = 'OWA-ADMIN-';
    private const MAX_IMAGES = 5;
    private const MAX_IMAGE_BYTES = 10485760;

    /** @return list<array{id_category:int,name:string}> */
    public function categories(): array
    {
        [$languageId, $shopId] = $this->contextIds();
        $rows = \Db::getInstance()->executeS('
            SELECT c.`id_category`, cl.`name`
            FROM `' . _DB_PREFIX_ . 'category` c
            INNER JOIN `' . _DB_PREFIX_ . 'category_lang` cl
                ON cl.`id_category` = c.`id_category` AND cl.`id_lang` = ' . (int) $languageId . '
            INNER JOIN `' . _DB_PREFIX_ . 'category_shop` cs
                ON cs.`id_category` = c.`id_category` AND cs.`id_shop` = ' . (int) $shopId . '
            WHERE c.`active` = 1 AND c.`id_parent` > 0
            ORDER BY c.`nleft` ASC, cl.`name` ASC
        ');
        if (!is_array($rows)) {
            throw new RuntimeException('PrestaShop 카테고리 목록을 불러오지 못했습니다.');
        }

        return array_map(static fn (array $row): array => [
            'id_category' => (int) $row['id_category'],
            'name' => (string) $row['name'],
        ], $rows);
    }

    /** @return list<array{id_product:int,name:string,price:int,reference:string}> */
    public function managedProducts(): array
    {
        [$languageId, $shopId] = $this->contextIds();
        $rows = \Db::getInstance()->executeS('
            SELECT p.`id_product`, p.`reference`, pl.`name`, ps.`price`
            FROM `' . _DB_PREFIX_ . 'product` p
            INNER JOIN `' . _DB_PREFIX_ . 'product_shop` ps
                ON ps.`id_product` = p.`id_product` AND ps.`id_shop` = ' . (int) $shopId . '
            INNER JOIN `' . _DB_PREFIX_ . 'product_lang` pl
                ON pl.`id_product` = p.`id_product` AND pl.`id_shop` = ' . (int) $shopId . ' AND pl.`id_lang` = ' . (int) $languageId . '
            WHERE p.`reference` LIKE \'OWA-ADMIN-%\'
                AND p.`active` = 0 AND ps.`active` = 0
                AND p.`visibility` = \'none\' AND p.`available_for_order` = 0
            ORDER BY ps.`date_upd` DESC, p.`id_product` DESC
            LIMIT 50
        ');
        if (!is_array($rows)) {
            throw new RuntimeException('관리 상품 목록을 불러오지 못했습니다.');
        }

        return array_map(static fn (array $row): array => [
            'id_product' => (int) $row['id_product'],
            'name' => (string) $row['name'],
            'price' => (int) round((float) $row['price']),
            'reference' => (string) $row['reference'],
        ], $rows);
    }

    /** @return array<string, mixed> */
    public function editorData(int $productId): array
    {
        [$languageId, $shopId] = $this->contextIds();
        $product = $this->loadManagedProduct($productId, $languageId, $shopId);
        $rows = \Db::getInstance()->executeS('
            SELECT l.`iso_code`, pl.`name`, pl.`description`
            FROM `' . _DB_PREFIX_ . 'lang` l
            LEFT JOIN `' . _DB_PREFIX_ . 'product_lang` pl
                ON pl.`id_lang` = l.`id_lang` AND pl.`id_product` = ' . (int) $productId . ' AND pl.`id_shop` = ' . (int) $shopId . '
            WHERE l.`active` = 1
        ');
        $localized = ['ja' => null, 'ko' => null];
        foreach (is_array($rows) ? $rows : [] as $row) {
            $iso = (string) ($row['iso_code'] ?? '');
            if (array_key_exists($iso, $localized)) {
                $localized[$iso] = $row;
            }
        }
        $fallbackName = is_array($product->name) ? (string) reset($product->name) : (string) $product->name;
        $fallbackDescription = is_array($product->description) ? (string) reset($product->description) : (string) $product->description;
        $nameJa = (string) ($localized['ja']['name'] ?? $fallbackName);
        $nameKo = (string) ($localized['ko']['name'] ?? $nameJa);
        $descriptionJa = $this->htmlToPlainText((string) ($localized['ja']['description'] ?? $fallbackDescription));
        $descriptionKo = $this->htmlToPlainText((string) ($localized['ko']['description'] ?? $descriptionJa));
        $combinationStockRows = $this->combinationStockRows($productId, $languageId, $shopId);
        // The default is the product-level stock row; variant stocks remain
        // independent and must never seed this value from the first variant.
        $quantity = (int) \StockAvailable::getQuantityAvailableByProduct($productId, 0, $shopId);
        $combinationQuantities = [];
        foreach ($combinationStockRows as $row) {
            $combinationQuantities[$row['id_product_attribute']] = $row['quantity'];
        }

        return [
            'id_product' => $productId,
            'name_ja' => $nameJa,
            'name_ko' => $nameKo,
            'price_jpy' => (int) round((float) $product->price),
            'quantity' => $quantity,
            'description_ja' => $descriptionJa,
            'description_ko' => $descriptionKo,
            'category_ids' => array_map('intval', \Product::getProductCategories($productId)),
            'options' => $this->optionText($productId, $languageId, $shopId),
            'combination_stock_rows' => $combinationStockRows,
            'combination_quantities' => $combinationQuantities,
            'image_ids' => $this->imageIds($productId),
        ];
    }

    /** @return list<array{id_product_attribute:int,label:string,quantity:int}> */
    public function combinationStockRows(int $productId, int $languageId, int $shopId): array
    {
        $rows = \Db::getInstance()->executeS('
            SELECT pa.`id_product_attribute`, agl.`name` AS `group_name`, al.`name` AS `attribute_name`
            FROM `' . _DB_PREFIX_ . 'product_attribute` pa
            INNER JOIN `' . _DB_PREFIX_ . 'product_attribute_combination` pac
                ON pac.`id_product_attribute` = pa.`id_product_attribute`
            INNER JOIN `' . _DB_PREFIX_ . 'attribute` a ON a.`id_attribute` = pac.`id_attribute`
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_group` ag ON ag.`id_attribute_group` = a.`id_attribute_group`
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_lang` agl
                ON agl.`id_attribute_group` = ag.`id_attribute_group` AND agl.`id_lang` = ' . (int) $languageId . '
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_lang` al
                ON al.`id_attribute` = a.`id_attribute` AND al.`id_lang` = ' . (int) $languageId . '
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_shop` ags
                ON ags.`id_attribute_group` = ag.`id_attribute_group` AND ags.`id_shop` = ' . (int) $shopId . '
            WHERE pa.`id_product` = ' . (int) $productId . '
            ORDER BY pa.`id_product_attribute` ASC, ag.`position` ASC, a.`position` ASC
        ');
        $labels = [];
        foreach (is_array($rows) ? $rows : [] as $row) {
            $combinationId = (int) $row['id_product_attribute'];
            $labels[$combinationId][] = (string) $row['group_name'] . ': ' . (string) $row['attribute_name'];
        }

        $result = [];
        foreach ($this->combinationIds($productId) as $combinationId) {
            $result[] = [
                'id_product_attribute' => $combinationId,
                'label' => implode(' / ', $labels[$combinationId] ?? []),
                'quantity' => (int) \StockAvailable::getQuantityAvailableByProduct($productId, $combinationId, $shopId),
            ];
        }

        return $result;
    }

    /** @return list<int> */
    public function imageIds(int $productId): array
    {
        $rows = \Db::getInstance()->executeS('
            SELECT `id_image` FROM `' . _DB_PREFIX_ . 'image`
            WHERE `id_product` = ' . (int) $productId . ' ORDER BY `position` ASC, `id_image` ASC
        ');

        return array_map(static fn (array $row): int => (int) $row['id_image'], is_array($rows) ? $rows : []);
    }

    /**
     * @param list<array{name:string,tmp_name:string,size:int,error:int}> $uploads Normalized HTTP uploads
     * @param list<int|string> $removeImageIds
     */
    public function save(
        ?int $productId,
        ProductAdminDraft $draft,
        array $uploads = [],
        array $removeImageIds = []
    ): int {
        [$languageId, $shopId] = $this->contextIds();
        $this->requireJpyDefaultCurrency();
        $this->validateCategories($draft->categoryIds, $languageId, $shopId);
        $this->validateUploads($uploads);

        $isNew = $productId === null || $productId < 1;
        $product = $isNew
            ? new \Product()
            : $this->loadManagedProduct((int) $productId, $languageId, $shopId);
        if (!$isNew) {
            // PrestaShop 9.2 updates only ObjectModel::$id_lang when it is set.
            // Reload without a language so localized name and description edits persist together.
            $product = new \Product((int) $product->id, false, null, $shopId);
        }
        $validatedRemovalIds = $this->validateImageChanges(
            $isNew ? null : (int) $product->id,
            $uploads,
            $removeImageIds
        );
        $this->validateOptionChanges(
            $isNew ? null : (int) $product->id,
            $draft,
            $languageId,
            $shopId
        );
        $this->validateCombinationQuantities(
            $isNew ? null : (int) $product->id,
            $draft
        );
        if ($isNew) {
            $product->reference = self::REFERENCE_PREFIX . strtoupper(bin2hex(random_bytes(6)));
            $product->id_shop_default = $shopId;
        }

        $languages = \Language::getLanguages(false);
        $product->name = $this->localizedValues($languages, $draft->nameJa, $draft->nameKo);
        $product->link_rewrite = $this->localizedSlugs($languages, $draft);
        $product->description = $this->localizedValues(
            $languages,
            $this->plainTextToHtml($draft->descriptionJa),
            $this->plainTextToHtml($draft->descriptionKo)
        );
        $product->description_short = $this->localizedValues(
            $languages,
            $this->plainTextToHtml($draft->descriptionJa),
            $this->plainTextToHtml($draft->descriptionKo)
        );
        $product->price = (float) $draft->priceJpy;
        $product->id_category_default = $draft->categoryIds[0];
        $product->id_tax_rules_group = 0;
        $product->minimal_quantity = 1;
        $product->active = 0;
        $product->visibility = 'none';
        $product->available_for_order = 0;
        $product->show_price = 0;

        if ($isNew) {
            if (!$product->add()) {
                throw new RuntimeException('PrestaShop에서 비활성 상품을 생성하지 못했습니다.');
            }
        } elseif (!$product->update()) {
            throw new RuntimeException('PrestaShop에서 상품 내용을 저장하지 못했습니다.');
        }

        $savedProductId = (int) $product->id;
        if ($savedProductId < 1 || !$product->updateCategories($draft->categoryIds)) {
            throw new RuntimeException('상품 카테고리를 저장하지 못했습니다.');
        }

        $this->syncCombinations($savedProductId, $draft, $languageId, $shopId);
        $this->removeImages($savedProductId, $validatedRemovalIds, $shopId);
        $this->addImages($savedProductId, $draft, $uploads, $shopId);

        // Reassert the sale gate after every product/combination mutation.
        $product = new \Product($savedProductId, false, $languageId, $shopId);
        $product->active = 0;
        $product->visibility = 'none';
        $product->available_for_order = 0;
        $product->show_price = 0;
        if (!$product->update()) {
            throw new RuntimeException('상품의 비활성 판매 보호 상태를 저장하지 못했습니다.');
        }

        return $savedProductId;
    }

    /** @return array{name:string,values:list<string>}[] */
    public function optionGroups(int $productId, int $languageId, int $shopId): array
    {
        $rows = \Db::getInstance()->executeS('
            SELECT ag.`id_attribute_group`, agl.`name` AS `group_name`, a.`id_attribute`, al.`name` AS `attribute_name`
            FROM `' . _DB_PREFIX_ . 'product_attribute` pa
            INNER JOIN `' . _DB_PREFIX_ . 'product_attribute_combination` pac
                ON pac.`id_product_attribute` = pa.`id_product_attribute`
            INNER JOIN `' . _DB_PREFIX_ . 'attribute` a ON a.`id_attribute` = pac.`id_attribute`
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_group` ag ON ag.`id_attribute_group` = a.`id_attribute_group`
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_lang` agl
                ON agl.`id_attribute_group` = ag.`id_attribute_group` AND agl.`id_lang` = ' . (int) $languageId . '
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_lang` al
                ON al.`id_attribute` = a.`id_attribute` AND al.`id_lang` = ' . (int) $languageId . '
            INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_shop` ags
                ON ags.`id_attribute_group` = ag.`id_attribute_group` AND ags.`id_shop` = ' . (int) $shopId . '
            WHERE pa.`id_product` = ' . (int) $productId . '
            GROUP BY ag.`id_attribute_group`, agl.`name`, a.`id_attribute`, al.`name`
            ORDER BY ag.`position` ASC, a.`position` ASC
        ');
        $groups = [];
        foreach (is_array($rows) ? $rows : [] as $row) {
            $groupId = (int) $row['id_attribute_group'];
            if (!isset($groups[$groupId])) {
                $groups[$groupId] = ['name' => (string) $row['group_name'], 'values' => []];
            }
            $groups[$groupId]['values'][] = (string) $row['attribute_name'];
        }

        return array_values($groups);
    }

    private function loadManagedProduct(int $productId, int $languageId, int $shopId): \Product
    {
        $product = new \Product($productId, false, $languageId, $shopId);
        if (!\Validate::isLoadedObject($product)
            || !str_starts_with((string) $product->reference, self::REFERENCE_PREFIX)) {
            throw new InvalidArgumentException('ORDENOWA 한국어 상품 관리에서 만든 상품만 수정할 수 있습니다.');
        }
        if ((bool) $product->active
            || (string) $product->visibility !== 'none'
            || (bool) $product->available_for_order) {
            throw new InvalidArgumentException('판매 보호 상태가 변경된 상품은 이 화면에서 수정할 수 없습니다.');
        }

        return $product;
    }

    /** @param list<int> $categoryIds */
    private function validateCategories(array $categoryIds, int $languageId, int $shopId): void
    {
        $ids = implode(',', array_map('intval', $categoryIds));
        $count = (int) \Db::getInstance()->getValue('
            SELECT COUNT(DISTINCT c.`id_category`)
            FROM `' . _DB_PREFIX_ . 'category` c
            INNER JOIN `' . _DB_PREFIX_ . 'category_lang` cl
                ON cl.`id_category` = c.`id_category` AND cl.`id_lang` = ' . (int) $languageId . '
            INNER JOIN `' . _DB_PREFIX_ . 'category_shop` cs
                ON cs.`id_category` = c.`id_category` AND cs.`id_shop` = ' . (int) $shopId . '
            WHERE c.`active` = 1 AND c.`id_parent` > 0 AND c.`id_category` IN (' . $ids . ')
        ');
        if ($count !== count($categoryIds)) {
            throw new InvalidArgumentException('선택한 카테고리 중 현재 쇼핑몰에서 사용할 수 없는 항목이 있습니다.');
        }
    }

    private function validateOptionChanges(?int $productId, ProductAdminDraft $draft, int $languageId, int $shopId): void
    {
        if ($productId === null
            || $this->optionGroups($productId, $languageId, $shopId) === $draft->optionGroups) {
            return;
        }

        $existingCombinationIds = $this->combinationIds($productId);
        if ($existingCombinationIds !== [] && $this->combinationsUsed($existingCombinationIds)) {
            throw new InvalidArgumentException('장바구니 또는 주문에서 사용된 옵션은 변경할 수 없습니다.');
        }
    }

    /** @param list<array{name:string,values:list<string>}> $groups */
    private function syncCombinations(int $productId, ProductAdminDraft $draft, int $languageId, int $shopId): void
    {
        $existingGroups = $this->optionGroups($productId, $languageId, $shopId);
        $existingCombinationIds = $this->combinationIds($productId);
        $newGroups = $draft->optionGroups;
        $groupsChanged = $existingGroups !== $newGroups;
        if ($groupsChanged) {
            if ($existingCombinationIds !== [] && $this->combinationsUsed($existingCombinationIds)) {
                throw new InvalidArgumentException('장바구니 또는 주문에서 사용된 옵션은 변경할 수 없습니다.');
            }
            foreach ($existingCombinationIds as $combinationId) {
                $combination = new \Combination($combinationId);
                if (!$combination->delete()) {
                    throw new RuntimeException('기존 상품 옵션을 안전하게 교체하지 못했습니다.');
                }
            }
            $existingCombinationIds = [];
        }

        if ($newGroups === []) {
            \StockAvailable::setQuantity($productId, 0, $draft->quantity, $shopId);

            return;
        }

        $attributeIdsByGroup = [];
        foreach ($newGroups as $group) {
            $groupId = $this->getOrCreateAttributeGroup($group['name'], $languageId, $shopId);
            $attributeIdsByGroup[] = array_map(
                fn (string $value): int => $this->getOrCreateAttribute($groupId, $value, $languageId, $shopId),
                $group['values']
            );
        }

        if ($existingCombinationIds !== []) {
            foreach ($existingCombinationIds as $combinationId) {
                $quantity = !$groupsChanged
                    ? ($draft->combinationQuantities[$combinationId] ?? $draft->quantity)
                    : $draft->quantity;
                \StockAvailable::setQuantity($productId, $combinationId, $quantity, $shopId);
            }
            \StockAvailable::setQuantity($productId, 0, 0, $shopId);

            return;
        }

        $attributeSets = [[]];
        foreach ($attributeIdsByGroup as $attributeIds) {
            $next = [];
            foreach ($attributeSets as $attributeSet) {
                foreach ($attributeIds as $attributeId) {
                    $next[] = [...$attributeSet, $attributeId];
                }
            }
            $attributeSets = $next;
        }

        foreach ($attributeSets as $index => $attributeSet) {
            $combination = new \Combination();
            $combination->id_product = $productId;
            $combination->reference = (string) (new \Product($productId))->reference . '-V' . ($index + 1);
            $combination->price = 0;
            $combination->minimal_quantity = 1;
            $combination->default_on = $index === 0;
            if (!$combination->add() || !$combination->setAttributes($attributeSet)) {
                throw new RuntimeException('상품 옵션 조합을 저장하지 못했습니다.');
            }
            \StockAvailable::setQuantity($productId, (int) $combination->id, $draft->quantity, $shopId);
        }
        \StockAvailable::setQuantity($productId, 0, 0, $shopId);
    }

    private function validateCombinationQuantities(?int $productId, ProductAdminDraft $draft): void
    {
        if ($draft->combinationQuantities === []) {
            return;
        }
        if ($productId === null) {
            throw new InvalidArgumentException('새 상품을 저장한 뒤 옵션 조합별 재고를 입력해 주세요.');
        }

        $existingIds = $this->combinationIds($productId);
        $submittedIds = array_map('intval', array_keys($draft->combinationQuantities));
        sort($existingIds, SORT_NUMERIC);
        sort($submittedIds, SORT_NUMERIC);
        if ($submittedIds !== $existingIds) {
            throw new InvalidArgumentException('현재 상품의 모든 옵션 조합별 재고를 다시 확인해 주세요.');
        }
    }

    /** @param list<int> $combinationIds */
    private function combinationsUsed(array $combinationIds): bool
    {
        $ids = implode(',', array_map('intval', $combinationIds));
        $orderRows = (int) \Db::getInstance()->getValue('
            SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'order_detail`
            WHERE `product_attribute_id` IN (' . $ids . ')
        ');
        $cartRows = (int) \Db::getInstance()->getValue('
            SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'cart_product`
            WHERE `id_product_attribute` IN (' . $ids . ')
        ');

        return $orderRows > 0 || $cartRows > 0;
    }

    /** @return list<int> */
    private function combinationIds(int $productId): array
    {
        $rows = \Db::getInstance()->executeS('
            SELECT `id_product_attribute` FROM `' . _DB_PREFIX_ . 'product_attribute`
            WHERE `id_product` = ' . (int) $productId . ' ORDER BY `id_product_attribute` ASC
        ');

        return array_map(static fn (array $row): int => (int) $row['id_product_attribute'], is_array($rows) ? $rows : []);
    }

    /** @param list<array{name:string,tmp_name:string,size:int,error:int}> $uploads */
    private function validateUploads(array $uploads): void
    {
        if (count($uploads) > self::MAX_IMAGES) {
            throw new InvalidArgumentException('한 번에 상품 이미지는 최대 5개까지 등록할 수 있습니다.');
        }
        foreach ($uploads as $upload) {
            if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_NO_FILE) {
                continue;
            }
            if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK
                || (int) ($upload['size'] ?? 0) < 1
                || (int) $upload['size'] > self::MAX_IMAGE_BYTES
                || !is_file((string) ($upload['tmp_name'] ?? ''))) {
                throw new InvalidArgumentException('상품 이미지는 10MB 이하의 JPEG, PNG, WEBP 파일로 등록해 주세요.');
            }
            $path = (string) $upload['tmp_name'];
            $finfo = new \finfo(FILEINFO_MIME_TYPE);
            $mime = $finfo->file($path);
            $imageInfo = @getimagesize($path);
            if (!in_array($mime, ['image/jpeg', 'image/png', 'image/webp'], true)
                || !is_array($imageInfo)
                || !in_array((string) ($imageInfo['mime'] ?? ''), ['image/jpeg', 'image/png', 'image/webp'], true)) {
                throw new InvalidArgumentException('상품 이미지는 실제 JPEG, PNG, WEBP 이미지 파일이어야 합니다.');
            }
        }
    }

    /**
     * Validate image ownership and the resulting image count before any product mutation.
     *
     * @param list<array{name:string,tmp_name:string,size:int,error:int}> $uploads
     * @param list<int|string> $removeImageIds
     * @return list<int>
     */
    private function validateImageChanges(?int $productId, array $uploads, array $removeImageIds): array
    {
        $removalIds = [];
        foreach ($removeImageIds as $rawImageId) {
            if (is_int($rawImageId)) {
                $imageId = $rawImageId;
            } elseif (is_string($rawImageId)
                && preg_match('/\A[1-9][0-9]*\z/D', $rawImageId) === 1
                && filter_var($rawImageId, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]) !== false) {
                $imageId = (int) $rawImageId;
            } else {
                throw new InvalidArgumentException('삭제할 상품 이미지 선택값이 올바르지 않습니다.');
            }
            if ($imageId < 1) {
                throw new InvalidArgumentException('삭제할 상품 이미지 선택값이 올바르지 않습니다.');
            }
            $removalIds[$imageId] = $imageId;
        }

        $existingImageIds = $productId === null ? [] : $this->imageIds($productId);
        $existingImageLookup = array_fill_keys($existingImageIds, true);
        foreach ($removalIds as $imageId) {
            if (!isset($existingImageLookup[$imageId])) {
                throw new InvalidArgumentException('현재 상품에 속한 이미지만 삭제할 수 있습니다.');
            }
        }

        $uploadCount = 0;
        foreach ($uploads as $upload) {
            if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_OK) {
                ++$uploadCount;
            }
        }
        $resultingImageCount = count($existingImageIds) - count($removalIds) + $uploadCount;
        if ($resultingImageCount > self::MAX_IMAGES) {
            throw new InvalidArgumentException('상품 이미지는 최대 5개까지 등록할 수 있습니다.');
        }

        return array_values($removalIds);
    }

    /** @param list<array{name:string,tmp_name:string,size:int,error:int}> $uploads */
    private function addImages(int $productId, ProductAdminDraft $draft, array $uploads, int $shopId): void
    {
        foreach ($uploads as $upload) {
            if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_NO_FILE) {
                continue;
            }
            $image = new \Image();
            $image->id_product = $productId;
            $image->position = \Image::getHighestPosition($productId) + 1;
            $image->cover = !\Image::getCover($productId, $shopId);
            $image->legend = $this->localizedValues(\Language::getLanguages(false), $draft->nameJa, $draft->nameKo);
            if (!$image->add() || !$image->associateTo([$shopId], $productId)) {
                throw new RuntimeException('상품 이미지 연결을 저장하지 못했습니다.');
            }

            $basePath = $image->getPathForCreation();
            if (!is_string($basePath) || !\ImageManager::resize((string) $upload['tmp_name'], $basePath . '.jpg')) {
                throw new RuntimeException('상품 이미지 파일을 처리하지 못했습니다.');
            }
            foreach (\ImageType::getImagesTypes('products') as $imageType) {
                $imagePath = $basePath . '-' . (string) $imageType['name'] . '.jpg';
                if (!\ImageManager::resize(
                    (string) $upload['tmp_name'],
                    $imagePath,
                    (int) $imageType['width'],
                    (int) $imageType['height']
                )) {
                    throw new RuntimeException('상품 이미지 미리보기를 만들지 못했습니다.');
                }
            }
        }
    }

    /** @param list<int> $imageIds */
    private function removeImages(int $productId, array $imageIds, int $shopId): void
    {
        foreach ($imageIds as $imageId) {
            $image = new \Image($imageId, null, $shopId);
            if (!\Validate::isLoadedObject($image) || (int) $image->id_product !== $productId) {
                throw new RuntimeException('검증된 상품 이미지를 불러오지 못했습니다.');
            }
            if (!$image->delete()) {
                throw new RuntimeException('선택한 상품 이미지를 삭제하지 못했습니다.');
            }
        }
    }

    private function optionText(int $productId, int $languageId, int $shopId): string
    {
        $lines = [];
        foreach ($this->optionGroups($productId, $languageId, $shopId) as $group) {
            $lines[] = $group['name'] . ':' . implode('|', $group['values']);
        }

        return implode("\n", $lines);
    }

    /** @param list<array<string, mixed>> $languages
     *  @return array<int,string>
     */
    private function localizedValues(array $languages, string $japanese, string $korean): array
    {
        $values = [];
        foreach ($languages as $language) {
            $id = (int) ($language['id_lang'] ?? 0);
            if ($id < 1) {
                continue;
            }
            $iso = (string) ($language['iso_code'] ?? '');
            $values[$id] = match ($iso) {
                'ko' => $korean,
                'ja' => $japanese,
                default => $japanese,
            };
        }
        if ($values === []) {
            throw new RuntimeException('PrestaShop 활성 언어를 찾지 못했습니다.');
        }

        return $values;
    }

    /** @param list<array<string, mixed>> $languages
     *  @return array<int,string>
     */
    private function localizedSlugs(array $languages, ProductAdminDraft $draft): array
    {
        $values = [];
        foreach ($languages as $language) {
            $id = (int) ($language['id_lang'] ?? 0);
            if ($id < 1) {
                continue;
            }
            $source = (string) (($language['iso_code'] ?? '') === 'ko' ? $draft->nameKo : $draft->nameJa);
            $slug = (string) \Tools::str2url($source);
            $values[$id] = $slug !== ''
                ? (string) \Tools::substr($slug, 0, 128)
                : strtolower(self::REFERENCE_PREFIX . bin2hex(random_bytes(2)));
        }

        return $values;
    }

    private function getOrCreateAttributeGroup(string $name, int $languageId, int $shopId): int
    {
        $existingId = (int) \Db::getInstance()->getValue(
            "SELECT ag.`id_attribute_group`
            FROM `" . _DB_PREFIX_ . "attribute_group` ag
            INNER JOIN `" . _DB_PREFIX_ . "attribute_group_lang` agl
                ON agl.`id_attribute_group` = ag.`id_attribute_group` AND agl.`id_lang` = " . (int) $languageId . "
            INNER JOIN `" . _DB_PREFIX_ . "attribute_group_shop` ags
                ON ags.`id_attribute_group` = ag.`id_attribute_group` AND ags.`id_shop` = " . (int) $shopId . "
            WHERE agl.`name` = '" . \pSQL($name) . "' LIMIT 1"
        );
        if ($existingId > 0) {
            return $existingId;
        }

        $names = array_fill_keys($this->languageIds(), $name);
        $container = SymfonyContainer::getInstance();
        if ($container === null || !$container->has('prestashop.core.command_bus')) {
            throw new RuntimeException('PrestaShop 옵션 관리 서비스를 사용할 수 없습니다.');
        }
        $result = $container->get('prestashop.core.command_bus')->handle(
            new AddAttributeGroupCommand($names, $names, 'select', [$shopId])
        );
        if (!is_object($result) || !method_exists($result, 'getValue')) {
            throw new RuntimeException('PrestaShop 옵션 그룹 생성을 확인하지 못했습니다.');
        }

        return (int) $result->getValue();
    }

    private function getOrCreateAttribute(int $groupId, string $name, int $languageId, int $shopId): int
    {
        $existingId = (int) \Db::getInstance()->getValue(
            "SELECT a.`id_attribute`
            FROM `" . _DB_PREFIX_ . "attribute` a
            INNER JOIN `" . _DB_PREFIX_ . "attribute_lang` al
                ON al.`id_attribute` = a.`id_attribute` AND al.`id_lang` = " . (int) $languageId . "
            INNER JOIN `" . _DB_PREFIX_ . "attribute_shop` ash
                ON ash.`id_attribute` = a.`id_attribute` AND ash.`id_shop` = " . (int) $shopId . "
            WHERE a.`id_attribute_group` = " . (int) $groupId . " AND al.`name` = '" . \pSQL($name) . "' LIMIT 1"
        );
        if ($existingId > 0) {
            return $existingId;
        }

        $names = array_fill_keys($this->languageIds(), $name);
        $container = SymfonyContainer::getInstance();
        if ($container === null || !$container->has('prestashop.core.command_bus')) {
            throw new RuntimeException('PrestaShop 옵션 관리 서비스를 사용할 수 없습니다.');
        }
        $result = $container->get('prestashop.core.command_bus')->handle(
            new AddAttributeCommand($groupId, $names, '', [$shopId])
        );
        if (!is_object($result) || !method_exists($result, 'getValue')) {
            throw new RuntimeException('PrestaShop 옵션 값 생성을 확인하지 못했습니다.');
        }

        return (int) $result->getValue();
    }

    /** @return list<int> */
    private function languageIds(): array
    {
        return array_values(array_filter(array_map(
            static fn (array $language): int => (int) ($language['id_lang'] ?? 0),
            \Language::getLanguages(false)
        ), static fn (int $id): bool => $id > 0));
    }

    private function plainTextToHtml(string $value): string
    {
        return nl2br(htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'), false);
    }

    private function htmlToPlainText(string $value): string
    {
        $withNewlines = preg_replace('/<br\s*\/?>|<\/p>/i', "\n", $value) ?? $value;

        return trim(html_entity_decode(strip_tags($withNewlines), ENT_QUOTES | ENT_HTML5, 'UTF-8'));
    }

    /** @return array{0:int,1:int} */
    private function contextIds(): array
    {
        $context = \Context::getContext();
        $languageId = (int) ($context->language->id ?? 0);
        $shopId = (int) ($context->shop->id ?? 0);
        if ($languageId < 1 || $shopId < 1) {
            throw new RuntimeException('PrestaShop 언어와 쇼핑몰 설정을 확인해 주세요.');
        }

        return [$languageId, $shopId];
    }

    private function requireJpyDefaultCurrency(): void
    {
        $currency = new \Currency((int) \Configuration::get('PS_CURRENCY_DEFAULT'));
        if ((string) $currency->iso_code !== 'JPY') {
            throw new RuntimeException('상품 관리자 등록은 기본 통화가 JPY일 때만 사용할 수 있습니다.');
        }
    }
}
