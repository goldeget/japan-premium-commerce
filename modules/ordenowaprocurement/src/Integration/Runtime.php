<?php

declare(strict_types=1);

namespace Ordenowa\Procurement\Integration;

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Requests\RequestService;
use Ordenowa\Procurement\Points\PointService;
use Ordenowa\Procurement\Security\Actor;

/** The only adapter from native session, shop and ACL to domain identities. */
final class Runtime
{
    public static function procurementEnabled(): bool
    {
        return getenv('ORDENOWA_APP_MODE') === 'procurement';
    }

    public static function database(): Database
    {
        return new Database(\Db::getInstance(), _DB_PREFIX_);
    }

    public static function requests(): RequestService
    {
        return new RequestService(self::database());
    }

    public static function points(): PointService
    {
        return new PointService(self::database());
    }

    public static function policies(): PolicyService
    {
        return new PolicyService(self::database());
    }

    public static function customerActor(): Actor
    {
        self::requireEnabled();
        $context = \Context::getContext();
        $shop = self::shopId();
        $customer = $context->customer;
        if (!$customer || !method_exists($customer, 'isLogged') || !$customer->isLogged()
            || (int) $customer->id < 1) {
            throw new \RuntimeException('인증 또는 권한을 확인할 수 없습니다.', 403);
        }
        self::validateCustomer((int) $customer->id);
        return Actor::customer($shop, (int) $customer->id);
    }

    public static function employeeActor(): Actor
    {
        self::requireEnabled();
        $context = \Context::getContext();
        $shop = self::shopId();
        $employee = $context->employee;
        if (!$employee || !method_exists($employee, 'isLoggedBack') || !$employee->isLoggedBack()
            || (int) $employee->id < 1 || !(bool) $employee->active) {
            throw new \RuntimeException('관리자 인증 또는 권한을 확인할 수 없습니다.', 403);
        }
        $db = self::database();
        $native = $db->one('SELECT id_employee, id_profile FROM ' . self::nativeTable('employee')
            . ' WHERE id_employee=' . (int) $employee->id . ' AND active=1');
        if (!$native || (int) $native['id_profile'] !== (int) $employee->id_profile
            || !$db->one('SELECT id_employee FROM ' . self::nativeTable('employee_shop')
                . ' WHERE id_employee=' . (int) $employee->id . ' AND id_shop=' . $shop)) {
            throw new \RuntimeException('현재 쇼핑몰에 접근할 권한이 없습니다.', 403);
        }
        $permissions = [];
        $assignmentRead = self::nativePermission('AdminOrdenowaProcurement', 'READ');
        $reviewRead = self::nativePermission('AdminOrdenowaProcurementReviews', 'READ');
        $pointsRead = self::nativePermission('AdminOrdenowaProcurementPoints', 'READ');
        if ($assignmentRead || $reviewRead || $pointsRead) {
            $permissions[] = 'procurement.read';
        }
        if ($assignmentRead && (self::nativePermission('AdminOrdenowaProcurement', 'ADD')
                || self::nativePermission('AdminOrdenowaProcurement', 'EDIT'))) {
            $permissions[] = 'procurement.manage';
        }
        if ($reviewRead && self::nativePermission('AdminOrdenowaProcurementReviews', 'EDIT')) {
            $permissions[] = 'procurement.review';
        }
        if ($pointsRead) {
            $permissions[] = 'points.read';
            if (self::nativePermission('AdminOrdenowaProcurementPoints', 'ADD')) {
                $permissions[] = 'points.award';
            }
            if (self::nativePermission('AdminOrdenowaProcurementPoints', 'EDIT')) {
                $permissions[] = 'points.correct';
            }
        }
        if (self::nativePermission('AdminOrdenowaProcurementAudit', 'READ')) {
            $permissions[] = 'audit.read';
        }
        if (self::nativePermission('AdminOrdenowaProcurementPolicies', 'READ')) {
            $permissions[] = 'policy.read';
            if (self::nativePermission('AdminOrdenowaProcurementPolicies', 'EDIT')) $permissions[] = 'policy.manage';
        }
        return Actor::employee($shop, (int) $employee->id, $permissions);
    }

    public static function nativePermission(string $tab, string $action): bool
    {
        $employee = \Context::getContext()->employee;
        if (!$employee || (int) $employee->id < 1 || !in_array($action, ['READ', 'ADD', 'EDIT', 'DELETE'], true)
            || (int) \Tab::getIdFromClassName($tab) < 1) {
            return false;
        }
        $nativeAction = ['READ' => 'READ', 'ADD' => 'CREATE', 'EDIT' => 'UPDATE', 'DELETE' => 'DELETE'][$action];
        $role = \Access::sluggifyTab(['class_name' => $tab], $nativeAction);
        return \Access::isGranted($role, (int) $employee->id_profile);
    }

    /** Validate a target using native persisted identity, never a submitted snapshot. */
    public static function validateCustomer(int $customerId): void
    {
        $db = self::database();
        if ($customerId < 1 || !$db->one('SELECT id_customer FROM ' . self::nativeTable('customer')
                . ' WHERE id_customer=' . $customerId . ' AND id_shop=' . self::shopId()
                . ' AND active=1 AND deleted=0 AND is_guest=0')) {
            throw new \RuntimeException('현재 쇼핑몰의 활성 회원을 선택해 주세요.', 404);
        }
    }

    /** Small native pickers include hidden products; no sale flags are changed. */
    public static function assignmentChoices(): array
    {
        self::employeeActor()->require('procurement.read');
        $db = self::database();
        $shop = self::shopId();
        $language = (int) (\Context::getContext()->language->id ?? 0);
        $customers = $db->all('SELECT id_customer,firstname,lastname FROM ' . self::nativeTable('customer')
            . ' WHERE id_shop=' . $shop . ' AND active=1 AND deleted=0 AND is_guest=0 ORDER BY id_customer DESC LIMIT 100');
        $products = $db->all('SELECT p.id_product,p.reference,pl.name,ps.active FROM ' . self::nativeTable('product') . ' p'
            . ' INNER JOIN ' . self::nativeTable('product_shop') . ' ps ON ps.id_product=p.id_product AND ps.id_shop=' . $shop
            . ' LEFT JOIN ' . self::nativeTable('product_lang') . ' pl ON pl.id_product=p.id_product AND pl.id_shop=' . $shop . ' AND pl.id_lang=' . $language
            . ' ORDER BY p.id_product DESC LIMIT 100');
        $variants = $db->all('SELECT pa.id_product_attribute,pa.id_product,pa.reference FROM ' . self::nativeTable('product_attribute') . ' pa'
            . ' INNER JOIN ' . self::nativeTable('product_attribute_shop') . ' pas ON pas.id_product_attribute=pa.id_product_attribute AND pas.id_shop=' . $shop
            . ' INNER JOIN ' . self::nativeTable('product_shop') . ' ps ON ps.id_product=pa.id_product AND ps.id_shop=' . $shop
            . ' ORDER BY pa.id_product_attribute DESC LIMIT 200');
        $images = $db->all('SELECT i.id_image,i.id_product FROM ' . self::nativeTable('image') . ' i'
            . ' INNER JOIN ' . self::nativeTable('image_shop') . ' ims ON ims.id_image=i.id_image AND ims.id_shop=' . $shop
            . ' INNER JOIN ' . self::nativeTable('product_shop') . ' ps ON ps.id_product=i.id_product AND ps.id_shop=' . $shop
            . ' ORDER BY i.id_image DESC LIMIT 200');
        return ['customers' => $customers, 'products' => $products, 'variants' => $variants, 'images' => $images];
    }

    public static function productReference(int $productId, int $attributeId = 0, array $manualImageRights = []): array
    {
        self::requireEnabled();
        $db = self::database();
        $shop = self::shopId();
        if ($productId < 1 || $attributeId < 0) {
            throw new \RuntimeException('상품 또는 옵션을 확인해 주세요.', 422);
        }
        $product = $db->one('SELECT p.id_product,p.reference FROM ' . self::nativeTable('product') . ' p'
            . ' INNER JOIN ' . self::nativeTable('product_shop') . ' ps ON ps.id_product=p.id_product'
            . ' WHERE p.id_product=' . $productId . ' AND ps.id_shop=' . $shop);
        if (!$product) {
            throw new \RuntimeException('현재 쇼핑몰의 상품을 찾을 수 없습니다.', 404);
        }
        $attributes = $db->all('SELECT pa.id_product_attribute,pa.reference FROM ' . self::nativeTable('product_attribute') . ' pa'
            . ' INNER JOIN ' . self::nativeTable('product_attribute_shop') . ' pas ON pas.id_product_attribute=pa.id_product_attribute'
            . ' WHERE pa.id_product=' . $productId . ' AND pas.id_shop=' . $shop);
        $selected = null;
        foreach ($attributes as $attribute) {
            if ((int) $attribute['id_product_attribute'] === $attributeId) {
                $selected = $attribute;
            }
        }
        if (($attributes !== [] && $selected === null) || ($attributeId > 0 && $selected === null)) {
            throw new \RuntimeException('해당 상품에 속한 정확한 옵션을 선택해 주세요.', 422);
        }
        $translations = $db->all('SELECT l.iso_code,pl.name,pl.description,pl.description_short,pl.link_rewrite'
            . ' FROM ' . self::nativeTable('product_lang') . ' pl INNER JOIN ' . self::nativeTable('lang') . ' l ON l.id_lang=pl.id_lang'
            . ' WHERE pl.id_product=' . $productId . ' AND pl.id_shop=' . $shop);
        $names = $descriptions = [];
        foreach ($translations as $translation) {
            if (in_array($translation['iso_code'], ['ja', 'en', 'ko'], true)) {
                $names[$translation['iso_code']] = trim(strip_tags((string) $translation['name']));
                $descriptions[$translation['iso_code']] = trim(strip_tags((string) ($translation['description'] ?: $translation['description_short'])));
            }
        }
        $fallback = $names['ja'] ?? $names['en'] ?? $names['ko'] ?? '';
        if ($fallback === '') {
            throw new \RuntimeException('표시할 상품명이 없습니다.', 422);
        }
        foreach (['ja', 'en', 'ko'] as $locale) {
            $names[$locale] = $names[$locale] ?? $fallback;
            $descriptions[$locale] = $descriptions[$locale] ?? '';
        }
        if ($attributeId > 0) {
            $options = $db->all('SELECT l.iso_code,agl.name AS group_name,al.name AS attribute_name FROM '
                . self::nativeTable('product_attribute_combination') . ' pac'
                . ' INNER JOIN ' . self::nativeTable('attribute') . ' a ON a.id_attribute=pac.id_attribute'
                . ' INNER JOIN ' . self::nativeTable('attribute_lang') . ' al ON al.id_attribute=a.id_attribute'
                . ' INNER JOIN ' . self::nativeTable('attribute_group_lang') . ' agl ON agl.id_attribute_group=a.id_attribute_group AND agl.id_lang=al.id_lang'
                . ' INNER JOIN ' . self::nativeTable('lang') . ' l ON l.id_lang=al.id_lang'
                . ' WHERE pac.id_product_attribute=' . $attributeId . ' ORDER BY a.id_attribute_group,a.id_attribute');
            $localizedOptions = [];
            foreach ($options as $option) {
                if (in_array($option['iso_code'], ['ja', 'en', 'ko'], true)) {
                    $localizedOptions[$option['iso_code']][] = trim(strip_tags((string) $option['group_name'])) . ': ' . trim(strip_tags((string) $option['attribute_name']));
                }
            }
            foreach (['ja', 'en', 'ko'] as $locale) {
                $labels = $localizedOptions[$locale] ?? $localizedOptions['ja'] ?? $localizedOptions['en'] ?? $localizedOptions['ko'] ?? [];
                if ($labels !== []) {
                    $names[$locale] .= ' · ' . implode(' / ', $labels);
                }
            }
        }
        $evidenceClass = '\\Ordenowa\\Procurement\\Catalog\\ReviewedProductEvidence';
        $evidence = class_exists($evidenceClass) ? (new $evidenceClass($db))->forProduct($shop, $productId) : [];
        if (str_starts_with((string) $product['reference'], 'OWA-IMPORT-') && empty($evidence['reviewed'])) {
            throw new \RuntimeException('수집 상품의 검토·출처 근거를 확인해 주세요.', 422);
        }
        $manualRights = [];
        if ($manualImageRights !== []) {
            $employee = self::employeeActor();
            $employee->require('procurement.manage');
            if (!self::nativePermission('AdminOrdenowaProcurement', 'ADD') || str_starts_with((string) $product['reference'], 'OWA-IMPORT-')) {
                throw new \RuntimeException('수집 상품의 이미지 권리는 원본 검토에서 확인해야 합니다.', 403);
            }
            $attestation = $manualImageRights['attestation'] ?? null;
            $ids = $manualImageRights['image_ids'] ?? null;
            if (!is_string($attestation) || trim($attestation) === '' || strlen($attestation) > 2000 || preg_match('//u', $attestation) !== 1
                || !is_array($ids) || $ids === [] || count($ids) > 20) throw new \InvalidArgumentException('이미지 권리 근거와 1~20개의 이미지 번호를 입력해 주세요.', 422);
            foreach ($ids as $id) if (!is_int($id) || $id < 1) throw new \InvalidArgumentException('이미지 번호 형식을 확인해 주세요.', 422);
            $ids = array_values(array_unique($ids));
            $actualImages = $db->all('SELECT i.id_image FROM ' . self::nativeTable('image') . ' i'
                . ' INNER JOIN ' . self::nativeTable('image_shop') . ' ims ON ims.id_image=i.id_image'
                . ' WHERE i.id_product=' . $productId . ' AND ims.id_shop=' . $shop . ' AND i.id_image IN (' . implode(',', $ids) . ')');
            $actualIds = array_map(static fn (array $row): int => (int) $row['id_image'], $actualImages);
            sort($ids); sort($actualIds);
            if ($ids !== $actualIds) throw new \RuntimeException('선택한 이미지가 현재 쇼핑몰의 지정 상품에 속하지 않습니다.', 422);
            $manualRights = ['kind' => 'operator-attestation', 'attestation' => trim($attestation), 'id_employee' => $employee->id, 'image_ids' => $ids];
        }
        $imageUrls = [];
        $approvedImages = array_filter(array_map('intval', $evidence['approved_image_ids'] ?? []), static fn (int $id): bool => $id > 0);
        if ($manualRights !== []) $approvedImages = $manualRights['image_ids'];
        $approvedImages = array_slice(array_values(array_unique($approvedImages)), 0, 20);
        if ($approvedImages !== []) {
            $images = $db->all('SELECT i.id_image FROM ' . self::nativeTable('image') . ' i'
                . ' INNER JOIN ' . self::nativeTable('image_shop') . ' ims ON ims.id_image=i.id_image'
                . ' WHERE i.id_product=' . $productId . ' AND ims.id_shop=' . $shop
                . ' AND i.id_image IN (' . implode(',', $approvedImages) . ') ORDER BY i.position ASC,i.id_image ASC LIMIT 20');
            foreach ($images as $image) {
                $url = self::nativeImagePath((int) $image['id_image']);
                if ($url !== '') $imageUrls[] = $url;
            }
        }
        $imageUrl = $imageUrls[0] ?? '';
        return [
            'shop_id' => $shop, 'id_product' => $productId, 'id_product_attribute' => $attributeId,
            'names' => $names, 'descriptions' => $descriptions, 'image_url' => $imageUrl, 'image_urls' => $imageUrls,
            'reference' => (string) (($selected['reference'] ?? '') ?: $product['reference']),
            'source_url' => (string) ($evidence['source_url'] ?? ''),
            'categories' => self::productCategories($productId, $shop),
            'reference_price' => (string) ($evidence['reference_price'] ?? ''),
            'currency' => (string) ($evidence['currency'] ?? ''),
            ...($manualRights !== [] ? ['image_rights' => $manualRights] : []),
        ];
    }

    /** Existing native public derivatives only; no remote fetch or new publication. */
    private static function nativeImagePath(int $image): string
    {
        if ($image < 1 || !defined('_PS_PROD_IMG_DIR_')) return '';
        $base = realpath((string) _PS_PROD_IMG_DIR_);
        if ($base === false) return '';
        $folder = implode('/', str_split((string) $image)) . '/';
        foreach (['-large_default', '-home_default', '-medium_default', ''] as $type) {
            foreach (['jpg', 'jpeg', 'png', 'webp'] as $extension) {
                $relative = $folder . $image . $type . '.' . $extension;
                $file = realpath($base . '/' . $relative);
                if ($file !== false && is_file($file) && str_starts_with($file, $base . DIRECTORY_SEPARATOR)) {
                    return '/img/p/' . $relative;
                }
            }
        }
        return '';
    }

    private static function productCategories(int $product, int $shop): array
    {
        $db = self::database();
        $rows = $db->all('SELECT DISTINCT c.id_category,c.id_parent,c.level_depth,l.iso_code,cl.name FROM ' . self::nativeTable('category_product') . ' cp'
            . ' INNER JOIN ' . self::nativeTable('category') . ' leaf ON leaf.id_category=cp.id_category'
            . ' INNER JOIN ' . self::nativeTable('category') . ' c ON c.nleft<=leaf.nleft AND c.nright>=leaf.nright'
            . ' INNER JOIN ' . self::nativeTable('category_shop') . ' cs ON cs.id_category=c.id_category AND cs.id_shop=' . $shop
            . ' INNER JOIN ' . self::nativeTable('category_lang') . ' cl ON cl.id_category=c.id_category AND cl.id_shop=' . $shop
            . ' INNER JOIN ' . self::nativeTable('lang') . ' l ON l.id_lang=cl.id_lang'
            . ' WHERE cp.id_product=' . $product . ' AND c.is_root_category=0 ORDER BY c.level_depth,c.id_category');
        $categories = [];
        foreach ($rows as $row) {
            if (!in_array($row['iso_code'], ['ja', 'en', 'ko'], true)) {
                continue;
            }
            $id = (int) $row['id_category'];
            $categories[$id]['id_category'] = $id;
            $categories[$id]['id_parent'] = (int) $row['id_parent'];
            $categories[$id]['names'][$row['iso_code']] = trim(strip_tags((string) $row['name']));
        }
        foreach ($categories as &$category) {
            $fallback = $category['names']['ja'] ?? $category['names']['en'] ?? $category['names']['ko'] ?? '';
            foreach (['ja', 'en', 'ko'] as $locale) {
                $category['names'][$locale] = $category['names'][$locale] ?? $fallback;
            }
        }
        unset($category);
        return array_values($categories);
    }

    private static function nativeTable(string $name): string
    {
        $prefix = (string) _DB_PREFIX_;
        if (preg_match('/\A[A-Za-z0-9_]+\z/D', $prefix . $name) !== 1) {
            throw new \RuntimeException('Invalid native table name.');
        }
        return '`' . $prefix . $name . '`';
    }

    private static function shopId(): int
    {
        $shop = (int) (\Context::getContext()->shop->id ?? 0);
        if ($shop < 1 || \Shop::getContext() !== \Shop::CONTEXT_SHOP) {
            throw new \RuntimeException('쇼핑몰 하나를 선택해 주세요.', 403);
        }
        return $shop;
    }

    private static function requireEnabled(): void
    {
        if (!self::procurementEnabled()) {
            throw new \RuntimeException('상품 발주 서비스가 활성화되지 않았습니다.', 503);
        }
    }
}
