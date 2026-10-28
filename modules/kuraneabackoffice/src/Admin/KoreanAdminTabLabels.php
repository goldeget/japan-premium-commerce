<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Admin;

/** Installation-only repair of known upstream Korean tab-name fallbacks. */
final class KoreanAdminTabLabels
{
    private const LABELS = [
        ['AdminPsdistributionapiclientCommunity', 'ps_distributionapiclient', 'Community', '커뮤니티'],
        ['AdminPsdistributionapiclient', 'ps_distributionapiclient', 'Wall of Fame', '명예의 전당'],
        ['AdminSecurity', '', 'Security', '보안'],
        ['AdminParentSecurity', '', 'Security', '보안'],
        ['AdminExtraPropertyDefinitions', '', 'Extra Properties', '추가 속성'],
    ];

    public static function repair(object $database, int $koreanLanguageId, string $prefix): bool
    {
        if ($koreanLanguageId < 1 || preg_match('/\A[A-Za-z0-9_]{1,64}\z/D', $prefix) !== 1
            || !method_exists($database, 'execute')) {
            return false;
        }
        foreach (self::LABELS as [$controller, $module, $fallback, $translation]) {
            // The native module owner and controller identify system metadata.
            // Existing custom wording and every non-Korean language stay intact.
            $moduleCondition = $module === '' ? "(t.module IS NULL OR t.module = '')" : 't.module = ' . self::quote($module);
            $sql = 'INSERT INTO `' . $prefix . 'tab_lang` (id_tab, id_lang, name)'
                . ' SELECT t.id_tab, ' . $koreanLanguageId . ', ' . self::quote($translation)
                . ' FROM `' . $prefix . 'tab` t WHERE t.class_name = ' . self::quote($controller)
                . ' AND ' . $moduleCondition
                . ' ON DUPLICATE KEY UPDATE name = CASE'
                . ' WHEN BINARY name IN (' . self::quote('') . ', ' . self::quote($fallback) . ')'
                . ' THEN VALUES(name) ELSE name END';
            if (!$database->execute($sql)) {
                return false;
            }
        }
        return true;
    }

    private static function quote(string $literal): string
    {
        // Only the fixed source literals above reach this helper.
        return "'" . str_replace("'", "''", $literal) . "'";
    }
}
