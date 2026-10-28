<?php

declare(strict_types=1);
namespace Kuranea\Backoffice\Admin;

use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpKernel\Event\ResponseEvent;
use Symfony\Component\HttpKernel\KernelEvents;

/** PS9 LegacyController creates a new Response; carry explicit module failures into that response. */
final class AdminResponseSubscriber implements EventSubscriberInterface
{
    public const STATUS_ATTRIBUTE = '_ordenowa_admin_status';
    private const CONTROLLERS = ['adminordenowaprocurement','adminordenowaprocurementreviews','adminordenowaprocurementpoints','adminordenowaprocurementaudit','adminordenowaprocurementpolicies','adminkuraneapush'];

    public function __construct(private readonly AdminPostTokenValidator $tokens, private readonly array $activeModules) {}

    public static function getSubscribedEvents(): array
    {
        return [KernelEvents::RESPONSE => ['onResponse', -255]];
    }

    public static function mark(object $controller, int $status): void
    {
        if (!in_array($status,[403,404,409,422,503],true)) return;
        try {
            $request = $controller->getContainer()->get('request_stack')->getMainRequest();
            if ($request !== null) $request->attributes->set(self::STATUS_ATTRIBUTE,$status);
        } catch (\Throwable) {
            // Native CLI render fixtures have no Symfony request. Their direct HTTP code is still set by the controller.
        }
    }

    public function onResponse(ResponseEvent $event): void
    {
        if (!$event->isMainRequest() || !in_array('kuraneabackoffice',$this->activeModules,true)) return;
        $request = $event->getRequest();
        $name = $request->attributes->get('_legacy_controller_name',$request->query->get('controller',''));
        if (!is_string($name) || !in_array(strtolower($name),self::CONTROLLERS,true)
            || !str_starts_with((string)$request->attributes->get('_route',''),'admin_')) return;
        $response = $event->getResponse();
        $response->headers->set('Cache-Control','private, no-store, max-age=0');
        $response->headers->set('Pragma','no-cache');
        $response->headers->set('Expires','0');
        $response->headers->set('X-Robots-Tag','noindex, nofollow');
        $status = $request->attributes->get(self::STATUS_ATTRIBUTE);
        try {
            if ($request->isMethod('POST') && !$this->tokens->valid($request->request->get('token'))) $status = 403;
            elseif ($request->isMethod('GET') && $request->query->has('token') && !$this->tokens->valid($request->query->get('token'))) $status = 403;
        } catch (\Throwable) { $status = 403; }
        if (is_int($status) && in_array($status,[403,404,409,422,503],true)) $response->setStatusCode($status);
    }
}
