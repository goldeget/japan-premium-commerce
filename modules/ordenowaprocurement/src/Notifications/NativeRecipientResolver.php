<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Notifications;

use Ordenowa\Procurement\Infrastructure\Database;

final class NativeRecipientResolver
{
    private const TARGETS = [
        'assignment.created' => ['assignment', 'id_assignment'], 'assignment.revoked' => ['assignment', 'id_assignment'],
        'request.submitted' => ['request', 'id_request'], 'request.reviewed' => ['request', 'id_request'],
        'points.awarded' => ['point_ledger', 'id_ledger'], 'points.corrected' => ['point_ledger', 'id_ledger'],
    ];

    public function __construct(private readonly Database $db, private readonly string $nativePrefix)
    {
        if (preg_match('/^[A-Za-z0-9_]+$/D', $nativePrefix) !== 1) {
            throw new \InvalidArgumentException('Invalid native table prefix.');
        }
    }

    public function resolve(array $event): ?array
    {
        $definition = self::TARGETS[$event['event'] ?? ''] ?? null;
        $shop = (int) ($event['id_shop'] ?? 0);
        $customer = (int) ($event['id_customer'] ?? 0);
        $target = (int) ($event['target_id'] ?? 0);
        if ($definition === null || ($event['target_type'] ?? '') !== $definition[0] || $shop < 1 || $customer < 1 || $target < 1) {
            return null;
        }
        if ($this->db->one('SELECT ' . $definition[1] . ' FROM ' . $this->db->table($definition[0]) . ' WHERE ' . $definition[1] . '=' . $target
            . ' AND id_shop=' . $shop . ' AND id_customer=' . $customer) === null) {
            return null;
        }
        $recipient = $this->db->one('SELECT c.id_customer,c.id_shop,c.id_lang,c.email,l.iso_code AS locale FROM `' . $this->nativePrefix . 'customer` c'
            . ' INNER JOIN `' . $this->nativePrefix . 'lang` l ON l.id_lang=c.id_lang AND l.active=1'
            . ' INNER JOIN `' . $this->nativePrefix . 'lang_shop` ls ON ls.id_lang=c.id_lang AND ls.id_shop=c.id_shop'
            . ' WHERE c.id_customer=' . $customer . ' AND c.id_shop=' . $shop . ' AND c.active=1 AND c.deleted=0 AND c.is_guest=0');
        if ($recipient === null || !in_array($recipient['locale'], ['ja', 'en', 'ko'], true)
            || !filter_var($recipient['email'], FILTER_VALIDATE_EMAIL)) {
            return null;
        }
        return $recipient;
    }
}
