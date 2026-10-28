<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Notifications;

final class MailTransport implements Transport
{
    private readonly \Closure $sender;
    private readonly \Closure $link;

    public function __construct(private readonly NativeRecipientResolver $recipients, ?callable $sender = null, ?callable $link = null)
    {
        $this->sender = $sender === null ? static function (array $message): bool {
            return (bool) \Mail::Send($message['id_lang'], 'procurement_event', $message['subject'], $message['variables'], $message['email'],
                null, null, null, null, null, dirname(__DIR__, 2) . '/mails/', false, $message['id_shop']);
        } : \Closure::fromCallable($sender);
        $this->link = $link === null ? static fn(int $shop, int $language, string $view): string => (string) \Context::getContext()->link->getModuleLink(
            'ordenowaprocurement', 'workspace', ['view' => $view], true, $language, $shop
        ) : \Closure::fromCallable($link);
    }

    public function send(array $event): DeliveryResult
    {
        $recipient = $this->recipients->resolve($event);
        if ($recipient === null) {
            return new DeliveryResult('skipped', 'recipient_ineligible');
        }
        $locale = $recipient['locale'];
        $subjects = ['ja' => 'ORDENOWA お知らせ', 'en' => 'ORDENOWA notification', 'ko' => 'ORDENOWA 알림'];
        $messages = [
            'assignment.created' => ['ja' => '新しい発注案内があります。', 'en' => 'A new procurement assignment is available.', 'ko' => '새로운 상품 발주 안내가 있습니다.'],
            'assignment.revoked' => ['ja' => '発注案内が取り消されました。', 'en' => 'A procurement assignment was cancelled.', 'ko' => '상품 발주 안내가 회수되었습니다.'],
            'request.submitted' => ['ja' => '発注リクエストを受け付けました。', 'en' => 'Your procurement request was received.', 'ko' => '상품 발주 요청이 접수되었습니다.'],
            'request.reviewed' => ['ja' => '発注リクエストの確認結果があります。', 'en' => 'Your procurement request review is available.', 'ko' => '상품 발주 요청의 검토 결과가 있습니다.'],
            'points.awarded' => ['ja' => '手当ポイントの付与を記録しました。', 'en' => 'An allowance points award was recorded.', 'ko' => '수당 포인트 지급이 기록되었습니다.'],
            'points.corrected' => ['ja' => '手当ポイントの訂正を記録しました。', 'en' => 'An allowance points correction was recorded.', 'ko' => '수당 포인트 정정이 기록되었습니다.'],
        ];
        $view = str_starts_with($event['event'], 'points.') ? 'points' : (str_starts_with($event['event'], 'request.') ? 'requests' : 'assignments');
        $url = ($this->link)((int) $recipient['id_shop'], (int) $recipient['id_lang'], $view);
        if (filter_var($url, FILTER_VALIDATE_URL) === false || !in_array(parse_url($url, PHP_URL_SCHEME), ['http', 'https'], true)) {
            return new DeliveryResult('retry', 'workspace_link_unavailable');
        }
        $sent = ($this->sender)([
            'id_lang' => (int) $recipient['id_lang'], 'id_shop' => (int) $recipient['id_shop'], 'email' => $recipient['email'],
            'subject' => $subjects[$locale], 'variables' => [
                '{event_message}' => $messages[$event['event']][$locale],
                '{workspace_url}' => htmlspecialchars($url, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'), '{workspace_url_text}' => $url,
            ],
        ]);
        return new DeliveryResult($sent ? 'sent' : 'retry', $sent ? '' : 'mail_send_failed');
    }
}
