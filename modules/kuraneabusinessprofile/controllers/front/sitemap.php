<?php

declare(strict_types=1);

use Kuranea\BusinessProfile\Customer\SitemapEndpoint;
use Kuranea\BusinessProfile\Customer\XmlSitemapService;

class KuraneabusinessprofileSitemapModuleFrontController extends ModuleFrontController
{
    public function initContent(): void
    {
        $shopId = (int) ($this->context->shop->id ?? 0);
        SitemapEndpoint::send((new XmlSitemapService())->index($shopId));
    }
}
