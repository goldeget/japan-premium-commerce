<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Infrastructure;

use InvalidArgumentException;
use RuntimeException;

/** Read-only, shop-scoped view of PrestaShop's persisted order state history. */
final class OrderHistoryAuditRepository
{
    private object $database;
    private string $prefix;

    public function __construct(?object $database = null, ?string $prefix = null)
    {
        if ($database === null) {
            if (!class_exists('Db')) {
                throw new RuntimeException('PrestaShop database service is not available.');
            }
            $database = \Db::getInstance();
        }

        $this->database = $database;
        $this->prefix = $prefix ?? (defined('_DB_PREFIX_') ? (string) _DB_PREFIX_ : '');
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $this->prefix) !== 1) {
            throw new RuntimeException('PrestaShop table prefix is invalid.');
        }
    }

    /**
     * @return array{rows:list<array{id_order_history:int,id_order:int,reference:string,id_order_state:int,state_name:string,id_employee:?int,date_add:string}>,has_next:bool}
     */
    public function pageForShop(int $shopId, int $languageId, int $page): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        self::assertPositiveId($languageId, '언어');
        if ($page < 1 || $page > intdiv(PHP_INT_MAX, 50)) {
            throw new InvalidArgumentException('주문 이력 페이지가 올바르지 않습니다.');
        }
        $offset = ($page - 1) * 50;
        $rows = $this->database->executeS(
            'SELECT oh.`id_order_history`, oh.`id_order`, o.`reference`, oh.`id_order_state`'
            . ', COALESCE(osl.`name`, \'\') AS `state_name`, oh.`id_employee`, oh.`date_add`'
            . ' FROM `' . $this->prefix . 'order_history` oh'
            . ' INNER JOIN `' . $this->prefix . 'orders` o ON o.`id_order` = oh.`id_order`'
            . ' LEFT JOIN `' . $this->prefix . 'order_state_lang` osl'
            . ' ON osl.`id_order_state` = oh.`id_order_state` AND osl.`id_lang` = ' . $languageId
            . ' WHERE o.`id_shop` = ' . $shopId
            . ' ORDER BY oh.`date_add` DESC, oh.`id_order_history` DESC LIMIT 51 OFFSET ' . $offset,
            true,
            false
        );
        if (!is_array($rows)) {
            throw new RuntimeException('주문 상태 변경 이력을 불러오지 못했습니다.');
        }

        $hasNext = count($rows) > 50;
        if ($hasNext) {
            array_pop($rows);
        }

        return [
            'rows' => array_map(static fn (array $row): array => [
                'id_order_history' => (int) ($row['id_order_history'] ?? 0),
                'id_order' => (int) ($row['id_order'] ?? 0),
                'reference' => (string) ($row['reference'] ?? ''),
                'id_order_state' => (int) ($row['id_order_state'] ?? 0),
                'state_name' => (string) ($row['state_name'] ?? ''),
                'id_employee' => isset($row['id_employee']) && (int) $row['id_employee'] > 0
                    ? (int) $row['id_employee']
                    : null,
                'date_add' => (string) ($row['date_add'] ?? ''),
            ], $rows),
            'has_next' => $hasNext,
        ];
    }

    private static function assertPositiveId(int $id, string $label): void
    {
        if ($id < 1) {
            throw new InvalidArgumentException($label . ' ID가 올바르지 않습니다.');
        }
    }
}
