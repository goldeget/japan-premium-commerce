<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use Kuranea\BusinessProfile\Customer\SitemapUrlPolicy;

final class ConfiguredShopUrlProvider
{
    public function baseUrl(int $shopId): ?string
    {
        if ($shopId < 1) {
            return null;
        }

        $rows = \Db::getInstance()->executeS(
            'SELECT domain, domain_ssl, physical_uri, virtual_uri
            FROM ' . _DB_PREFIX_ . 'shop_url
            WHERE id_shop = ' . (int) $shopId . ' AND active = 1 AND main = 1'
        );
        if (!is_array($rows) || count($rows) !== 1 || !is_array($rows[0])) {
            return null;
        }

        $sslEnabled = (bool) \Configuration::get('PS_SSL_ENABLED', null, null, $shopId);

        return SitemapUrlPolicy::configuredBaseUrl($rows[0], $sslEnabled);
    }
}
