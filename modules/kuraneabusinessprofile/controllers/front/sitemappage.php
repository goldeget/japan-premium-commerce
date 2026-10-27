<?php

declare(strict_types=1);

use Kuranea\BusinessProfile\Customer\SitemapEndpoint;
use Kuranea\BusinessProfile\Customer\XmlSitemapService;

class KuraneabusinessprofileSitemappageModuleFrontController extends ModuleFrontController
{
    public function initContent(): void
    {
        $iso = $_GET['iso'] ?? '';
        $rawPage = $_GET['page'] ?? '';
        if (!is_string($iso) || !is_string($rawPage) || preg_match('/\A[1-9][0-9]{0,4}\z/D', $rawPage) !== 1) {
            SitemapEndpoint::send(['status' => 404, 'body' => '']);
        }

        $shopId = (int) ($this->context->shop->id ?? 0);
        SitemapEndpoint::send((new XmlSitemapService())->page($shopId, $iso, (int) $rawPage));
    }
}
