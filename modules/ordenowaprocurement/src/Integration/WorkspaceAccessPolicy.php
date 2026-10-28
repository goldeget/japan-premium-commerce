<?php

declare(strict_types=1);

namespace Ordenowa\Procurement\Integration;

/** Procurement uses native membership without exposing legacy commerce. */
final class WorkspaceAccessPolicy
{
    public static function deniesController(string $name): bool
    {
        return in_array($name, [
            'product', 'category', 'search', 'manufacturer', 'supplier', 'new-products', 'best-sales', 'prices-drop',
            'cart', 'order', 'order-opc', 'order-confirmation', 'order-detail', 'history',
            'guest-tracking', 'address', 'addresses', 'discount', 'order-follow', 'order-return', 'order-slip',
            'pdf-invoice', 'pdf-order-return', 'pdf-order-slip', 'getfile',
        ], true);
    }
}
