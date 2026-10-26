<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\BusinessProfile\Admin\AdminAccessPolicy;
use Kuranea\BusinessProfile\Customer\CommerceGate;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionIssuer;
use Kuranea\BusinessProfile\Domain\BankTransferPayment;
use Kuranea\BusinessProfile\Domain\JpyAmount;
use Kuranea\BusinessProfile\Infrastructure\BankTransferInstructionRepository;
use Kuranea\BusinessProfile\Infrastructure\BankTransferReceiptConfirmer;
use Kuranea\BusinessProfile\Infrastructure\BankTransferReceiptRepository;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

class AdminBusinessProfileTransfersController extends ModuleAdminController
{
    private string $ordenowaFeedback = '';
    private bool $ordenowaFeedbackIsError = false;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '주문 입금 안내';
    }

    public function initHeader()
    {
        $koreanLanguageId = (int) Language::getIdByIso('ko', true);
        if ($koreanLanguageId > 0) {
            $this->context->language = new Language($koreanLanguageId);
        }

        parent::initHeader();
    }

    public function initContent(): void
    {
        $this->viewAccess();

        $tabAccess = (array) ($this->tabAccess ?? []);
        $canIssue = AdminAccessPolicy::canIssueBankTransferInstructions($tabAccess);
        $canConfirm = AdminAccessPolicy::canConfirmBankTransferReceipt($tabAccess);
        if (!AdminAccessPolicy::canView($tabAccess)) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">주문 입금 정보를 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        $shopId = (int) ($this->context->shop->id ?? 0);
        if ($shopId < 1) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">단일 쇼핑몰을 선택한 후 이용해 주세요.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        $instructions = new BankTransferInstructionRepository();
        $receipts = new BankTransferReceiptRepository();
        $this->processIssue($shopId, $instructions);
        $this->processConfirm($shopId, $instructions, $receipts);
        $orders = $this->unpaidJpyOrders($shopId);

        parent::initContent();
        $actionUrl = (string) $this->context->link->getAdminLink('AdminBusinessProfileTransfers');
        $token = (string) Tools::getAdminTokenLite('AdminBusinessProfileTransfers');
        $this->content .= $this->renderFeedback();
        $this->content .= '<h2>미결제 엔화 주문</h2>'
            . '<p>주문 금액과 게시된 계좌를 확인한 뒤 안내를 한 번 발급합니다. 금액이나 계좌를 이 화면에서 바꿀 수 없으며, 발급만으로 결제완료 처리되지 않습니다.</p>'
            . '<p>입금 확인은 은행 거래내역에서 주문별 전액을 대조하고 확인 항목에 동의한 담당자만 처리할 수 있습니다. 확인하면 PrestaShop의 결제 내역과 주문 상태가 갱신됩니다.</p>'
            . (CommerceGate::isIsolatedCiCheckoutEnabled()
                ? '<p class="alert alert-info">격리 CI 모드: 입금 확인은 합성 QA 자료만 사용합니다.</p>'
                : '')
            . $this->renderOrders($orders, $instructions, $receipts, $actionUrl, $token, $canIssue, $canConfirm);
        $this->context->smarty->assign('content', $this->content);
    }

    private function processIssue(int $shopId, BankTransferInstructionRepository $repository): void
    {
        if (!Tools::isSubmit('submitOrdenowaIssueTransfer')) {
            return;
        }

        $submittedToken = isset($_POST['token']) && is_string($_POST['token']) ? $_POST['token'] : '';
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST'
            || !hash_equals((string) Tools::getAdminTokenLite('AdminBusinessProfileTransfers'), $submittedToken)) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.');
            return;
        }
        if (!AdminAccessPolicy::canIssueBankTransferInstructions((array) ($this->tabAccess ?? []))) {
            $this->fail('주문 입금 안내를 발급할 권한이 없습니다.');
            return;
        }

        $orderId = (int) Tools::getValue('id_order', 0);
        $order = $orderId > 0 ? new Order($orderId) : false;
        if (!Validate::isLoadedObject($order)
            || (int) $order->id_shop !== $shopId
            || (int) $order->id_customer < 1
        ) {
            $this->fail('선택한 쇼핑몰의 주문을 찾을 수 없습니다.');
            return;
        }
        if ((string) $order->module !== 'ps_checkpayment') {
            $this->fail('입금 안내는 미결제 계좌이체 주문에만 발급할 수 있습니다.');
            return;
        }

        $currency = new Currency((int) $order->id_currency);
        $orderState = new OrderState((int) $order->current_state);
        if (!Validate::isLoadedObject($currency)
            || strtoupper((string) $currency->iso_code) !== 'JPY'
            || !Validate::isLoadedObject($orderState)
            || (bool) $orderState->paid
            || (int) $order->current_state === (int) Configuration::get('PS_OS_CANCELED')
            || !$this->isZeroAmount((string) $order->total_paid_real)
            || !$this->isPositiveAmount((string) $order->total_paid_tax_incl)
        ) {
            $this->fail('미결제 상태의 유효한 엔화 주문만 안내할 수 있습니다.');
            return;
        }

        $profileRepository = new VersionedProfileRepository();
        $published = $profileRepository->loadPublished($shopId);
        if ($published === null
            || (!CommerceGate::isIsolatedCiCheckoutEnabled()
                && !CommerceGate::isEnabled(
                    $published->profile,
                    getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'
                ))
            || BankTransferPayment::selectedActiveAccount($published->profile) === null
        ) {
            $this->fail('판매자 승인과 게시된 계좌 안내를 먼저 확인해 주세요.');
            return;
        }

        $employeeId = (int) ($this->context->employee->id ?? 0);
        if ($employeeId < 1) {
            $this->fail('관리자 계정을 확인할 수 없습니다.');
            return;
        }

        try {
            $result = (new BankTransferInstructionIssuer($repository))->issue(
                $shopId,
                (int) $order->id,
                (string) $order->reference,
                (string) $order->total_paid_tax_incl,
                strtoupper((string) $currency->iso_code),
                $published,
                $employeeId,
                gmdate('Y-m-d H:i:s')
            );
            $this->ordenowaFeedback = $result->created
                ? '선택한 주문에 입금 안내를 발급했습니다. 고객 주문 상세에 같은 안내가 표시됩니다. 주문은 미결제 상태입니다.'
                : '이미 발급된 주문 안내를 유지했습니다. 기존 계좌와 금액은 변경하지 않았습니다.';
        } catch (Throwable $exception) {
            $this->fail($exception instanceof \InvalidArgumentException || $exception instanceof \RuntimeException
                ? $exception->getMessage()
                : '주문 입금 안내를 발급하지 못했습니다.');
        }
    }

    private function processConfirm(
        int $shopId,
        BankTransferInstructionRepository $instructionRepository,
        BankTransferReceiptRepository $receiptRepository
    ): void {
        if (!Tools::isSubmit('submitOrdenowaConfirmBankTransfer')) {
            return;
        }

        $submittedToken = isset($_POST['token']) && is_string($_POST['token']) ? $_POST['token'] : '';
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST'
            || !hash_equals((string) Tools::getAdminTokenLite('AdminBusinessProfileTransfers'), $submittedToken)) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.');
            return;
        }
        if (!AdminAccessPolicy::canConfirmBankTransferReceipt((array) ($this->tabAccess ?? []))) {
            $this->fail('주문 입금 확인 권한이 없습니다.');
            return;
        }

        $employeeId = (int) ($this->context->employee->id ?? 0);
        $amount = isset($_POST['received_amount']) && is_string($_POST['received_amount'])
            ? trim($_POST['received_amount'])
            : '';
        $statementReference = isset($_POST['bank_statement_reference']) && is_string($_POST['bank_statement_reference'])
            ? $_POST['bank_statement_reference']
            : '';
        $verifiedTransfer = isset($_POST['verified_transfer'])
            && is_string($_POST['verified_transfer'])
            && $_POST['verified_transfer'] === '1';
        if ($employeeId < 1 || !$verifiedTransfer) {
            $this->fail('은행 거래내역과 주문 금액을 직접 대조하고 입금 사실을 확인해야 합니다.');
            return;
        }

        $postedOrderId = isset($_POST['id_order']) && is_string($_POST['id_order']) ? $_POST['id_order'] : '';
        $orderId = preg_match('/\\A[1-9][0-9]{0,9}\\z/D', $postedOrderId) === 1 ? (int) $postedOrderId : 0;

        try {
            $profile = (new VersionedProfileRepository())->loadPublished($shopId);
            $isolatedCi = CommerceGate::isIsolatedCiCheckoutEnabled();
            $commerceEnabled = $isolatedCi || ($profile !== null && CommerceGate::isEnabled(
                $profile->profile,
                getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'
            ));
            $result = (new BankTransferReceiptConfirmer($instructionRepository, $receiptRepository))->confirm(
                $shopId,
                $orderId,
                $amount,
                $statementReference,
                $verifiedTransfer,
                $employeeId,
                gmdate('Y-m-d H:i:s'),
                $commerceEnabled
            );
            if ($result->receipt->synthetic) {
                $this->ordenowaFeedback = $result->created
                    ? '격리 QA용 합성 입금 확인을 기록하고 합성 주문 상태를 갱신했습니다.'
                    : '격리 QA용 동일 입금 확인 기록을 유지했습니다. 추가 결제 내역은 만들지 않았습니다.';
            } else {
                $this->ordenowaFeedback = $result->created
                    ? '담당자가 확인한 입금을 기록하고 주문 결제 상태를 갱신했습니다.'
                    : '이미 확인된 동일 입금 기록을 유지했습니다. 추가 결제 내역은 만들지 않았습니다.';
            }
        } catch (Throwable $exception) {
            $this->fail($exception instanceof \InvalidArgumentException || $exception instanceof \RuntimeException
                ? $exception->getMessage()
                : '주문 입금을 확인하지 못했습니다. 주문 상태와 결제 기록을 다시 확인해 주세요.');
        }
    }

    /** @return list<array{id_order: int, reference: string, total_paid_tax_incl: string, currency_iso: string}> */
    private function unpaidJpyOrders(int $shopId): array
    {
        $rows = Db::getInstance()->executeS(
            'SELECT o.`id_order`, o.`reference`, o.`total_paid_tax_incl`, c.`iso_code` AS `currency_iso`'
            . ' FROM `' . _DB_PREFIX_ . 'orders` o'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'order_state` os ON os.`id_order_state` = o.`current_state`'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'currency` c ON c.`id_currency` = o.`id_currency`'
            . ' WHERE o.`id_shop` = ' . (int) $shopId
            . ' AND o.`module` = \'ps_checkpayment\''
            . ' AND os.`paid` = 0 AND o.`total_paid_real` <= 0 AND c.`iso_code` = \'JPY\''
            . ' AND o.`current_state` != ' . (int) Configuration::get('PS_OS_CANCELED')
            . ' ORDER BY o.`id_order` DESC LIMIT 50'
        );

        if (!is_array($rows)) {
            return [];
        }

        return array_values(array_filter($rows, static function (array $row): bool {
            return (int) ($row['id_order'] ?? 0) > 0
                && (string) ($row['currency_iso'] ?? '') === 'JPY';
        }));
    }

    /** @param list<array<string, mixed>> $orders */
    private function renderOrders(
        array $orders,
        BankTransferInstructionRepository $repository,
        BankTransferReceiptRepository $receiptRepository,
        string $actionUrl,
        string $token,
        bool $canIssue,
        bool $canConfirm
    ): string {
        if ($orders === []) {
            return '<p>발급할 수 있는 미결제 엔화 주문이 없습니다.</p>';
        }

        $html = '<table class="table"><thead><tr><th>주문번호</th><th>주문 ID</th><th>금액</th><th>안내 상태</th><th>작업</th></tr></thead><tbody>';
        foreach ($orders as $row) {
            $orderId = (int) $row['id_order'];
            $instruction = $repository->findForOrder((int) ($this->context->shop->id ?? 0), $orderId);
            $instructionMatchesOrder = $instruction !== null
                && $instruction->orderReference === (string) $row['reference']
                && $instruction->totalPaid === (string) $row['total_paid_tax_incl']
                && $instruction->currencyIso === (string) $row['currency_iso'];
            $receipt = $instructionMatchesOrder
                ? $receiptRepository->findForOrder((int) ($this->context->shop->id ?? 0), $orderId)
                : null;
            $html .= '<tr><td>' . $this->escape((string) $row['reference']) . '</td>'
                . '<td>' . $orderId . '</td>'
                . '<td>' . $this->escape((string) $row['total_paid_tax_incl']) . ' JPY</td>'
                . '<td>' . ($instruction === null
                    ? '미발급'
                    : ($instructionMatchesOrder
                        ? ($receipt === null ? '입금 안내 발급' : '입금 확인 완료')
                        : '주문 변경으로 안내 숨김')) . '</td><td>';
            if ($instruction === null && $canIssue) {
                $html .= '<form method="post" action="' . $this->escape($actionUrl) . '">'
                    . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                    . '<input type="hidden" name="id_order" value="' . $orderId . '">'
                    . '<button class="btn btn-primary" type="submit" name="submitOrdenowaIssueTransfer" value="1">입금 안내 발급</button>'
                    . '</form>';
            } elseif ($instruction !== null && $instructionMatchesOrder && $receipt !== null) {
                $html .= '<span>확인자 ' . (int) $receipt->confirmedByEmployeeId
                    . ' · ' . $this->escape($receipt->confirmedAtUtc) . ' UTC'
                    . ($receipt->synthetic ? ' · 격리 CI 합성' : '') . '</span>';
            } elseif ($instruction !== null && $instructionMatchesOrder && $canConfirm) {
                $html .= '<form method="post" action="' . $this->escape($actionUrl) . '">'
                    . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                    . '<input type="hidden" name="id_order" value="' . $orderId . '">'
                    . '<label>실제 입금액 <input type="text" name="received_amount" inputmode="numeric" pattern="[0-9]+" required></label>'
                    . '<small>주문 금액 ' . $this->escape((string) $row['total_paid_tax_incl']) . ' JPY와 정확히 일치해야 합니다.</small>'
                    . '<label>은행 거래내역 참고번호 <input type="text" name="bank_statement_reference" maxlength="256" required></label>'
                    . '<label><input type="checkbox" name="verified_transfer" value="1" required> 은행 거래내역에서 이 주문의 전액 입금을 직접 확인했습니다.</label>'
                    . '<button class="btn btn-primary" type="submit" name="submitOrdenowaConfirmBankTransfer" value="1">입금 확인 및 주문 상태 갱신</button>'
                    . '</form>';
            } elseif ($instruction !== null && $instructionMatchesOrder) {
                $html .= '<span>입금 안내 발급자 ' . (int) $instruction->issuedByEmployeeId
                    . ' · ' . $this->escape($instruction->issuedAtUtc) . ' UTC</span>';
            } else {
                $html .= '<span>주문 금액 또는 번호가 바뀌어 안내를 숨겼습니다. 입금 확인 전 주문을 검토해 주세요.</span>';
            }
            $html .= '</td></tr>';
        }

        return $html . '</tbody></table>';
    }

    private function isPositiveAmount(string $amount): bool
    {
        return JpyAmount::normalizePositive($amount) !== null;
    }

    private function isZeroAmount(string $amount): bool
    {
        return preg_match('/\\A0(?:\\.0{1,6})?\\z/D', $amount) === 1;
    }

    private function fail(string $message): void
    {
        $this->ordenowaFeedback = $message;
        $this->ordenowaFeedbackIsError = true;
    }

    private function renderFeedback(): string
    {
        if ($this->ordenowaFeedback === '') {
            return '';
        }
        $class = $this->ordenowaFeedbackIsError ? 'alert-danger' : 'alert-success';

        return '<div class="alert ' . $class . '">' . $this->escape($this->ordenowaFeedback) . '</div>';
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
