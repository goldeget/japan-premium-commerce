<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Support;

/** Protect account-owned contact context before the native contactform module runs. */
final class SupportContactAccessGuard
{
    public static function allows(object $context, array $query, array $post, bool $submission): bool
    {
        // Tools::getValue gives POST precedence over GET; do not change either input or CSRF token.
        $input = array_replace($query, $post);
        $shopId = (int) ($context->shop->id ?? 0);
        $customer = $context->customer;
        $customerId = $customer->isLogged() ? (int) $customer->id : 0;
        if ($shopId < 1) {
            return false;
        }
        if (isset($input['id_customer_thread']) && $input['id_customer_thread'] !== '' && $input['id_customer_thread'] !== '0') {
            $threadId = self::positiveId($input['id_customer_thread']);
            if ($threadId === null) {
                return false;
            }
            $thread = new \CustomerThread($threadId);
            if ((int) $thread->id !== $threadId || (int) $thread->id_shop !== $shopId) {
                return false;
            }
            if ((int) $thread->id_customer > 0) {
                if ($customerId < 1 || (int) $thread->id_customer !== $customerId) {
                    return false;
                }
            } elseif (!is_string($input['token'] ?? null) || !hash_equals((string) $thread->token, $input['token'])) {
                return false;
            }
        }
        if (!$submission) {
            return true;
        }
        $from = $input['from'] ?? null;
        if (!is_string($from)) {
            return false;
        }
        $from = trim($from);
        if ($customerId > 0) {
            if (strcasecmp($from, (string) $customer->email) !== 0) {
                return false;
            }
        } elseif (\Customer::customerExists($from, true, true)) {
            // Native getByEmail must not convert an unauthenticated sender into an account owner.
            return false;
        }
        $orderValue = $input['id_order'] ?? '';
        if ($orderValue === '' || $orderValue === '0') {
            return true;
        }
        $orderId = self::positiveId($orderValue);
        if ($customerId < 1 || $orderId === null) {
            return false;
        }
        $order = new \Order($orderId);
        return (int) $order->id === $orderId && (int) $order->id_customer === $customerId && (int) $order->id_shop === $shopId;
    }

    private static function positiveId(mixed $value): ?int
    {
        return is_string($value) && preg_match('/\A[1-9][0-9]{0,9}\z/D', $value) === 1 ? (int) $value : null;
    }
}
