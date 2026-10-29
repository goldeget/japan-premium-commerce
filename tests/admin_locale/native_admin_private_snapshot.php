<?php
declare(strict_types=1);

/** Test-only private handoff; never writes a raw native response to artifacts. */
function persistNativeAdminSnapshot(string $kind, string $content, string $ownedRoot, string $project): void
{
    if (!in_array($kind, ['mbo', 'facebook', 'mbo-auth-landing', 'facebook-unauthenticated'], true)
        || !preg_match('/\Aordenowa-procurement-ci-[0-9]{1,20}-[0-9]{1,8}\z/D', $project)
        || strlen($content) < 100 || strlen($content) > 8 * 1024 * 1024
        || is_link($ownedRoot) || realpath($ownedRoot) !== $ownedRoot
        || !is_file($ownedRoot . '/.ordenowa-ci-project')
        || is_link($ownedRoot . '/.ordenowa-ci-project')
        || trim((string) file_get_contents($ownedRoot . '/.ordenowa-ci-project')) !== $project) {
        throw new RuntimeException('private_snapshot_guard_failed');
    }
    $directory = $ownedRoot . DIRECTORY_SEPARATOR . 'private-snapshots';
    if (is_link($directory) || !is_dir($directory) || realpath($directory) !== $directory
        || (PHP_OS_FAMILY !== 'Windows' && (fileperms($directory) & 0777) !== 0700)) {
        throw new RuntimeException('private_snapshot_directory_invalid');
    }
    $path = $directory . '/' . $kind . '.html';
    if (file_exists($path) || is_link($path)) {
        throw new RuntimeException('private_snapshot_already_exists');
    }
    $oldMask = umask(0077);
    $stream = false;
    $created = false;
    try {
        $stream = @fopen($path, 'x+b');
        if ($stream === false) throw new RuntimeException('private_snapshot_create_failed');
        $created = true;
        if (!chmod($path, 0600) || fwrite($stream, $content) !== strlen($content)
            || !fflush($stream) || (function_exists('fsync') && !fsync($stream))) {
            throw new RuntimeException('private_snapshot_write_failed');
        }
    } catch (Throwable $error) {
        if (is_resource($stream)) fclose($stream);
        $stream = false;
        if ($created) @unlink($path);
        throw new RuntimeException('private_snapshot_handoff_failed', 0, $error);
    } finally {
        if (is_resource($stream)) fclose($stream);
        umask($oldMask);
    }
}
