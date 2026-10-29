<?php

declare(strict_types=1);
namespace Ordenowa\Procurement\Integration;

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Recorder;
use Ordenowa\Procurement\Security\Actor;

/** Append-only, shop-scoped service disclosures. No seller or logistics inputs. */
final class PolicyService
{
    public const LOCALES = ['ja', 'en', 'ko'];
    public const SECTIONS = ['terms', 'privacy', 'points'];

    public function __construct(private readonly Database $db) {}

    public static function emptyPayload(): array
    {
        return ['operator_name' => '', 'support_email' => '', 'support_phone' => '', 'support_url' => '',
            'terms' => array_fill_keys(self::LOCALES, ''), 'privacy' => array_fill_keys(self::LOCALES, ''), 'points' => array_fill_keys(self::LOCALES, '')];
    }

    public function current(int $shop): array
    {
        if ($shop < 1) throw new \InvalidArgumentException('쇼핑몰을 확인해 주세요.', 422);
        $row = $this->db->one('SELECT * FROM ' . $this->db->table('policy') . ' WHERE id_shop=' . $shop . ' ORDER BY version DESC LIMIT 1');
        if ($row === null) return ['id_policy' => 0, 'version' => 0, 'payload' => self::emptyPayload(), 'created_at' => null];
        try {
            $row['payload'] = $this->validate(json_decode((string) $row['payload'], true, 16, JSON_THROW_ON_ERROR));
        } catch (\Throwable $error) {
            throw new \RuntimeException('운영 정책 기록을 확인할 수 없습니다.', 503, $error);
        }
        $row['id_policy'] = (int) $row['id_policy'];
        $row['version'] = (int) $row['version'];
        return $row;
    }

    public function save(Actor $actor, int $version, array $payload): array
    {
        $actor->require('policy.manage');
        if ($version < 0) throw new \InvalidArgumentException('정책 버전을 확인해 주세요.', 422);
        $payload = $this->validate($payload);
        if ($this->unresolvedFields($payload) !== []) {
            throw new \InvalidArgumentException('미확정 자리표시를 실제 승인된 문구로 바꾼 뒤 저장해 주세요.', 422);
        }
        try {
            return $this->db->transaction(function () use ($actor, $version, $payload): array {
            $current = $this->db->one('SELECT id_policy,version FROM ' . $this->db->table('policy') . ' WHERE id_shop=' . $actor->shopId . ' ORDER BY version DESC LIMIT 1 FOR UPDATE');
            if ((int) ($current['version'] ?? 0) !== $version) throw new \RuntimeException('정책이 다른 화면에서 변경되었습니다. 최신 내용을 다시 확인해 주세요.', 409);
            $next = $version + 1;
            $this->db->execute('INSERT INTO ' . $this->db->table('policy') . ' (id_shop,version,payload,id_employee,created_at) VALUES ('
                . $actor->shopId . ',' . $next . ',' . $this->db->quote(json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE)) . ',' . $actor->id . ',UTC_TIMESTAMP())');
            $id = $this->db->insertId();
            (new Recorder($this->db))->audit($actor, 'policy.updated', 'policy', $id, ['version' => $next]);
            return ['id_policy' => $id, 'version' => $next, 'payload' => $payload];
            });
        } catch (\Throwable $error) {
            if ($error->getCode() === 409) throw $error;
            for ($cause = $error; $cause !== null; $cause = $cause->getPrevious()) {
                $code = (int) $cause->getCode();
                $driver = $cause instanceof \PDOException ? (int) ($cause->errorInfo[1] ?? 0) : 0;
                if (in_array($code, [1062,1205,1213,23000,40001], true) || in_array($driver, [1062,1205,1213], true)) {
                    throw new \RuntimeException('다른 운영자가 정책을 저장했습니다. 최신 버전에서 다시 확인해 주세요.', 409, $error);
                }
            }
            throw new \RuntimeException('운영 정책을 저장하지 못했습니다. 최신 내역을 확인한 뒤 다시 시도해 주세요.', 503, $error);
        }
    }

    /** Public only after actual operator/contact and all three policy translations are entered. */
    public function published(int $shop): ?array
    {
        $current = $this->current($shop);
        return $this->missing($current['payload']) === [] ? ['version' => $current['version'], 'payload' => $current['payload']] : null;
    }

    public function history(Actor $actor): array
    {
        $actor->require('policy.read');
        return $this->db->all('SELECT id_policy,version,id_employee,created_at FROM ' . $this->db->table('policy')
            . ' WHERE id_shop=' . $actor->shopId . ' ORDER BY version DESC LIMIT 20');
    }

    public function missing(array $payload): array
    {
        $missing = $this->unresolvedFields($payload);
        foreach (['operator_name', 'support_email'] as $field) if (trim((string) ($payload[$field] ?? '')) === '') $missing[] = $field;
        foreach (self::SECTIONS as $section) foreach (self::LOCALES as $locale) if (trim((string) ($payload[$section][$locale] ?? '')) === '') $missing[] = $section . '.' . $locale;
        return array_values(array_unique($missing));
    }

    /** Preserve old draft rows for editing while keeping them out of public reads. */
    private function unresolvedFields(array $payload): array
    {
        $unresolved = [];
        foreach (['operator_name', 'support_email', 'support_phone', 'support_url'] as $field) {
            if ($this->hasUnresolvedMarker((string) ($payload[$field] ?? ''))) $unresolved[] = $field;
        }
        foreach (self::SECTIONS as $section) foreach (self::LOCALES as $locale) {
            if ($this->hasUnresolvedMarker((string) ($payload[$section][$locale] ?? ''))) $unresolved[] = $section . '.' . $locale;
        }
        return $unresolved;
    }

    private function hasUnresolvedMarker(string $text): bool
    {
        // Include broken/unclosed markers, not only today's five draft tokens.
        return str_contains($text, '{{') || str_contains($text, '}}');
    }

    private function validate(mixed $payload): array
    {
        if (!is_array($payload)) throw new \InvalidArgumentException('운영 정책 형식을 확인해 주세요.', 422);
        $clean = self::emptyPayload();
        foreach (['operator_name' => 500, 'support_email' => 254, 'support_phone' => 100, 'support_url' => 2048] as $field => $limit) {
            $clean[$field] = $this->text($payload[$field] ?? '', $limit);
        }
        if ($clean['support_email'] !== '' && filter_var($clean['support_email'], FILTER_VALIDATE_EMAIL) === false) throw new \InvalidArgumentException('고객 지원 이메일 주소를 확인해 주세요.', 422);
        if ($clean['support_url'] !== '') {
            $url = parse_url($clean['support_url']);
            if (filter_var($clean['support_url'], FILTER_VALIDATE_URL) === false || !is_array($url) || ($url['scheme'] ?? '') !== 'https'
                || isset($url['user']) || isset($url['pass']) || empty($url['host'])) throw new \InvalidArgumentException('고객 지원 URL은 인증 정보 없는 HTTPS 주소를 입력해 주세요.', 422);
        }
        foreach (self::SECTIONS as $section) {
            if (!is_array($payload[$section] ?? [])) throw new \InvalidArgumentException('정책 언어별 형식을 확인해 주세요.', 422);
            foreach (self::LOCALES as $locale) $clean[$section][$locale] = $this->text($payload[$section][$locale] ?? '', 30000);
        }
        return $clean;
    }

    private function text(mixed $value, int $limit): string
    {
        if (!is_string($value) || strlen($value) > $limit || preg_match('//u', $value) !== 1 || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F]/', $value)) throw new \InvalidArgumentException('입력 내용의 형식 또는 길이를 확인해 주세요.', 422);
        return trim($value);
    }
}
