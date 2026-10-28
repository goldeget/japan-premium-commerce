<?php

declare(strict_types=1);

require dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';
use Kuranea\Backoffice\Admin\KoreanAdminTabLabels;

$dsn = getenv('PROCUREMENT_TEST_DSN');
if (!$dsn || !str_contains($dsn, 'dbname=ordenowa_procurement_test')) {
    fwrite(STDERR, "Isolated procurement test DB required for Korean metadata tests.\n");
    exit(2);
}
$pdo = new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: '', [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$prefix = 'kolabel_' . bin2hex(random_bytes(4)) . '_';
$checks = 0;
$assert = static function (bool $condition) use (&$checks): void { ++$checks; if (!$condition) throw new RuntimeException('Korean administrator metadata contract failed'); };
$db = new class($pdo) {
    public function __construct(private PDO $pdo) {}
    public function execute(string $sql): bool { $this->pdo->exec($sql); return true; }
};
try {
    $pdo->exec('CREATE TABLE `' . $prefix . 'tab` (id_tab INT PRIMARY KEY,class_name VARCHAR(100),module VARCHAR(100),wording VARCHAR(100)) ENGINE=InnoDB');
    $pdo->exec('CREATE TABLE `' . $prefix . 'tab_lang` (id_tab INT,id_lang INT,name VARCHAR(100),PRIMARY KEY(id_tab,id_lang)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');
    $pdo->exec('CREATE TABLE `' . $prefix . 'access` (id_profile INT,id_tab INT,permission VARCHAR(10)) ENGINE=InnoDB');
    $tabs = [[1,'AdminPsdistributionapiclientCommunity','ps_distributionapiclient','Community'],[2,'AdminPsdistributionapiclient','ps_distributionapiclient','Wall of Fame'],[3,'AdminSecurity','','Security'],[4,'AdminExtraPropertyDefinitions',null,'Extra Properties'],[5,'CustomModule','','Custom item'],[6,'AdminParentSecurity','','Security']];
    $insert = $pdo->prepare('INSERT INTO `' . $prefix . 'tab` VALUES (?,?,?,?)');
    foreach ($tabs as $tab) $insert->execute($tab);
    $insert = $pdo->prepare('INSERT INTO `' . $prefix . 'tab_lang` VALUES (?,?,?)');
    foreach ($tabs as $tab) foreach ([1,2,3] as $language) $insert->execute([$tab[0],$language,$tab[3]]);
    $pdo->exec('INSERT INTO `' . $prefix . 'access` VALUES (1,3,"READ"),(2,4,"READ")');
    $snapshot = static fn(string $table): string => hash('sha256', json_encode($pdo->query('SELECT * FROM `' . $prefix . $table . '` ORDER BY 1,2')->fetchAll(PDO::FETCH_ASSOC),JSON_THROW_ON_ERROR));
    $tabHash = $snapshot('tab'); $accessHash = $snapshot('access');
    $otherLanguages = $pdo->query('SELECT * FROM `' . $prefix . 'tab_lang` WHERE id_lang <> 3 ORDER BY 1,2')->fetchAll(PDO::FETCH_ASSOC);
    $assert(KoreanAdminTabLabels::repair($db,3,$prefix));
    $names = $pdo->query('SELECT id_tab,name FROM `' . $prefix . 'tab_lang` WHERE id_lang=3 ORDER BY id_tab')->fetchAll(PDO::FETCH_KEY_PAIR);
    $assert($names === [1=>'커뮤니티',2=>'명예의 전당',3=>'보안',4=>'추가 속성',5=>'Custom item',6=>'보안']);
    $assert($otherLanguages === $pdo->query('SELECT * FROM `' . $prefix . 'tab_lang` WHERE id_lang <> 3 ORDER BY 1,2')->fetchAll(PDO::FETCH_ASSOC));
    $assert($tabHash === $snapshot('tab') && $accessHash === $snapshot('access'));
    $firstHash = $snapshot('tab_lang');
    $assert(KoreanAdminTabLabels::repair($db,3,$prefix) && $firstHash === $snapshot('tab_lang'));
    $pdo->exec('UPDATE `' . $prefix . 'tab_lang` SET name="Custom Korean admin menu" WHERE id_tab=1 AND id_lang=3');
    $pdo->exec('UPDATE `' . $prefix . 'tab_lang` SET name="community" WHERE id_tab=2 AND id_lang=3');
    $pdo->exec('UPDATE `' . $prefix . 'tab_lang` SET name="" WHERE id_tab=3 AND id_lang=3');
    $pdo->exec('DELETE FROM `' . $prefix . 'tab_lang` WHERE id_tab=4 AND id_lang=3');
    $assert(KoreanAdminTabLabels::repair($db,3,$prefix));
    $names = $pdo->query('SELECT id_tab,name FROM `' . $prefix . 'tab_lang` WHERE id_lang=3 ORDER BY id_tab')->fetchAll(PDO::FETCH_KEY_PAIR);
    $assert($names[1] === 'Custom Korean admin menu' && $names[2] === 'community');
    $assert($names[3] === '보안' && $names[4] === '추가 속성');
    $pdo->exec('UPDATE `' . $prefix . 'tab` SET module="other_module" WHERE id_tab=3');
    $pdo->exec('UPDATE `' . $prefix . 'tab_lang` SET name="Security" WHERE id_tab=3 AND id_lang=3');
    $assert(KoreanAdminTabLabels::repair($db,3,$prefix));
    $assert($pdo->query('SELECT name FROM `' . $prefix . 'tab_lang` WHERE id_tab=3 AND id_lang=3')->fetchColumn() === 'Security');
    $before = $snapshot('tab_lang');
    $assert(!KoreanAdminTabLabels::repair($db,0,$prefix) && !KoreanAdminTabLabels::repair($db,3,'unsafe`prefix'));
    $assert($before === $snapshot('tab_lang'));
    echo 'PASS Korean native tab labels: ' . $checks . ' real MariaDB checks, Korean-only exact fallback CAS, custom/other locales/metadata/ACL preserved, missing row and idempotence' . PHP_EOL;
} finally {
    foreach (['access','tab_lang','tab'] as $table) $pdo->exec('DROP TABLE IF EXISTS `' . $prefix . $table . '`');
}
