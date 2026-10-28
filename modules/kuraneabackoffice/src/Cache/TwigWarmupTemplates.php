<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Cache;

/** Restrict eager Twig compilation to templates; runtime loaders remain unchanged. */
final class TwigWarmupTemplates implements \IteratorAggregate
{
    public function __construct(private readonly iterable $templates) {}

    public function getIterator(): \Traversable
    {
        foreach ($this->templates as $template) {
            if (!is_string($template)) throw new \UnexpectedValueException('Native Twig template names must be strings.');
            // Equivalent to Symfony Twig's documented file_name_pattern: '*.twig'.
            // PrestaShop registers the whole modules directory as @Modules, which
            // otherwise makes its optional warmer parse PHP libraries and PHARs.
            if (str_ends_with($template, '.twig')) yield $template;
        }
    }
}
