<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\BusinessProfile\Admin\AdminAccessPolicy;
use Kuranea\BusinessProfile\Admin\AdminBankAccountForm;
use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Domain\ProfileVersionService;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

class AdminBusinessProfileBanksController extends ModuleAdminController
{
    private string $ordenowaFeedback = '';
    private bool $ordenowaFeedbackIsError = false;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '은행 계좌';
    }

    public function initHeader()
    {
        $koreanLanguageId = (int) Language::getIdByIso('ko', true);
        if ($koreanLanguageId > 0) {
            // PrestaShop 9's legacy Back Office header reads its document
            // language from Context::language while the header is initialized.
            $this->context->language = new Language($koreanLanguageId);
        }

        parent::initHeader();
    }

    public function initContent(): void
    {
        $this->viewAccess();
        $this->access('edit');

        $bankAccess = (array) ($this->tabAccess ?? []);
        if (!AdminAccessPolicy::canViewBank($bankAccess)) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">은행 계좌를 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        parent::initContent();

        $repository = new VersionedProfileRepository();
        $shopId = max(1, (int) ($this->context->shop->id ?? 0));
        $employeeId = (int) ($this->context->employee->id ?? 0);
        $draft = $repository->loadDraft($shopId);
        $profile = $draft?->profile ?? ProfileDefaults::initial();
        $service = new ProfileVersionService($repository, new \Kuranea\BusinessProfile\Domain\ProfileValidator());

        if (Tools::isSubmit('submitOrdenowaRestoreBanks')) {
            if (!AdminAccessPolicy::canEditBank((array) ($this->tabAccess ?? []))) {
                $this->ordenowaFeedback = '은행 계좌를 복원할 권한이 없습니다.';
                $this->ordenowaFeedbackIsError = true;
            } else {
                $versionId = (int) Tools::getValue('restore_version_id', 0);
                try {
                    if ($versionId < 1) {
                        throw new \InvalidArgumentException('복원할 계좌 버전을 선택해 주세요.');
                    }
                    $service->restoreBankAccountsAsDraft($shopId, $versionId, $employeeId);
                    $this->ordenowaFeedback = '선택한 은행 계좌를 새 초안으로 복원했습니다. 다른 운영 설정은 유지됩니다.';
                } catch (Throwable $exception) {
                    $this->ordenowaFeedback = $exception instanceof \InvalidArgumentException
                        ? $exception->getMessage()
                        : '은행 계좌 버전을 복원하지 못했습니다.';
                    $this->ordenowaFeedbackIsError = true;
                }
            }
            $draft = $repository->loadDraft($shopId);
            $profile = $draft?->profile ?? $profile;
        }

        if (Tools::isSubmit('submitOrdenowaSaveBanks')) {
            if (!AdminAccessPolicy::canEditBank((array) ($this->tabAccess ?? []))) {
                $this->ordenowaFeedback = '은행 계좌를 수정할 권한이 없습니다.';
                $this->ordenowaFeedbackIsError = true;
            } else {
                $submitted = Tools::getValue('bank_accounts', []);
                if (!is_array($submitted)) {
                    $this->ordenowaFeedback = '제출된 계좌 정보 형식이 올바르지 않습니다.';
                    $this->ordenowaFeedbackIsError = true;
                } else {
                    try {
                        $profile['bank_accounts'] = AdminBankAccountForm::apply($submitted);
                        $paymentMethods = $profile['payment_methods'] ?? [];
                        if (!is_array($paymentMethods)) {
                            $paymentMethods = [];
                        }
                        $paymentMethods['bank_transfer'] = AdminBankAccountForm::applyPaymentMethod(
                            is_array($submitted['payment_method'] ?? null) ? $submitted['payment_method'] : [],
                            $profile['bank_accounts']
                        );
                        $profile['payment_methods'] = $paymentMethods;
                        $service->saveDraft($shopId, $profile, $employeeId);
                        $this->ordenowaFeedback = '은행 계좌 초안을 저장했습니다. 고객에게 표시하려면 운영정보 게시 검증을 통과해야 합니다.';
                    } catch (Throwable $exception) {
                        $this->ordenowaFeedback = $exception instanceof \InvalidArgumentException
                            ? $exception->getMessage()
                            : '계좌 초안을 저장하지 못했습니다.';
                        $this->ordenowaFeedbackIsError = true;
                    }
                }
            }
            $draft = $repository->loadDraft($shopId);
            $profile = $draft?->profile ?? $profile;
        }

        $actionUrl = (string) $this->context->link->getAdminLink('AdminBusinessProfileBanks');
        $token = (string) Tools::getAdminTokenLite('AdminBusinessProfileBanks');
        $paymentMethod = $profile['payment_methods']['bank_transfer'] ?? [];
        if (!is_array($paymentMethod)) {
            $paymentMethod = [];
        }
        $this->content .= $this->renderFeedback();
        $this->content .= '<p><a href="' . htmlspecialchars((string) $this->context->link->getAdminLink('AdminBusinessProfile'), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '">쇼핑몰 운영 설정으로 돌아가기</a></p>';
        $this->content .= AdminBankAccountForm::render($profile['bank_accounts'] ?? [], $actionUrl, $token, $paymentMethod);
        $this->content .= AdminBankAccountForm::renderHistory(
            $service->history($shopId),
            $draft?->id ?? 0,
            $actionUrl,
            $token,
            AdminAccessPolicy::canEditBank((array) ($this->tabAccess ?? []))
        );
        $this->context->smarty->assign('content', $this->content);
    }

    private function renderFeedback(): string
    {
        if ($this->ordenowaFeedback === '') {
            return '';
        }
        $class = $this->ordenowaFeedbackIsError ? 'alert-danger' : 'alert-success';

        return '<div class="alert ' . $class . '">' . htmlspecialchars($this->ordenowaFeedback, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '</div>';
    }
}
