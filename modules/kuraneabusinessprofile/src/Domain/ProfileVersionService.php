<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

use InvalidArgumentException;

final class ProfileVersionService
{
    private const PUBLISHED_BRAND_ASSETS = [
        'header_desktop' => [
            'official-header-desktop.png' => [1600, 500],
            'header-desktop.png' => [640, 200],
        ],
        'header_mobile' => [
            'official-header-mobile.png' => [800, 250],
            'header-mobile.png' => [360, 120],
        ],
        'admin_login' => [
            'official-admin-login.png' => [1600, 500],
            'admin-login.png' => [600, 188],
        ],
        'email_logo' => [
            'official-email-logo.png' => [800, 250],
            'email-logo.png' => [480, 150],
        ],
        'og_image' => [
            'official-og-brand.png' => [1200, 630],
            'og-brand.png' => [1200, 630],
        ],
        'favicon' => ['official-favicon.ico' => [32, 32], 'favicon.ico' => [32, 32]],
        'favicon_16' => ['official-favicon-16.png' => [16, 16], 'favicon-16.png' => [16, 16]],
        'favicon_32' => ['official-favicon-32.png' => [32, 32], 'favicon-32.png' => [32, 32]],
        'apple_touch' => [
            'official-apple-touch-icon.png' => [180, 180],
            'apple-touch-icon.png' => [180, 180],
        ],
        'pwa_192' => ['official-pwa-192.png' => [192, 192], 'pwa-192.png' => [192, 192]],
        'pwa_512' => ['official-pwa-512.png' => [512, 512], 'pwa-512.png' => [512, 512]],
        'pwa_maskable_512' => [
            'official-pwa-maskable-512.png' => [512, 512],
            'pwa-maskable-512.png' => [512, 512],
        ],
    ];

    public function __construct(
        private readonly ProfileVersionRepositoryInterface $repository,
        private readonly ProfileValidator $validator,
        private readonly ?string $webRoot = null,
    ) {
    }

    public function saveDraft(int $shopId, array $profile, int $employeeId): int
    {
        if ($shopId < 1 || $employeeId < 1) {
            throw new InvalidArgumentException('Shop and employee identifiers must be positive.');
        }

        $errors = $this->validator->validateDraft($profile);
        if ($errors !== []) {
            throw new InvalidArgumentException(implode(' ', $errors));
        }

        $parentVersionId = $this->repository->loadDraft($shopId)?->id;
        $version = $this->repository->insertVersion($shopId, $profile, $employeeId, $parentVersionId);
        $this->repository->setDraftPointer($shopId, $version->id);

        return $version->id;
    }

    /** @return array{published: bool, errors: list<string>} */
    public function publish(int $shopId, int $versionId, int $employeeId): array
    {
        $version = $this->repository->find($shopId, $versionId);
        if ($version === null) {
            return ['published' => false, 'errors' => ['게시할 설정 버전을 찾을 수 없습니다.']];
        }

        $errors = $this->validator->validateForPublish($version->profile);
        foreach (array_keys(self::PUBLISHED_BRAND_ASSETS) as $asset) {
            if (!$this->hasPublishedAsset($asset, $version->profile['brand']['assets'][$asset] ?? null)) {
                $errors[] = '게시할 공식 로고·파비콘·PWA 이미지 파일을 확인해 주세요.';
                break;
            }
        }
        if ($errors !== []) {
            return ['published' => false, 'errors' => $errors];
        }

        $this->repository->publishVersion($shopId, $versionId, $employeeId);

        return ['published' => true, 'errors' => []];
    }

    private function hasPublishedAsset(string $asset, mixed $relativePath): bool
    {
        if (!is_string($relativePath)
            || preg_match('~\Aimg/ordenowa/versions/[a-f0-9]{64}/[a-zA-Z0-9-]+\.(?:png|ico)\z~D', $relativePath) !== 1
        ) {
            return false;
        }

        $expectedDimensions = self::PUBLISHED_BRAND_ASSETS[$asset][basename($relativePath)] ?? null;
        if (!is_array($expectedDimensions) || count($expectedDimensions) !== 2) {
            return false;
        }

        $root = $this->webRoot ?? (defined('_PS_ROOT_DIR_') ? (string) constant('_PS_ROOT_DIR_') : dirname(__DIR__, 4));
        $path = realpath($root);
        if ($path === false) {
            return false;
        }
        foreach (explode('/', $relativePath) as $component) {
            $path .= DIRECTORY_SEPARATOR . $component;
            if (is_link($path)) {
                return false;
            }
        }

        if (!is_file($path) || !is_readable($path)) {
            return false;
        }

        clearstatcache(true, $path);
        $size = filesize($path);
        if ($size === false || $size < 1 || $size > 16 * 1024 * 1024) {
            return false;
        }

        $bytes = file_get_contents($path);
        if (!is_string($bytes) || strlen($bytes) !== $size) {
            return false;
        }

        if ($asset === 'favicon') {
            return self::isValidPngIcon($bytes, $expectedDimensions);
        }

        return self::isValidPng($bytes, $expectedDimensions);
    }

    /** @param array{0: int, 1: int} $expectedDimensions */
    private static function isValidPng(string $bytes, array $expectedDimensions): bool
    {
        if (!function_exists('getimagesizefromstring') || !function_exists('imagecreatefromstring')
            || !str_starts_with($bytes, "\x89PNG\r\n\x1a\n")
        ) {
            return false;
        }

        $imageInfo = @getimagesizefromstring($bytes);
        if (!is_array($imageInfo)
            || ($imageInfo['mime'] ?? null) !== 'image/png'
            || ($imageInfo[0] ?? null) !== $expectedDimensions[0]
            || ($imageInfo[1] ?? null) !== $expectedDimensions[1]
        ) {
            return false;
        }

        $image = @imagecreatefromstring($bytes);
        if (!$image instanceof \GdImage) {
            return false;
        }

        $valid = imagesx($image) === $expectedDimensions[0] && imagesy($image) === $expectedDimensions[1];
        imagedestroy($image);

        return $valid;
    }

    /** @param array{0: int, 1: int} $expectedDimensions */
    private static function isValidPngIcon(string $bytes, array $expectedDimensions): bool
    {
        if (strlen($bytes) < 22) {
            return false;
        }

        $header = unpack('vreserved/vtype/vcount', substr($bytes, 0, 6));
        if (!is_array($header) || $header['reserved'] !== 0 || $header['type'] !== 1
            || $header['count'] < 1 || $header['count'] > 16
        ) {
            return false;
        }

        $directoryEnd = 6 + ($header['count'] * 16);
        if ($directoryEnd > strlen($bytes)) {
            return false;
        }

        $ranges = [];
        $hasExpectedIcon = false;
        for ($index = 0; $index < $header['count']; $index++) {
            $entryOffset = 6 + ($index * 16);
            $entry = unpack('Cwidth/Cheight/Ccolors/Creserved/vplanes/vbitCount/Vbytes/Voffset', substr($bytes, $entryOffset, 16));
            if (!is_array($entry) || $entry['reserved'] !== 0 || !in_array($entry['planes'], [0, 1], true) || $entry['bitCount'] !== 32) {
                return false;
            }

            $width = $entry['width'] === 0 ? 256 : $entry['width'];
            $height = $entry['height'] === 0 ? 256 : $entry['height'];
            if (!in_array([$width, $height], [[16, 16], [32, 32], [48, 48], [64, 64], [128, 128], [256, 256]], true)) {
                return false;
            }

            $chunkStart = $entry['offset'];
            $chunkSize = $entry['bytes'];
            $fileSize = strlen($bytes);
            if ($chunkSize < 8 || $chunkStart < $directoryEnd || $chunkStart > $fileSize - $chunkSize) {
                return false;
            }

            $png = substr($bytes, $chunkStart, $chunkSize);
            if (!str_starts_with($png, "\x89PNG\r\n\x1a\n")
                || !self::isValidPng($png, [$width, $height])
            ) {
                return false;
            }

            $ranges[] = [$chunkStart, $chunkStart + $chunkSize];
            if ($width === $expectedDimensions[0] && $height === $expectedDimensions[1]) {
                $hasExpectedIcon = true;
            }
        }

        usort($ranges, static fn (array $left, array $right): int => $left[0] <=> $right[0]);
        for ($index = 1; $index < count($ranges); $index++) {
            if ($ranges[$index][0] < $ranges[$index - 1][1]) {
                return false;
            }
        }

        return $hasExpectedIcon;
    }

    public function restoreAsDraft(int $shopId, int $versionId, int $employeeId): int
    {
        $version = $this->repository->find($shopId, $versionId);
        if ($version === null) {
            throw new InvalidArgumentException('복원할 설정 버전을 찾을 수 없습니다.');
        }

        $currentDraft = $this->repository->loadDraft($shopId);
        $currentBankAccounts = $currentDraft?->profile['bank_accounts'] ?? [];
        $targetBankAccounts = $version->profile['bank_accounts'] ?? [];
        $currentBankTransfer = self::bankTransferConfiguration($currentDraft?->profile ?? []);
        $targetBankTransfer = self::bankTransferConfiguration($version->profile);

        if ($targetBankAccounts !== $currentBankAccounts || $targetBankTransfer !== $currentBankTransfer) {
            throw new InvalidArgumentException('은행 계좌 관리 권한이 필요한 버전은 일반 설정에서 복원할 수 없습니다.');
        }

        return $this->saveDraft($shopId, $version->profile, $employeeId);
    }

    public function restoreBankAccountsAsDraft(int $shopId, int $versionId, int $employeeId): int
    {
        $version = $this->repository->find($shopId, $versionId);
        $currentDraft = $this->repository->loadDraft($shopId);
        if ($version === null || $currentDraft === null) {
            throw new InvalidArgumentException('복원할 은행 계좌 또는 현재 초안을 찾을 수 없습니다.');
        }

        $profile = $currentDraft->profile;
        $profile['bank_accounts'] = $version->profile['bank_accounts'] ?? [];
        $paymentMethods = $profile['payment_methods'] ?? [];
        if (!is_array($paymentMethods)) {
            $paymentMethods = [];
        }
        $paymentMethods['bank_transfer'] = self::bankTransferConfiguration($version->profile);
        $profile['payment_methods'] = $paymentMethods;

        return $this->saveDraft($shopId, $profile, $employeeId);
    }

    /** @return list<ProfileVersion> */
    public function history(int $shopId): array
    {
        return $this->repository->history($shopId);
    }

    /** @param array<string, mixed> $profile
     *  @return array{enabled: bool, bank_account_id: string}
     */
    private static function bankTransferConfiguration(array $profile): array
    {
        $settings = $profile['payment_methods']['bank_transfer'] ?? [];
        if (!is_array($settings)) {
            $settings = [];
        }

        return [
            'enabled' => ($settings['enabled'] ?? false) === true,
            'bank_account_id' => is_string($settings['bank_account_id'] ?? null)
                ? $settings['bank_account_id']
                : '',
        ];
    }
}
