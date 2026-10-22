<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Admin;

use InvalidArgumentException;

final class AdminBankAccountForm
{
    private const ACCOUNT_TYPES = ['ordinary' => '보통', 'current' => '당좌', 'savings' => '저축'];

    /** @return list<array{bank_name: string, branch_name: string, account_type: string, account_number: string, account_holder: string, active: bool}> */
    public static function apply(array $submitted): array
    {
        $rows = $submitted['accounts'] ?? [];
        if (!is_array($rows) || count($rows) > 10) {
            throw new InvalidArgumentException('은행 계좌는 10개 이하로 등록해 주세요.');
        }

        $accounts = [];
        foreach ($rows as $row) {
            if (!is_array($row)) {
                continue;
            }
            $account = [
                'bank_name' => self::text($row['bank_name'] ?? '', 120),
                'branch_name' => self::text($row['branch_name'] ?? '', 120),
                'account_type' => is_scalar($row['account_type'] ?? null) ? (string) $row['account_type'] : '',
                'account_number' => preg_replace('/[^0-9]/', '', (string) ($row['account_number'] ?? '')) ?? '',
                'account_holder' => self::text($row['account_holder'] ?? '', 120),
                'active' => in_array($row['active'] ?? false, [1, '1', true, 'on'], true),
            ];

            if (implode('', [$account['bank_name'], $account['branch_name'], $account['account_number'], $account['account_holder']]) === '') {
                continue;
            }
            if ($account['bank_name'] === '' || $account['branch_name'] === '' || $account['account_holder'] === '') {
                throw new InvalidArgumentException('은행명·지점명·예금주를 모두 입력해 주세요.');
            }
            if (!array_key_exists($account['account_type'], self::ACCOUNT_TYPES)) {
                throw new InvalidArgumentException('계좌 종류를 선택해 주세요.');
            }
            if (preg_match('/\A[0-9]{4,12}\z/D', $account['account_number']) !== 1) {
                throw new InvalidArgumentException('계좌번호는 숫자 4~12자리로 입력해 주세요.');
            }

            $accounts[] = $account;
        }

        return $accounts;
    }

    /** @param list<array<string, mixed>> $accounts */
    public static function render(array $accounts, string $actionUrl, string $token): string
    {
        if ($accounts === []) {
            $accounts = [[
                'bank_name' => '',
                'branch_name' => '',
                'account_type' => 'ordinary',
                'account_number' => '',
                'account_holder' => '',
                'active' => false,
            ]];
        }

        $html = '<form method="post" action="' . self::escape($actionUrl) . '" class="ordenowa-bank-settings">';
        $html .= '<input type="hidden" name="token" value="' . self::escape($token) . '">';
        $html .= '<div class="alert alert-warning">은행 계좌는 활성 게시 시 결제 안내에 표시될 수 있습니다. 실제 계좌만 입력하고 게시 전에 다시 확인해 주세요.</div>';
        foreach (array_slice($accounts, 0, 10) as $index => $account) {
            $html .= '<fieldset class="panel"><legend>계좌 ' . ($index + 1) . '</legend>';
            $html .= self::input($index, 'bank_name', '은행명', $account['bank_name'] ?? '');
            $html .= self::input($index, 'branch_name', '지점명', $account['branch_name'] ?? '');
            $html .= '<div class="form-group"><label for="bank-type-' . $index . '">계좌 종류</label><select class="form-control" id="bank-type-' . $index
                . '" name="bank_accounts[accounts][' . $index . '][account_type]">';
            foreach (self::ACCOUNT_TYPES as $value => $label) {
                $selected = (string) ($account['account_type'] ?? '') === $value ? ' selected' : '';
                $html .= '<option value="' . $value . '"' . $selected . '>' . $label . '</option>';
            }
            $html .= '</select></div>';
            $html .= self::input($index, 'account_number', '계좌번호', $account['account_number'] ?? '', 'text', 'numeric');
            $html .= self::input($index, 'account_holder', '예금주', $account['account_holder'] ?? '');
            $checked = !empty($account['active']) ? ' checked' : '';
            $html .= '<div class="checkbox"><label><input type="checkbox" name="bank_accounts[accounts][' . $index . '][active]" value="1"' . $checked . '> 결제 안내에 사용할 계좌</label></div>';
            $html .= '</fieldset>';
        }

        $html .= '<button class="btn btn-primary" type="submit" name="submitOrdenowaSaveBanks" value="1">계좌 초안 저장</button></form>';

        return $html;
    }

    /** @param list<\Kuranea\BusinessProfile\Domain\ProfileVersion> $versions */
    public static function renderHistory(
        array $versions,
        int $draftVersionId,
        string $actionUrl,
        string $token,
        bool $canRestore
    ): string {
        $html = '<section class="panel ordenowa-bank-history"><h2>은행 계좌 변경 이력</h2>';
        if ($versions === []) {
            return $html . '<p>저장된 계좌 이력이 없습니다.</p></section>';
        }

        $html .= '<div class="table-responsive"><table class="table"><thead><tr><th>버전</th><th>변경자 ID</th><th>변경일시</th><th>등록 계좌</th><th>작업</th></tr></thead><tbody>';
        foreach ($versions as $version) {
            $accounts = $version->profile['bank_accounts'] ?? [];
            if (!is_array($accounts)) {
                $accounts = [];
            }
            $details = [];
            foreach (array_slice($accounts, 0, 10) as $account) {
                if (!is_array($account)) {
                    continue;
                }
                $masked = BankAccountPresenter::mask($account);
                $details[] = self::escape((string) ($masked['bank_name'] ?? ''))
                    . ' · ' . self::escape((string) ($masked['branch_name'] ?? ''))
                    . ' · ' . self::escape((string) ($masked['account_number'] ?? ''))
                    . ' · ' . self::escape((string) ($masked['account_holder'] ?? ''));
            }
            $html .= '<tr><td>#' . $version->id . ($version->id === $draftVersionId ? ' · 현재 초안' : '')
                . '</td><td>' . $version->employeeId . '</td><td>' . self::escape($version->createdAt) . '</td><td>'
                . ($details === [] ? '등록 계좌 없음' : implode('<br>', $details)) . '</td><td>';
            if ($canRestore && $version->id !== $draftVersionId) {
                $html .= '<form method="post" action="' . self::escape($actionUrl) . '" class="ordenowa-history-action">'
                    . '<input type="hidden" name="token" value="' . self::escape($token) . '">'
                    . '<input type="hidden" name="restore_version_id" value="' . $version->id . '">'
                    . '<button class="btn btn-default btn-sm" type="submit" name="submitOrdenowaRestoreBanks" value="1">이 계좌 설정 복원</button></form>';
            }
            $html .= '</td></tr>';
        }

        return $html . '</tbody></table></div><p>계좌번호와 예금주는 보안을 위해 일부를 가린 상태로 표시합니다.</p></section>';
    }

    private static function input(int $index, string $key, string $label, mixed $value, string $type = 'text', string $inputMode = ''): string
    {
        $id = 'ordenowa-bank-' . $index . '-' . $key;
        $mode = $inputMode === '' ? '' : ' inputmode="' . self::escape($inputMode) . '"';

        return '<div class="form-group"><label for="' . $id . '">' . self::escape($label) . '</label><input class="form-control" type="'
            . self::escape($type) . '" id="' . $id . '" name="bank_accounts[accounts][' . $index . '][' . self::escape($key) . ']" value="'
            . self::escape((string) $value) . '"' . $mode . '></div>';
    }

    private static function text(mixed $value, int $maxLength): string
    {
        if (!is_scalar($value)) {
            return '';
        }

        return mb_substr(trim((string) $value), 0, $maxLength);
    }

    private static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
