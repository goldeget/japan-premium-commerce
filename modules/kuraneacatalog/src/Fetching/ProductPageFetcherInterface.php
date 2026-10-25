<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

interface ProductPageFetcherInterface
{
    public function fetch(string $url): FetchedProduct;
}
