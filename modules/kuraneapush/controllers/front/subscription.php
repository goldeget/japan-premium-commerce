<?php

declare(strict_types=1);
require_once dirname(__FILE__, 3) . '/autoload.php';
use Kuranea\Push\Domain\Readiness;
use Kuranea\Push\Domain\SubscriptionApi;
use Kuranea\Push\Infrastructure\PushSettings;
use Kuranea\Push\Infrastructure\SubscriptionCipher;
use Kuranea\Push\Infrastructure\SubscriptionRepository;

class KuraneapushSubscriptionModuleFrontController extends ModuleFrontController
{
    public $auth = false;
    public $ssl = true;

    public function initContent(): void
    {
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: private, no-store, max-age=0', true);
        header('Pragma: no-cache', true);
        header('Expires: 0', true);
        header('X-Content-Type-Options: nosniff', true);
        try {
            $method = (string) ($_SERVER['REQUEST_METHOD'] ?? '');
            $body = [];
            if ($method === 'POST') {
                $type = strtolower(trim(explode(';', (string) ($_SERVER['CONTENT_TYPE'] ?? ''))[0]));
                $raw = file_get_contents('php://input', false, null, 0, 8193);
                if ($type !== 'application/json' || $raw === false || strlen($raw) > 8192) {
                    $this->respond(400, ['error' => 'invalid_request']);
                }
                $body = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
                if (!is_array($body) || array_is_list($body)) {
                    $this->respond(400, ['error' => 'invalid_request']);
                }
            }
            $action = $body['action'] ?? ($_GET['action'] ?? '');
            if (!is_string($action)) {
                $this->respond(400, ['error' => 'invalid_request']);
            }
            $customer = $this->context->customer;
            $authenticated = (bool) $this->module->active && $customer && $customer->isLogged()
                && !(bool) $customer->is_guest;
            $shop = (int) ($this->context->shop->id ?? 0);
            $customerId = (int) ($customer->id ?? 0);
            $cipher = null;
            try {
                $cipher = new SubscriptionCipher();
            } catch (\Throwable $e) {
                // A missing or invalid key disables subscription, never owner revocation.
            }
            $trustedLocale = (string) ($this->context->language->iso_code ?? 'ja');
            $trustedLocale = in_array($trustedLocale, PushSettings::LOCALES, true) ? $trustedLocale : 'ja';
            $notice = trim(PushSettings::notice($shop, $trustedLocale));
            $api = new SubscriptionApi(new SubscriptionRepository(), $cipher);
            [$status, $result] = $api->handle($method, $action, $body, $authenticated, $shop, $customerId,
                (string) ($_SERVER['HTTP_ORIGIN'] ?? ''),
                (string) $this->context->link->getBaseLink($shop),
                (string) Tools::getToken('kuraneapush', $this->context),
                Readiness::canSubscribe(null, $notice, $cipher !== null), $notice, $trustedLocale);
            $this->respond($status, $result);
        } catch (\Throwable $e) {
            $this->respond(400, ['error' => 'invalid_request']);
        }
    }

    private function respond(int $status, array $body): void
    {
        http_response_code($status);
        if ($status === 405) {
            header('Allow: POST');
        }
        echo json_encode($body, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        exit;
    }
}
