<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';

use Kuranea\Backoffice\AdminDocumentLanguage;

$decoyDocument = '<!doctype html><!-- Embedded example: <html lang="ja-JP" data-example="decoy"> -->'
    . '<html lang="en" data-root="yes"><head></head><body>ORDENOWA</body></html>';
$expectedDocument = '<!doctype html><!-- Embedded example: <html lang="ja-JP" data-example="decoy"> -->'
    . '<html lang="ko-KR" data-root="yes"><head></head><body>ORDENOWA</body></html>';
$localizedDocument = AdminDocumentLanguage::setRootLocale($decoyDocument, 'ko-KR');

if ($localizedDocument !== $expectedDocument) {
    fwrite(STDERR, "The Korean locale helper must update the document root and preserve embedded HTML examples.\n");
    exit(1);
}

$alreadyKorean = '<!doctype html><html lang="ko-KR"><body>ORDENOWA</body></html>';
if (AdminDocumentLanguage::setRootLocale($alreadyKorean, 'ko-KR') !== $alreadyKorean) {
    fwrite(STDERR, "An already-Korean document root must remain unchanged.\n");
    exit(1);
}

if (AdminDocumentLanguage::setRootLocale('<p>No document root</p>', 'ko-KR') !== null) {
    fwrite(STDERR, "A fragment without a document root must not be localized.\n");
    exit(1);
}

$prefixedDocument = "\xEF\xBB\xBF \n<!-- first example <html lang=\"fr\"> -->\n"
    . '<!DOCTYPE html [<!ENTITY sample "quoted > delimiter">]>'
    . "\n<HTML data-example='one > two' LANG='ja-JP' id=root><body>ORDENOWA</body></HTML>";
$expectedPrefixedDocument = "\xEF\xBB\xBF \n<!-- first example <html lang=\"fr\"> -->\n"
    . '<!DOCTYPE html [<!ENTITY sample "quoted > delimiter">]>'
    . "\n<HTML data-example='one > two' LANG=\"ko-KR\" id=root><body>ORDENOWA</body></HTML>";
if (AdminDocumentLanguage::setRootLocale($prefixedDocument, 'ko-KR') !== $expectedPrefixedDocument) {
    fwrite(STDERR, "Leading markup, uppercase tags, and quoted delimiters must preserve the actual document root.\n");
    exit(1);
}

$rootWithoutLanguage = '<!-- decoy <html lang="fr"> --><html data-root="yes"><body>ORDENOWA</body></html>';
$expectedRootWithoutLanguage = '<!-- decoy <html lang="fr"> --><html data-root="yes" lang="ko-KR"><body>ORDENOWA</body></html>';
if (AdminDocumentLanguage::setRootLocale($rootWithoutLanguage, 'ko-KR') !== $expectedRootWithoutLanguage) {
    fwrite(STDERR, "A missing language attribute must be added to the actual document root only.\n");
    exit(1);
}

fwrite(STDOUT, "PASS: only the Korean document root was localized.\n");
