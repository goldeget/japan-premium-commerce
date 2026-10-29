<?php
declare(strict_types=1);
require __DIR__ . '/native_admin_private_snapshot.php';
$root = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'ordenowa-snapshot-' . bin2hex(random_bytes(8));
mkdir($root, 0700);
$root = realpath($root);
$directory = $root . '/private-snapshots';
mkdir($directory, 0700);
chmod($directory, 0700);
$project = 'ordenowa-procurement-ci-431-2';
file_put_contents($root . '/.ordenowa-ci-project', $project);
$body = '<html><body data-token="PRIVATE_NATIVE_TOKEN">' . str_repeat('fixed text ', 20) . '</body></html>';
$reject = static function (callable $action): void {
    try { $action(); } catch (RuntimeException) { return; }
    throw new RuntimeException('invalid_snapshot_handoff_accepted');
};
try {
    $reject(fn () => persistNativeAdminSnapshot('mbo', $body, $root, 'ordenowa-procurement-ci-999-1'));
    $reject(fn () => persistNativeAdminSnapshot('../escape', $body, $root, $project));
    $reject(fn () => persistNativeAdminSnapshot('mbo', str_repeat('x', 8 * 1024 * 1024 + 1), $root, $project));
    $reject(fn () => persistNativeAdminSnapshot('mbo-auth-landing/../escape', $body, $root, $project));
    persistNativeAdminSnapshot('mbo', $body, $root, $project);
    $path = $directory . '/mbo.html';
    if (file_get_contents($path) !== $body || (PHP_OS_FAMILY !== 'Windows' && (fileperms($path) & 0777) !== 0600)) {
        throw new RuntimeException('private_handoff_bytes_or_mode_invalid');
    }
    $reject(fn () => persistNativeAdminSnapshot('mbo', 'replacement' . $body, $root, $project));
    if (file_get_contents($path) !== $body) throw new RuntimeException('private_snapshot_was_overwritten');
    $envelope = json_encode([
        'scope' => 'synthetic', 'status' => 200, 'request_uri' => '/admin-kuranea/x',
        'body_base64' => base64_encode($body),
    ], JSON_THROW_ON_ERROR);
    $binaryBody = "\x00\xFFbroken-utf8";
    $binaryEnvelope = json_encode([
        'scope' => 'synthetic', 'status' => 502, 'request_uri' => '/admin-kuranea/x',
        'body_base64' => base64_encode($binaryBody),
    ], JSON_THROW_ON_ERROR);
    $decodedEnvelope = json_decode($binaryEnvelope, true, 8, JSON_THROW_ON_ERROR);
    if (base64_decode($decodedEnvelope['body_base64'], true) !== $binaryBody) {
        throw new RuntimeException('binary_native_response_bytes_not_preserved');
    }
    persistNativeAdminSnapshot('mbo-auth-landing', $envelope, $root, $project);
    persistNativeAdminSnapshot('facebook-unauthenticated', $envelope, $root, $project);
    foreach (['mbo-auth-landing.html', 'facebook-unauthenticated.html'] as $name) {
        $capturePath = $directory . '/' . $name;
        if (file_get_contents($capturePath) !== $envelope
            || (PHP_OS_FAMILY !== 'Windows' && (fileperms($capturePath) & 0777) !== 0600)) {
            throw new RuntimeException('private_debug_envelope_bytes_or_mode_invalid');
        }
        $reject(fn () => persistNativeAdminSnapshot(pathinfo($name, PATHINFO_FILENAME), 'replacement' . $envelope, $root, $project));
    }
    if (PHP_OS_FAMILY !== 'Windows') {
        chmod($directory, 0755);
        clearstatcache();
        $reject(fn () => persistNativeAdminSnapshot('facebook', $body, $root, $project));
        chmod($directory, 0700);
        symlink($path, $directory . '/facebook.html');
        $reject(fn () => persistNativeAdminSnapshot('facebook', $body, $root, $project));
        unlink($directory . '/facebook.html');
    }
    echo "PASS private native snapshot bytes, ownership marker, permissions and no overwrite\n";
} finally {
    foreach (['mbo.html', 'facebook.html', 'mbo-auth-landing.html', 'facebook-unauthenticated.html'] as $name) {
        if (is_file($directory . '/' . $name) || is_link($directory . '/' . $name)) unlink($directory . '/' . $name);
    }
    unlink($root . '/.ordenowa-ci-project');
    rmdir($directory);
    rmdir($root);
}
