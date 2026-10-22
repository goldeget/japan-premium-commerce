<?php

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

$options = getopt('', ['file:']);
$csvFile = is_array($options) && isset($options['file']) ? (string) $options['file'] : '';
if ($csvFile === '' || !is_file($csvFile) || !is_readable($csvFile)) {
    fwrite(STDERR, "Usage: php modules/kuraneapostcode/bin/import-ken-all.php --file=/absolute/path/to/KEN_ALL.CSV\n");
    exit(2);
}

$shopRoot = dirname(__DIR__, 3);
$configFile = $shopRoot . '/config/config.inc.php';
if (!is_file($configFile)) {
    fwrite(STDERR, "PrestaShop config/config.inc.php was not found. Run this command from an installed shop checkout.\n");
    exit(2);
}

require_once $configFile;
require_once dirname(__DIR__) . '/autoload.php';

use Kuranea\Postcode\Domain\KenAllCsvImporter;
use Kuranea\Postcode\Domain\KenAllCsvParser;
use Kuranea\Postcode\Infrastructure\DatabaseSchema;

$database = Db::getInstance();
$mainTable = _DB_PREFIX_ . 'kuraneapostcode_address';
$exists = (int) $database->getValue(
    'SELECT COUNT(*) FROM information_schema.tables'
    . ' WHERE table_schema = DATABASE() AND table_name = \'' . pSQL($mainTable) . '\''
);
if ($exists !== 1) {
    fwrite(STDERR, "The module address table is missing. Install KURANEA Japan Postcode Lookup from the Back Office first.\n");
    exit(2);
}

if (!$database->execute(DatabaseSchema::createStageTableSql(_DB_PREFIX_))) {
    fwrite(STDERR, "Unable to create the module staging table. Existing postcode data was not changed.\n");
    exit(1);
}

$stageTable = '`' . _DB_PREFIX_ . 'kuraneapostcode_stage`';
$mainTableSql = '`' . $mainTable . '`';
if (!$database->execute('TRUNCATE TABLE ' . $stageTable)) {
    fwrite(STDERR, "Unable to reset the module staging table. Existing postcode data was not changed.\n");
    exit(1);
}

try {
    $importer = new KenAllCsvImporter(new KenAllCsvParser());
    $summary = $importer->import($csvFile, static function ($address) use ($database): void {
        $ok = $database->insert('kuraneapostcode_stage', [
            'candidate_id' => $address->candidateId,
            'postcode' => $address->postcode,
            'jis_code' => $address->jisCode,
            'prefecture' => $address->prefecture,
            'municipality' => $address->municipality,
            'town' => $address->town,
        ], false, false, Db::INSERT_IGNORE);

        if (!$ok) {
            throw new RuntimeException('Could not write a parsed address to the staging table.');
        }
    });

    $stagedCount = (int) $database->getValue('SELECT COUNT(*) FROM ' . $stageTable);
    if ($summary->imported < 1 || $stagedCount < 1) {
        throw new RuntimeException('The supplied CSV had no valid address rows; existing data was not replaced.');
    }

    if (!$database->execute('START TRANSACTION')) {
        throw new RuntimeException('Could not start the postcode data replacement transaction.');
    }
    if (!$database->execute('DELETE FROM ' . $mainTableSql)) {
        $database->execute('ROLLBACK');
        throw new RuntimeException('Could not replace the module postcode rows.');
    }
    $copy = 'INSERT INTO ' . $mainTableSql
        . ' (`candidate_id`,`postcode`,`jis_code`,`prefecture`,`municipality`,`town`)'
        . ' SELECT `candidate_id`,`postcode`,`jis_code`,`prefecture`,`municipality`,`town` FROM ' . $stageTable;
    if (!$database->execute($copy) || !$database->execute('COMMIT')) {
        $database->execute('ROLLBACK');
        throw new RuntimeException('Postcode data replacement failed; the transaction was rolled back.');
    }

    // Keep the production address table as the source of truth, not a second
    // full copy of Japan Post's dataset. The staging table is disposable once
    // the validated replacement transaction has committed.
    if (!$database->execute('TRUNCATE TABLE ' . $stageTable)) {
        fwrite(STDERR, "Warning: postcode data is active but the staging table could not be cleared.\n");
    }

    fwrite(STDOUT, sprintf(
        "Imported %d valid CSV rows (%d unique candidates); skipped %d malformed rows.\n",
        $summary->imported,
        $stagedCount,
        $summary->skipped
    ));
} catch (Throwable $exception) {
    fwrite(STDERR, 'Import failed: ' . $exception->getMessage() . "\n");
    exit(1);
}
