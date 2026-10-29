<?php

declare(strict_types=1);

namespace Symfony\Component\EventDispatcher {
    interface EventSubscriberInterface
    {
        public static function getSubscribedEvents(): array;
    }
}

namespace Symfony\Component\HttpKernel {
    final class KernelEvents
    {
        public const EXCEPTION = 'kernel.exception';
    }
}

namespace {
    $subscriberFile = dirname(__DIR__, 2)
        . '/modules/kuraneabackoffice/src/AdminFacebookTransportExceptionSubscriber.php';
    if (!is_file($subscriberFile)) {
        throw new RuntimeException('subscriber_file_missing');
    }

    require_once $subscriberFile;

    $class = 'Kuranea\\Backoffice\\AdminFacebookTransportExceptionSubscriber';
    $correctInterface = 'Symfony\\Component\\EventDispatcher\\EventSubscriberInterface';
    $wrongInterface = 'Symfony\\Component\\HttpKernel\\EventSubscriberInterface';
    if (!interface_exists($correctInterface, false) || interface_exists($wrongInterface, false)
        || !class_exists($class, false)) {
        throw new RuntimeException('subscriber_or_stub_interface_contract_failed');
    }

    $reflection = new ReflectionClass($class);
    if (!$reflection->implementsInterface($correctInterface)) {
        throw new RuntimeException('subscriber_event_dispatcher_interface_mismatch');
    }
    $events = $class::getSubscribedEvents();
    if ($events !== ['kernel.exception' => ['onKernelException', 64]]) {
        throw new RuntimeException('subscriber_event_registration_contract_failed');
    }

    echo "PASS subscriber class loads against EventDispatcher contract\n";
}
