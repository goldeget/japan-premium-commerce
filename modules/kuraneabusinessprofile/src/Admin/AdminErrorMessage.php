<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Admin;

use Throwable;

final class AdminErrorMessage
{
    /** @var list<string> */
    private const SAFE_TRANSFER_RUNTIME_MESSAGES = [
        '은행 거래내역에서 입금 사실을 확인한 뒤 처리해 주세요.',
        '주문 입금 확인 권한 또는 대상이 올바르지 않습니다.',
        '입금액은 0보다 큰 엔화 정수여야 합니다.',
        '선택한 쇼핑몰의 주문을 찾을 수 없습니다.',
        '같은 쇼핑몰의 유효한 엔화 주문만 확인할 수 있습니다.',
        '먼저 이 주문의 입금 안내를 발급해야 합니다.',
        '실제 입금액이 주문 금액과 다릅니다. 부분 입금이나 초과 입금은 확인할 수 없습니다.',
        '이 은행 거래 참고번호는 다른 주문에 이미 연결되어 있습니다. 기존 입금 기록을 확인해 주세요.',
        '이미 확인된 주문 입금 내역과 일치하지 않습니다. 기존 기록은 변경하지 않았습니다.',
        '판매자 승인과 주문 운영 설정을 확인한 후 처리해 주세요.',
        '이미 결제 내역이 있는 주문입니다. 기존 내역을 먼저 확인해 주세요.',
        '입금 확인 이전에 내부 결제 기록이 발견되었습니다. 수동 검토가 필요합니다.',
        '이미 발급된 입금 안내와 현재 주문 정보가 다릅니다.',
        '입금 확인 기록이 동시에 변경되었습니다. 주문을 다시 조회해 주세요.',
        '입금 안내와 현재 주문 정보가 일치하지 않습니다.',
        '미결제 상태이며 입금 내역이 없는 주문만 확인할 수 있습니다.',
        '은행 거래내역 참고번호를 확인해 주세요.',
    ];

    public static function fromException(Throwable $exception, string $fallback): string
    {
        $message = trim($exception->getMessage());
        if ($message === '') {
            return $fallback;
        }

        if ($exception instanceof \InvalidArgumentException
            && preg_match('/[가-힣]/u', $message) === 1) {
            return $message;
        }

        // Keep only explicitly reviewed, static transfer-domain guidance from
        // RuntimeException. Unlisted runtime failures can contain SQL, paths,
        // tokens, or customer data even if they also contain Korean text.
        return $exception instanceof \RuntimeException
            && in_array($message, self::SAFE_TRANSFER_RUNTIME_MESSAGES, true)
                ? $message
                : $fallback;
    }
}
