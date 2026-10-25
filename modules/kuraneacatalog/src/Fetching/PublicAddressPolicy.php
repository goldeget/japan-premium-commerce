<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

final class PublicAddressPolicy
{
    /** Fail the entire answer set if any address is nonpublic or malformed. */
    public static function validate(array $addresses): array
    {
        if ($addresses === [] || count($addresses) > 64) {
            throw new FetchException('Product host has no permitted public destination.');
        }
        foreach ($addresses as $address) {
            if (!is_string($address) || !self::isPublic($address)) {
                throw new FetchException('Product host has no permitted public destination.');
            }
        }
        return array_values(array_unique($addresses));
    }

    private static function isPublic(string $address): bool
    {
        if (filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4) !== false) {
            foreach (['0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
                '169.254.0.0/16', '172.16.0.0/12', '192.0.0.0/24', '192.0.2.0/24',
                '192.88.99.0/24', '192.168.0.0/16', '198.18.0.0/15', '198.51.100.0/24',
                '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4'] as $range) {
                if (self::inRange($address, $range)) return false;
            }
            return true;
        }
        // Only global unicast IPv6, excluding special-purpose/documentation and
        // transition ranges. This also rejects every IPv4-mapped IPv6 address.
        return filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6) !== false
            && self::inRange($address, '2000::/3')
            && !self::inRange($address, '2001::/23')
            && !self::inRange($address, '2001:db8::/32')
            && !self::inRange($address, '2002::/16')
            && !self::inRange($address, '5f00::/16')
            && !self::inRange($address, '3fff::/20');
    }

    private static function inRange(string $address, string $range): bool
    {
        [$network, $prefix] = explode('/', $range);
        $packed = inet_pton($address);
        $base = inet_pton($network);
        if ($packed === false || $base === false || strlen($packed) !== strlen($base)) return false;
        $bytes = intdiv((int) $prefix, 8);
        $bits = (int) $prefix % 8;
        return substr($packed, 0, $bytes) === substr($base, 0, $bytes)
            && ($bits === 0 || (ord($packed[$bytes]) & (255 << (8 - $bits))) === (ord($base[$bytes]) & (255 << (8 - $bits))));
    }
}
