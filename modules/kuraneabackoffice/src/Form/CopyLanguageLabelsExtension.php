<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Form;

use PrestaShopBundle\Form\Admin\Improve\International\Translations\CopyLanguageType;
use Symfony\Component\Form\AbstractTypeExtension;
use Symfony\Component\Form\FormInterface;
use Symfony\Component\Form\FormView;
use Symfony\Component\HttpFoundation\RequestStack;

/** Native form themes render these two upstream labels without translating them. */
final class CopyLanguageLabelsExtension extends AbstractTypeExtension
{
    /** @param string[] $activeModules */
    public function __construct(
        private readonly RequestStack $requestStack,
        private readonly array $activeModules,
    ) {
    }

    public static function getExtendedTypes(): iterable
    {
        return [CopyLanguageType::class];
    }

    public function finishView(FormView $view, FormInterface $form, array $options): void
    {
        if (
            !in_array('kuraneabackoffice', $this->activeModules, true)
            || $this->requestStack->getCurrentRequest()?->getLocale() !== 'ko-KR'
        ) {
            return;
        }

        foreach (['from_language' => ['From', '원본 언어'], 'to_language' => ['To', '대상 언어']] as $field => [$source, $label]) {
            if (isset($view->children[$field]) && ($view->children[$field]->vars['label'] ?? null) === $source) {
                $view->children[$field]->vars['label'] = $label;
            }
        }
    }
}
