<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\{DeliveryPayload, PushDeliveryProvider, PushDeliveryResult, SubscriptionValidator};
use Minishlink\WebPush\{Subscription, WebPush};

/** RFC Web Push encryption and VAPID signing are delegated to the maintained library. */
final class WebPushDeliveryProvider implements PushDeliveryProvider
{
    private ?object $client = null;
    private bool $initialized = false;
    private mixed $httpHandler;

    /** The optional Guzzle handler allows offline HTTP contract tests without real endpoints. */
    public function __construct(private array $vapid = [], ?callable $httpHandler = null)
    {
        $this->httpHandler = $httpHandler;
    }

    public function available(): bool
    {
        if ($this->initialized) return $this->client !== null;
        $this->initialized = true;
        $autoload = dirname(__DIR__, 2) . '/vendor/autoload.php';
        if (is_file($autoload)) require_once $autoload;
        if (!class_exists(WebPush::class)) return false;
        foreach (['subject', 'publicKey', 'privateKey'] as $field) {
            if (!is_string($this->vapid[$field] ?? null) || trim($this->vapid[$field]) === '' || strlen($this->vapid[$field]) > 2048) return false;
        }
        $subject = $this->vapid['subject'];
        $subjectValid = str_starts_with($subject, 'mailto:')
            ? filter_var(substr($subject, 7), FILTER_VALIDATE_EMAIL) !== false
            : filter_var($subject, FILTER_VALIDATE_URL) !== false && parse_url($subject, PHP_URL_SCHEME) === 'https'
                && !isset(parse_url($subject)['user']) && !isset(parse_url($subject)['pass']);
        if (!$subjectValid) return false;
        $options = ['verify' => true, 'allow_redirects' => false, 'http_errors' => false,
            'timeout' => 10.0, 'connect_timeout' => 3.0];
        if ($this->httpHandler !== null) $options['handler'] = $this->httpHandler;
        try {
            $this->client = new WebPush(['VAPID' => $this->vapid], ['TTL' => 300, 'urgency' => 'normal'], 10, $options);
        } catch (\Throwable) {
            $this->client = null;
        }
        return $this->client !== null;
    }

    public function send(array $subscription, DeliveryPayload $payload): PushDeliveryResult
    {
        $subscription = SubscriptionValidator::validate($subscription);
        if (!$this->available()) return new PushDeliveryResult(PushDeliveryResult::RETRYABLE_FAILURE);
        try {
            $report = $this->client->sendOneNotification(Subscription::create($subscription + ['contentEncoding' => 'aes128gcm']), $payload->toJson());
            $status = $report->getResponse()?->getStatusCode();
            if (in_array($status, [404, 410], true)) return new PushDeliveryResult(PushDeliveryResult::GONE);
            if ($report->isSuccess() && $status !== null && $status >= 200 && $status < 300) {
                return new PushDeliveryResult(PushDeliveryResult::DELIVERED);
            }
        } catch (\Throwable) {
            // Endpoint, key material, response bodies and exception details never enter application logs.
        }
        return new PushDeliveryResult(PushDeliveryResult::RETRYABLE_FAILURE);
    }
}
