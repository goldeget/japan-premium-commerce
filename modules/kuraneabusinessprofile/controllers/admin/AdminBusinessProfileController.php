<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\BusinessProfile\Admin\AdminAccessPolicy;
use Kuranea\BusinessProfile\Admin\AdminProfileForm;
use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Domain\ProfileValidator;
use Kuranea\BusinessProfile\Domain\ProfileVersionService;
use Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

class AdminBusinessProfileController extends ModuleAdminController
{
    private string $ordenowaFeedback = '';
    private bool $ordenowaFeedbackIsError = false;
    private ?array $ordenowaPreviewProfile = null;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '쇼핑몰 운영 설정';
    }

    public function initContent(): void
    {
        $this->viewAccess();
        $this->access('edit');
        $this->access('add');

        if (!AdminAccessPolicy::canView((array) ($this->tabAccess ?? []))) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">쇼핑몰 운영 설정을 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        $repository = new VersionedProfileRepository();
        $validator = new ProfileValidator();
        $service = new ProfileVersionService($repository, $validator);
        $shopId = $this->shopId();
        $employeeId = (int) ($this->context->employee->id ?? 0);

        $this->processProfileActions($repository, $service, $validator, $shopId, $employeeId);

        parent::initContent();

        $draft = $repository->loadDraft($shopId);
        $profile = $draft?->profile ?? ProfileDefaults::initial();
        $published = $repository->loadPublished($shopId);
        $adminUrl = (string) $this->context->link->getAdminLink('AdminBusinessProfile');
        $bankUrl = (string) $this->context->link->getAdminLink('AdminBusinessProfileBanks');
        $token = (string) Tools::getAdminTokenLite('AdminBusinessProfile');
        $canPublish = AdminAccessPolicy::canPublish((array) ($this->tabAccess ?? []));

        $this->content .= $this->renderFeedback();
        $this->content .= $this->renderSellerApproval($profile, $adminUrl, $token);
        $this->content .= AdminProfileForm::render(
            $profile,
            $adminUrl,
            $token,
            $canPublish,
            $bankUrl,
            (string) $this->context->link->getBaseLink()
        );
        if ($this->ordenowaPreviewProfile !== null) {
            $this->content .= AdminProfileForm::renderPreview(
                $this->ordenowaPreviewProfile,
                (string) $this->context->link->getBaseLink()
            );
        }
        $this->content .= AdminProfileForm::renderHistory(
            $service->history($shopId),
            $draft?->id ?? 0,
            $published?->id ?? 0,
            $adminUrl,
            $token,
            AdminAccessPolicy::canEdit((array) ($this->tabAccess ?? []))
        );
        $this->context->smarty->assign('content', $this->content);
    }

    private function processProfileActions(
        VersionedProfileRepository $repository,
        ProfileVersionService $service,
        ProfileValidator $validator,
        int $shopId,
        int $employeeId
    ): void {
        if (!AdminAccessPolicy::canView((array) ($this->tabAccess ?? []))) {
            $this->fail('설정을 조회할 권한이 없습니다.');
            return;
        }

        if (Tools::isSubmit('submitOrdenowaPreview')) {
            $previewVersionId = (int) Tools::getValue('preview_version_id', 0);
            if ($previewVersionId > 0) {
                $version = $repository->find($shopId, $previewVersionId);
                if ($version === null) {
                    $this->fail('미리 볼 설정 버전을 찾을 수 없습니다.');
                    return;
                }
                $this->ordenowaPreviewProfile = $version->profile;
                return;
            }

            if (!AdminAccessPolicy::canEdit((array) ($this->tabAccess ?? []))) {
                $this->fail('저장하지 않은 설정 미리보기를 만들 권한이 없습니다.');
                return;
            }

            $draft = $repository->loadDraft($shopId);
            $base = $draft?->profile ?? ProfileDefaults::initial();
            $submitted = Tools::getValue('profile', []);
            if (!is_array($submitted)) {
                $this->fail('미리보기 설정 형식이 올바르지 않습니다.');
                return;
            }
            try {
                $candidate = $this->applyUploadedBrandAssets(AdminProfileForm::apply($base, $submitted));
                $errors = $validator->validateDraft($candidate);
                if ($errors !== []) {
                    $this->fail(implode(' ', $errors));
                    return;
                }
                $this->ordenowaPreviewProfile = $candidate;
            } catch (Throwable $exception) {
                $this->fail($exception instanceof \InvalidArgumentException
                    ? $exception->getMessage()
                    : '브랜드 이미지 미리보기를 만들지 못했습니다.');
            }
            return;
        }

        if (Tools::isSubmit('submitOrdenowaRestore')) {
            if (!AdminAccessPolicy::canEdit((array) ($this->tabAccess ?? []))) {
                $this->fail('이전 설정을 복원할 권한이 없습니다.');
                return;
            }

            $versionId = (int) Tools::getValue('restore_version_id', 0);
            if ($versionId < 1) {
                $this->fail('복원할 설정 버전을 선택해 주세요.');
                return;
            }

            try {
                $service->restoreAsDraft($shopId, $versionId, $employeeId);
                $this->succeed('이전 설정을 새 초안으로 복원했습니다. 고객 화면에는 게시되지 않았습니다.');
            } catch (Throwable $exception) {
                $this->fail($exception instanceof \InvalidArgumentException
                    ? $exception->getMessage()
                    : '설정 버전을 복원하지 못했습니다.');
            }
            return;
        }

        if (Tools::isSubmit('submitOrdenowaSaveDraft')) {
            if (!AdminAccessPolicy::canEdit((array) ($this->tabAccess ?? []))) {
                $this->fail('설정 초안을 수정할 권한이 없습니다.');
                return;
            }

            $draft = $repository->loadDraft($shopId);
            $base = $draft?->profile ?? ProfileDefaults::initial();
            $submitted = Tools::getValue('profile', []);
            if (!is_array($submitted)) {
                $this->fail('제출된 설정 형식이 올바르지 않습니다.');
                return;
            }

            try {
                $profile = $this->applyUploadedBrandAssets(AdminProfileForm::apply($base, $submitted));
            } catch (Throwable $exception) {
                $this->fail($exception instanceof \InvalidArgumentException
                    ? $exception->getMessage()
                    : '브랜드 이미지 업로드를 처리하지 못했습니다.');
                return;
            }
            $errors = $validator->validateDraft($profile);
            if ($errors !== []) {
                $this->fail(implode(' ', $errors));
                return;
            }

            $service->saveDraft($shopId, $profile, $employeeId);
            $this->succeed('초안을 저장했습니다. 아직 고객 화면에는 게시되지 않았습니다.');
            return;
        }

        if (Tools::isSubmit('submitOrdenowaPublish')) {
            if (!AdminAccessPolicy::canPublish((array) ($this->tabAccess ?? []))) {
                $this->fail('변경사항을 게시할 권한이 없습니다.');
                return;
            }

            $draft = $repository->loadDraft($shopId);
            if ($draft === null) {
                $this->fail('게시할 초안이 없습니다.');
                return;
            }

            $submitted = Tools::getValue('profile', []);
            if (!is_array($submitted)
                || AdminProfileForm::hasUnsavedChanges($draft->profile, $submitted)
                || $this->hasPendingBrandUpload()
            ) {
                $this->fail('저장되지 않은 변경사항이 있습니다. 먼저 초안 저장을 누른 뒤 다시 게시해 주세요. 선택한 브랜드 이미지는 초안에 저장된 후 게시할 수 있습니다.');
                return;
            }

            $result = $service->publish($shopId, $draft->id, $employeeId);
            if (!$result['published']) {
                $this->fail(implode(' ', $result['errors']));
                return;
            }

            $compatibilityReady = (bool) \Configuration::updateValue(
                'PS_SHOP_NAME',
                (string) ($draft->profile['brand']['name']['ja-JP'] ?? 'ORDENOWA'),
                false,
                null,
                $shopId
            );
            $emailLogo = $draft->profile['brand']['assets']['email_logo'] ?? '';
            if (is_string($emailLogo)
                && preg_match('~\\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/(?:email-logo|official-email-logo)\\.png\\z~D', $emailLogo) === 1
                && is_file(_PS_ROOT_DIR_ . '/' . $emailLogo)
            ) {
                $compatibilityReady = (bool) \Configuration::updateValue('PS_LOGO_MAIL', substr($emailLogo, 4), false, null, $shopId)
                    && $compatibilityReady;
            }

            $this->succeed($compatibilityReady
                ? '변경사항을 게시했습니다.'
                : '운영정보는 게시했지만 PrestaShop 호환 설정을 모두 동기화하지 못했습니다. 설정을 확인해 주세요.');
            return;
        }

        if (Tools::isSubmit('submitOrdenowaApproveSeller') || Tools::isSubmit('submitOrdenowaRevokeSellerApproval')) {
            $employee = $this->context->employee ?? null;
            $isSuperAdmin = is_object($employee) && method_exists($employee, 'isSuperAdmin') && (bool) $employee->isSuperAdmin();
            if (!AdminAccessPolicy::canApproveSeller($isSuperAdmin)) {
                $this->fail('판매사업 승인 상태는 최고 관리자만 변경할 수 있습니다.');
                return;
            }
            if ((string) Tools::getValue('confirm_seller_authorization', '') !== '1') {
                $this->fail('판매사업 운영 승인 관계를 확인한 뒤 체크해 주세요.');
                return;
            }

            $draft = $repository->loadDraft($shopId);
            $profile = $draft?->profile ?? ProfileDefaults::initial();
            $approved = Tools::isSubmit('submitOrdenowaApproveSeller');
            $profile['seller']['authorization_status'] = $approved ? 'approved' : 'pending';
            $profile['seller']['authorization_decision'] = [
                'status' => $approved ? 'approved' : 'pending',
                'employee_id' => $employeeId,
                'recorded_at' => date(DATE_ATOM),
            ];

            $service->saveDraft($shopId, $profile, $employeeId);
            $this->succeed($approved
                ? '내부 승인 확인을 초안 이력에 기록했습니다. 이 설정만으로는 실거래가 활성화되지 않습니다.'
                : '판매사업 승인 상태를 확인 대기로 되돌렸습니다.');
        }
    }

    private function renderSellerApproval(array $profile, string $actionUrl, string $token): string
    {
        $approved = ($profile['seller']['authorization_status'] ?? 'pending') === 'approved';
        $status = $approved ? '내부 상태 확인됨' : '확인 대기';
        $html = '<section class="panel ordenowa-approval"><h2>판매사업 운영 승인</h2><p>현재 상태: '
            . htmlspecialchars($status, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
            . '</p><p>법인 참고정보만으로 판매사업 승인을 추정하지 않습니다. 내부 상태 변경만으로 실거래가 활성화되지 않으며, 별도 운영 승인 설정과 판매 필수정보 검증이 필요합니다.</p>';
        $employee = $this->context->employee ?? null;
        $isSuperAdmin = is_object($employee) && method_exists($employee, 'isSuperAdmin') && (bool) $employee->isSuperAdmin();
        if ($isSuperAdmin) {
            $action = $approved ? 'submitOrdenowaRevokeSellerApproval' : 'submitOrdenowaApproveSeller';
            $label = $approved ? '승인 상태 되돌리기' : '판매사업 운영 승인 확인';
            $html .= '<form method="post" action="' . htmlspecialchars($actionUrl, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '">'
                . '<input type="hidden" name="token" value="' . htmlspecialchars($token, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '">'
                . '<label><input type="checkbox" name="confirm_seller_authorization" value="1" required> 판매사업자와 운영 승인 관계를 별도로 확인했습니다.</label> '
                . '<button class="btn btn-default" type="submit" name="' . $action . '" value="1">' . $label . '</button></form>';
        }
        $html .= '</section>';

        return $html;
    }

    private function renderFeedback(): string
    {
        if ($this->ordenowaFeedback === '') {
            return '';
        }

        $class = $this->ordenowaFeedbackIsError ? 'alert-danger' : 'alert-success';

        return '<div class="alert ' . $class . '">' . htmlspecialchars($this->ordenowaFeedback, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '</div>';
    }

    private function fail(string $message): void
    {
        $this->ordenowaFeedback = $message;
        $this->ordenowaFeedbackIsError = true;
    }

    private function succeed(string $message): void
    {
        $this->ordenowaFeedback = $message;
        $this->ordenowaFeedbackIsError = false;
    }

    private function shopId(): int
    {
        $shopId = (int) ($this->context->shop->id ?? 0);

        return max(1, $shopId);
    }

    private function hasPendingBrandUpload(): bool
    {
        $upload = $_FILES['brand_uploads'] ?? [];
        if ($upload === []) {
            return false;
        }
        if (!is_array($upload) || !is_array($upload['error'] ?? null)) {
            return true;
        }

        foreach (['primary_logo', 'favicon_symbol', 'pwa_icon'] as $slot) {
            $error = $upload['error'][$slot] ?? UPLOAD_ERR_NO_FILE;
            if (!is_numeric($error) || (int) $error !== UPLOAD_ERR_NO_FILE) {
                return true;
            }
        }

        return false;
    }

    /** @param array<string, mixed> $profile
     *  @return array<string, mixed>
     */
    private function applyUploadedBrandAssets(array $profile): array
    {
        $upload = $_FILES['brand_uploads'] ?? [];
        if ($upload === []) {
            return $profile;
        }
        if (!is_array($upload)) {
            throw new \InvalidArgumentException('브랜드 이미지 업로드 형식이 올바르지 않습니다.');
        }

        foreach (['primary_logo', 'favicon_symbol', 'pwa_icon'] as $slot) {
            $error = (int) ($upload['error'][$slot] ?? UPLOAD_ERR_NO_FILE);
            if ($error === UPLOAD_ERR_NO_FILE) {
                continue;
            }
            if ($error !== UPLOAD_ERR_OK) {
                throw new \InvalidArgumentException('브랜드 원본 업로드에 실패했습니다. 파일 크기와 서버 업로드 한도를 확인해 주세요.');
            }

            $temporaryPath = $upload['tmp_name'][$slot] ?? '';
            if (!is_string($temporaryPath) || $temporaryPath === '' || !is_uploaded_file($temporaryPath)) {
                throw new \InvalidArgumentException('브랜드 원본 업로드 경로를 검증하지 못했습니다.');
            }
            $temporarySize = filesize($temporaryPath);
            if ($temporarySize === false) {
                throw new \InvalidArgumentException('브랜드 원본 파일 크기를 확인하지 못했습니다.');
            }
            if ($temporarySize > BrandAssetProcessor::MAX_BYTES) {
                throw new \InvalidArgumentException('브랜드 원본 이미지는 10MiB 이하로 업로드해 주세요.');
            }
            $bytes = file_get_contents($temporaryPath);
            if (!is_string($bytes)) {
                throw new \InvalidArgumentException('브랜드 원본 파일을 읽지 못했습니다.');
            }

            $result = BrandAssetProcessor::process(
                $slot,
                $bytes,
                _PS_ROOT_DIR_,
                _PS_ROOT_DIR_ . '/var/ordenowa-private'
            );
            $profile['brand']['sources'][$slot] = $result['source'];
            $profile['brand']['assets'] = array_replace($profile['brand']['assets'] ?? [], $result['assets']);
        }

        return $profile;
    }
}
