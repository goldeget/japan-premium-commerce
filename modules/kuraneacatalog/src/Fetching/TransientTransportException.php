<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

/** Internal transport signal; the fetcher never exposes its message or cause. */
final class TransientTransportException extends \RuntimeException
{
}
