<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

final class PublicSitemapRepository
{
    public function countEntries(
        int $shopId,
        int $langId,
        int $rootCategoryId,
        int $homeCategoryId,
        bool $groupFeatureActive,
        int $guestGroupId
    ): ?int {
        if ($shopId < 1 || $langId < 1) {
            return null;
        }

        $subquery = $this->candidateQuery(
            $shopId,
            $langId,
            $rootCategoryId,
            $homeCategoryId,
            $groupFeatureActive,
            $guestGroupId
        );
        $count = \Db::getInstance()->getValue('SELECT COUNT(*) FROM (' . $subquery . ') sitemap_candidates');

        return is_numeric($count) ? (int) $count : null;
    }

    /** @return list<array{kind: string, id: int, link_rewrite: string}>|null */
    public function entries(
        int $shopId,
        int $langId,
        int $rootCategoryId,
        int $homeCategoryId,
        int $offset,
        int $limit,
        bool $groupFeatureActive,
        int $guestGroupId
    ): ?array {
        if ($shopId < 1 || $langId < 1 || $offset < 0 || $limit < 1 || $limit > 10000) {
            return null;
        }

        $subquery = $this->candidateQuery(
            $shopId,
            $langId,
            $rootCategoryId,
            $homeCategoryId,
            $groupFeatureActive,
            $guestGroupId
        );
        $rows = \Db::getInstance()->executeS(
            'SELECT kind, id, link_rewrite
            FROM (' . $subquery . ') sitemap_candidates
            ORDER BY kind ASC, id ASC
            LIMIT ' . (int) $offset . ', ' . (int) $limit
        );
        if (!is_array($rows)) {
            return null;
        }

        $entries = [];
        foreach ($rows as $row) {
            if (!is_array($row) || !isset($row['kind'], $row['id'], $row['link_rewrite'])
                || !in_array($row['kind'], ['category', 'product'], true)
                || (int) $row['id'] < 1 || trim((string) $row['link_rewrite']) === ''
            ) {
                continue;
            }
            $entries[] = [
                'kind' => (string) $row['kind'],
                'id' => (int) $row['id'],
                'link_rewrite' => (string) $row['link_rewrite'],
            ];
        }

        return $entries;
    }

    private function candidateQuery(
        int $shopId,
        int $langId,
        int $rootCategoryId,
        int $homeCategoryId,
        bool $groupFeatureActive,
        int $guestGroupId
    ): string {
        $shopId = max(1, $shopId);
        $langId = max(1, $langId);
        $guestGroupId = max(0, $guestGroupId);
        $excludedCategories = array_values(array_filter(
            array_unique([$rootCategoryId, $homeCategoryId]),
            static fn (int $id): bool => $id > 0
        ));
        $excludedSql = $excludedCategories === [] ? '' : ' AND c.id_category NOT IN (' . implode(',', array_map('intval', $excludedCategories)) . ')';
        $categoryGuestAccessSql = $groupFeatureActive
            ? ' AND EXISTS (
                SELECT 1 FROM ' . _DB_PREFIX_ . 'category_group cg
                WHERE cg.id_category = c.id_category AND cg.id_group = ' . $guestGroupId . '
            )'
            : '';
        $productGuestAccessSql = $groupFeatureActive
            ? ' AND EXISTS (
                SELECT 1
                FROM ' . _DB_PREFIX_ . 'category_product cp
                INNER JOIN ' . _DB_PREFIX_ . 'category_group cg
                    ON cg.id_category = cp.id_category AND cg.id_group = ' . $guestGroupId . '
                INNER JOIN ' . _DB_PREFIX_ . 'category c_public
                    ON c_public.id_category = cp.id_category AND c_public.active = 1
                INNER JOIN ' . _DB_PREFIX_ . 'category_shop cs_public
                    ON cs_public.id_category = cp.id_category AND cs_public.id_shop = ' . $shopId . '
                WHERE cp.id_product = ps.id_product
            )'
            : '';

        return "SELECT 'category' AS kind, c.id_category AS id, cl.link_rewrite AS link_rewrite
            FROM " . _DB_PREFIX_ . "category c
            INNER JOIN " . _DB_PREFIX_ . "category_shop cs
                ON cs.id_category = c.id_category AND cs.id_shop = " . $shopId . "
            INNER JOIN " . _DB_PREFIX_ . "category_lang cl
                ON cl.id_category = c.id_category AND cl.id_shop = " . $shopId . " AND cl.id_lang = " . $langId . "
            WHERE c.active = 1" . $excludedSql . $categoryGuestAccessSql . "
                AND TRIM(cl.name) <> '' AND TRIM(cl.link_rewrite) <> ''
            UNION ALL
            SELECT 'product' AS kind, ps.id_product AS id, pl.link_rewrite AS link_rewrite
            FROM " . _DB_PREFIX_ . "product p
            INNER JOIN " . _DB_PREFIX_ . "product_shop ps
                ON ps.id_product = p.id_product AND ps.id_shop = " . $shopId . "
            INNER JOIN " . _DB_PREFIX_ . "product_lang pl
                ON pl.id_product = ps.id_product AND pl.id_shop = " . $shopId . " AND pl.id_lang = " . $langId . "
            WHERE p.active = 1 AND ps.active = 1 AND ps.indexed = 1
                AND ps.visibility IN ('both', 'catalog') AND ps.show_price = 1" . $productGuestAccessSql . "
                AND TRIM(pl.name) <> '' AND TRIM(pl.link_rewrite) <> ''";
    }
}
