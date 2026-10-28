<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Notifications;

interface Transport
{
    /** Event identifiers only; adapters resolve the current native recipient. */
    public function send(array $event): DeliveryResult;
}
