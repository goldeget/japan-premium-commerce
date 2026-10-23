<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use InvalidArgumentException;
use RuntimeException;

final class BrandAssetProcessor
{
    public const MAX_BYTES = 10 * 1024 * 1024;
    private const MAX_DIMENSION = 8192;
    private const MAX_PIXELS = 40000000;

    /**
     * @return array{
     *   source: array{path: string, sha256: string, mime: string, width: int, height: int},
     *   assets: array<string, string>
     * }
     */
    public static function process(string $slot, string $bytes, string $webRoot, string $privateRoot): array
    {
        $definitions = self::definitions();
        if (!isset($definitions[$slot])) {
            throw new InvalidArgumentException('알 수 없는 브랜드 이미지 구분입니다.');
        }
        if ($bytes === '' || strlen($bytes) > self::MAX_BYTES) {
            throw new InvalidArgumentException('브랜드 원본 이미지는 10MiB 이하로 업로드해 주세요.');
        }

        $mime = (new \finfo(FILEINFO_MIME_TYPE))->buffer($bytes);
        $mimeToExtension = ['image/png' => 'png', 'image/jpeg' => 'jpg', 'image/webp' => 'webp'];
        $extension = is_string($mime) ? ($mimeToExtension[$mime] ?? null) : null;
        if ($extension === null) {
            throw new InvalidArgumentException('PNG, JPEG, WebP 이미지만 업로드할 수 있습니다.');
        }

        $imageInfo = @getimagesizefromstring($bytes);
        if (!is_array($imageInfo) || !isset($imageInfo[0], $imageInfo[1], $imageInfo['mime'])
            || $imageInfo['mime'] !== $mime
        ) {
            throw new InvalidArgumentException('이미지 형식과 실제 파일 데이터가 일치하지 않습니다.');
        }
        $width = (int) $imageInfo[0];
        $height = (int) $imageInfo[1];
        if ($width < 32 || $height < 32 || $width > self::MAX_DIMENSION || $height > self::MAX_DIMENSION
            || $width * $height > self::MAX_PIXELS
        ) {
            throw new InvalidArgumentException('이미지 크기는 각 변 32~8192px, 전체 4천만 픽셀 이하로 등록해 주세요.');
        }

        $decoded = @imagecreatefromstring($bytes);
        if (!$decoded instanceof \GdImage) {
            throw new InvalidArgumentException('이미지를 안전하게 읽지 못했습니다.');
        }

        $sourceHash = hash('sha256', $bytes);
        $privateRelative = 'source/' . $slot . '/' . $sourceHash . '.' . $extension;
        $privatePath = rtrim($privateRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $privateRelative;
        self::ensureDirectory(dirname($privatePath), 0700);
        self::denyPublicAccess($privateRoot);
        self::writeImmutable($privatePath, $bytes, $sourceHash, 0600);

        $source = self::cropTransparent($decoded);
        $versionRoot = rtrim($webRoot, DIRECTORY_SEPARATOR) . '/img/ordenowa/versions/' . $sourceHash;
        self::ensureDirectory($versionRoot, 0755);
        $assets = [];
        foreach ($definitions[$slot] as $assetKey => $definition) {
            if ($assetKey === 'favicon') {
                $png = self::pngBytes($source, 32, 32);
                $filename = 'favicon.ico';
                $output = self::icoFromPng($png);
            } else {
                [$targetWidth, $targetHeight] = $definition['size'];
                $filename = $definition['filename'];
                $output = self::pngBytes(
                    $source,
                    $targetWidth,
                    $targetHeight,
                    (float) ($definition['safe_area'] ?? 1.0),
                    (bool) ($definition['opaque_white_background'] ?? false)
                );
            }

            $path = $versionRoot . DIRECTORY_SEPARATOR . $filename;
            self::writeImmutable($path, $output, hash('sha256', $output), 0644);
            $assets[$assetKey] = 'img/ordenowa/versions/' . $sourceHash . '/' . $filename;
        }

        return [
            'source' => [
                'path' => $privateRelative,
                'sha256' => $sourceHash,
                'mime' => (string) $mime,
                'width' => $width,
                'height' => $height,
            ],
            'assets' => $assets,
        ];
    }

    /** @return array<string, array<string, array<string, mixed>>> */
    private static function definitions(): array
    {
        return [
            'primary_logo' => [
                'header_desktop' => ['filename' => 'header-desktop.png', 'size' => [640, 200]],
                'header_mobile' => ['filename' => 'header-mobile.png', 'size' => [360, 120]],
                'admin_login' => ['filename' => 'admin-login.png', 'size' => [600, 188]],
                'email_logo' => ['filename' => 'email-logo.png', 'size' => [480, 150]],
                'og_image' => ['filename' => 'og-brand.png', 'size' => [1200, 630], 'opaque_white_background' => true],
            ],
            'favicon_symbol' => [
                'favicon' => ['filename' => 'favicon.ico', 'size' => [32, 32]],
                'favicon_16' => ['filename' => 'favicon-16.png', 'size' => [16, 16]],
                'favicon_32' => ['filename' => 'favicon-32.png', 'size' => [32, 32]],
            ],
            'pwa_icon' => [
                'apple_touch' => ['filename' => 'apple-touch-icon.png', 'size' => [180, 180]],
                'pwa_192' => ['filename' => 'pwa-192.png', 'size' => [192, 192]],
                'pwa_512' => ['filename' => 'pwa-512.png', 'size' => [512, 512]],
                'pwa_maskable_512' => ['filename' => 'pwa-maskable-512.png', 'size' => [512, 512], 'safe_area' => 0.8],
            ],
        ];
    }

    private static function cropTransparent(\GdImage $image): \GdImage
    {
        $cropped = @imagecropauto($image, IMG_CROP_TRANSPARENT);

        return $cropped instanceof \GdImage ? $cropped : $image;
    }

    private static function pngBytes(\GdImage $source, int $width, int $height, float $safeArea = 1.0, bool $white = false): string
    {
        if (!function_exists('imagecreatetruecolor') || !function_exists('imagecopyresampled')) {
            throw new RuntimeException('이미지 파생 파일을 만들려면 GD 이미지 기능이 필요합니다.');
        }
        if ($safeArea <= 0 || $safeArea > 1) {
            throw new InvalidArgumentException('이미지 안전 영역 설정이 올바르지 않습니다.');
        }

        $canvas = imagecreatetruecolor($width, $height);
        imagealphablending($canvas, $white);
        imagesavealpha($canvas, true);
        $background = $white
            ? imagecolorallocate($canvas, 255, 255, 255)
            : imagecolorallocatealpha($canvas, 0, 0, 0, 127);
        imagefill($canvas, 0, 0, $background);

        $sourceWidth = imagesx($source);
        $sourceHeight = imagesy($source);
        $fitWidth = max(1, (int) floor($width * $safeArea));
        $fitHeight = max(1, (int) floor($height * $safeArea));
        $scale = min($fitWidth / $sourceWidth, $fitHeight / $sourceHeight);
        $destinationWidth = max(1, (int) round($sourceWidth * $scale));
        $destinationHeight = max(1, (int) round($sourceHeight * $scale));
        $destinationX = (int) floor(($width - $destinationWidth) / 2);
        $destinationY = (int) floor(($height - $destinationHeight) / 2);
        imagecopyresampled($canvas, $source, $destinationX, $destinationY, 0, 0, $destinationWidth, $destinationHeight, $sourceWidth, $sourceHeight);

        ob_start();
        imagepng($canvas, null, 9);
        $bytes = ob_get_clean();
        if (!is_string($bytes) || $bytes === '') {
            throw new RuntimeException('이미지 파생 파일을 만들지 못했습니다.');
        }

        return $bytes;
    }

    private static function icoFromPng(string $png): string
    {
        $header = pack('vvv', 0, 1, 1);
        $entry = pack('CCCCvvVV', 32, 32, 0, 0, 1, 32, strlen($png), 22);

        return $header . $entry . $png;
    }

    private static function ensureDirectory(string $directory, int $mode): void
    {
        if ($directory === '' || $directory[0] !== DIRECTORY_SEPARATOR) {
            throw new RuntimeException('이미지 저장 경로는 절대 경로여야 합니다.');
        }

        $components = explode(DIRECTORY_SEPARATOR, trim($directory, DIRECTORY_SEPARATOR));
        $currentDirectory = DIRECTORY_SEPARATOR;
        foreach ($components as $component) {
            if ($component === '' || $component === '.') {
                continue;
            }
            if ($component === '..') {
                throw new RuntimeException('이미지 저장 경로에 상위 경로 이동을 사용할 수 없습니다.');
            }

            $currentDirectory = rtrim($currentDirectory, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $component;
            if (is_link($currentDirectory)) {
                throw new RuntimeException('이미지 경로에는 심볼릭 링크를 사용할 수 없습니다.');
            }
            if (!is_dir($currentDirectory)
                && !mkdir($currentDirectory, $mode)
                && !is_dir($currentDirectory)
            ) {
                throw new RuntimeException('이미지 저장 디렉터리를 준비하지 못했습니다.');
            }
            if (is_link($currentDirectory) || !is_dir($currentDirectory)) {
                throw new RuntimeException('이미지 경로에는 심볼릭 링크를 사용할 수 없습니다.');
            }
        }

        if (!is_writable($currentDirectory)) {
            throw new RuntimeException('이미지 저장 디렉터리 권한을 확인해 주세요.');
        }
    }

    private static function denyPublicAccess(string $privateRoot): void
    {
        self::ensureDirectory($privateRoot, 0700);
        $path = rtrim($privateRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . '.htaccess';
        $rules = implode(PHP_EOL, ['Options -Indexes', 'Require all denied', 'Deny from all']) . PHP_EOL;
        self::writeImmutable($path, $rules, hash('sha256', $rules), 0600);
    }

    private static function writeImmutable(string $path, string $bytes, string $expectedHash, int $mode): void
    {
        if (is_link($path)) {
            throw new RuntimeException('이미지 경로에는 심볼릭 링크를 사용할 수 없습니다.');
        }

        if (is_file($path)) {
            if (hash_file('sha256', $path) !== $expectedHash) {
                throw new RuntimeException('기존 이미지 원본을 덮어쓰지 않고 안전하게 보존합니다.');
            }

            return;
        }

        $temporary = tempnam(dirname($path), '.ordenowa-');
        if ($temporary === false) {
            throw new RuntimeException('이미지 파일 임시 저장에 실패했습니다.');
        }
        try {
            $written = file_put_contents($temporary, $bytes, LOCK_EX);
            if ($written !== strlen($bytes)) {
                throw new RuntimeException('이미지 파일을 완전히 저장하지 못했습니다.');
            }
            chmod($temporary, $mode);
            if (!rename($temporary, $path)) {
                throw new RuntimeException('이미지 파일을 보존 경로로 이동하지 못했습니다.');
            }
        } finally {
            if (is_file($temporary)) {
                unlink($temporary);
            }
        }
    }
}
