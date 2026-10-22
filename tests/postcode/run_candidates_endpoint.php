<?php

declare(strict_types=1);

if (!defined('_DB_PREFIX_')) {
    define('_DB_PREFIX_', 'ps_');
}

if (!defined('_PS_VERSION_')) {
    define('_PS_VERSION_', '9.2.0');
}

if (!function_exists('pSQL')) {
    function pSQL(string $value): string
    {
        return str_replace("'", "\\'", $value);
    }
}

if (!class_exists('Tools')) {
    class Tools
    {
        public static function getValue(string $key, $default = false)
        {
            return $_POST[$key] ?? $_GET[$key] ?? $default;
        }
    }
}

if (!class_exists('Db')) {
    class Db
    {
        private static ?self $instance = null;

        public static function getInstance($slave = false): self
        {
            return self::$instance ??= new self();
        }

        public function executeS(string $query): array
        {
            if (!str_starts_with($query, 'SELECT ')
                || !str_contains($query, '`ps_kuraneapostcode_address`')
                || !str_contains($query, "`postcode` = '999-9999'")) {
                throw new RuntimeException('Candidate lookup must use a read-only query on the normalized postcode.');
            }

            return [[
                'postcode' => '999-9999',
                'jis_code' => '13101',
                'prefecture' => '東京都',
                'municipality' => '千代田区',
                'town' => 'テスト町（次のビルを除く）',
            ]];
        }
    }
}

if (!class_exists('Country')) {
    class Country
    {
        public static function getByIso(string $isoCode): int|false
        {
            return strtoupper($isoCode) === 'JP' ? 392 : false;
        }
    }
}

if (!class_exists('State')) {
    class State
    {
        public static function getStatesByIdCountry(
            int $countryId,
            bool $active = false,
            ?string $orderBy = null,
            string $sort = 'ASC'
        ): array {
            return $countryId === 392 ? [['id_state' => 43, 'iso_code' => 'JP-13']] : [];
        }
    }
}

if (!class_exists('ModuleFrontController')) {
    class ModuleFrontController
    {
        protected function ajaxRender($value = null, $controller = null, $method = null): void
        {
            echo (string) $value;
        }
    }
}

require_once __DIR__ . '/../../modules/kuraneapostcode/autoload.php';
require_once __DIR__ . '/../../modules/kuraneapostcode/controllers/front/candidates.php';

$_SERVER['REQUEST_METHOD'] = 'GET';
$_GET = ['q' => '9999999'];
(new KuraneapostcodeCandidatesModuleFrontController())->initContent();
