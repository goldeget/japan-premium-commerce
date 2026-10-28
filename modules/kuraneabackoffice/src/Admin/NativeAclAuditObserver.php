<?php

declare(strict_types=1);
namespace Kuranea\Backoffice\Admin;

use Kuranea\Backoffice\Infrastructure\NativeAclAuditRepository;

/** Official native Before hooks wrap AdminAccess's die() action in one audited transaction. */
final class NativeAclAuditObserver
{
    private static ?array $pending = null;
    private static bool $shutdownRegistered = false;

    public static function before(array $params, string $kind): void
    {
        $controller = $params['controller'] ?? null;
        $action = $kind === 'TAB' ? 'updateAccess' : 'updateModuleAccess';
        $submit = $kind === 'TAB' ? 'submitAddAccess' : 'changeModuleAccess';
        if (!in_array($kind,['TAB','MODULE'],true) || !$controller instanceof \AdminAccessControllerCore
            || ($controller->controller_name ?? '') !== 'AdminAccess' || empty($controller->ajax)
            || \Tools::getValue('action') !== $action || !\Tools::isSubmit($submit)
            || (defined('_PS_MODE_DEMO_') && _PS_MODE_DEMO_)
            || !$controller->checkToken() || (string)$controller->access('edit') !== '1') return;
        $context = \Context::getContext();
        $employee = $context->employee ?? null;
        $profile = \Tools::getValue('id_profile');
        if (!$employee instanceof \Employee || !$employee->isLoggedBack() || !(bool)$employee->active
            || !is_scalar($profile) || preg_match('/\A[1-9][0-9]*\z/D',(string)$profile) !== 1 || filter_var($profile,FILTER_VALIDATE_INT) === false) {
            throw new NativeAclAuditUnavailableException('권한 변경 대상과 관리자 세션을 확인할 수 없습니다. 다시 로그인한 뒤 확인해 주세요.');
        }
        $actor = (int)$employee->id;
        $actorProfile = (int)$employee->id_profile;
        $target = (int)$profile;
        $shop = \Shop::getContext() === \Shop::CONTEXT_SHOP ? (int)($context->shop->id ?? 0) : 0;
        $repository = null;
        $lock = null;
        $transaction = false;
        $bufferLevel = null;
        try {
            $repository = new NativeAclAuditRepository();
            if (!$repository->actorMatches($actor,$actorProfile,$shop) || !$repository->profileExists($target)) throw new \RuntimeException('Native ACL actor or target could not be verified.');
            if (self::$pending !== null || headers_sent()) throw new \RuntimeException('ACL observation cannot buffer a native response.');
            $lock = $repository->lock($target);
            $repository->begin($kind);
            $transaction = true;
            $before = $repository->snapshot($target,$kind);
            // Discard premature flushes. Only finish() may release the captured native "ok" after commit.
            if (!ob_start(static fn(string $chunk): string => '')) throw new \RuntimeException('ACL response buffering unavailable.');
            $bufferLevel = ob_get_level();
            self::$pending = compact('repository','lock','before','shop','actor','actorProfile','target','kind','bufferLevel')
                + ['correlation'=>bin2hex(random_bytes(16))];
            if (!self::$shutdownRegistered) { register_shutdown_function([self::class,'finish']); self::$shutdownRegistered = true; }
        } catch (\Throwable $error) {
            if ($bufferLevel !== null) while (ob_get_level() >= $bufferLevel) { if (!ob_end_clean()) break; }
            if ($transaction) { try { $repository->rollback(); } catch (\Throwable) {} }
            if ($lock !== null) { try { $repository->unlock($lock); } catch (\Throwable) {} }
            error_log('ORDENOWA native ACL audit preparation failed.');
            // ModuleErrorInterface propagates through native Hook and is caught before its permission mutation.
            throw new NativeAclAuditUnavailableException('권한 변경 감사 기록을 준비하지 못했습니다. 잠시 후 다시 시도해 주세요.',0,$error);
        }
    }

    public static function finish(): void
    {
        $pending = self::$pending;
        self::$pending = null;
        if ($pending === null) return;
        $repository = $pending['repository'];
        $body = '';
        $committed = false;
        try {
            $last = error_get_last();
            $fatal = $last !== null && in_array($last['type'],[E_ERROR,E_PARSE,E_CORE_ERROR,E_COMPILE_ERROR,E_USER_ERROR,E_RECOVERABLE_ERROR],true);
            if ($fatal || ob_get_level() !== $pending['bufferLevel']) throw new \RuntimeException('Native ACL action did not complete safely.');
            $body = (string)ob_get_contents();
            // Both native PS9 actions return exactly "ok" or "error" via die(). A failed/partial update rolls back.
            if ($body !== 'ok') throw new \RuntimeException('Native ACL action did not report success.');
            $after = $repository->snapshot($pending['target'],$pending['kind'],$pending['before']);
            $repository->appendChanges($pending['shop'],$pending['actor'],$pending['actorProfile'],$pending['target'],$pending['kind'],$pending['before'],$after,$pending['correlation']);
            $repository->commit();
            $committed = true;
        } catch (\Throwable) {
            try { $repository->rollback(); } catch (\Throwable) { error_log('ORDENOWA native ACL audit rollback failed.'); }
            error_log('ORDENOWA native ACL change rolled back because audited completion failed.');
        } finally {
            while (ob_get_level() >= $pending['bufferLevel']) { if (!ob_end_clean()) break; }
            try { $repository->unlock($pending['lock']); } catch (\Throwable) { error_log('ORDENOWA native ACL audit lock release failed.'); }
        }
        if (!$committed) {
            if (!headers_sent()) http_response_code(503);
            echo 'error';
            return;
        }
        echo $body;
    }
}
