<?php

declare(strict_types=1);

// Uses the installed native Symfony form implementation without config/DB bootstrap.
$sourceRoot = $argv[2] ?? dirname(__DIR__, 2);
require $argv[1] ?? $sourceRoot . '/vendor/autoload.php';
require $sourceRoot . '/modules/kuraneabackoffice/vendor/autoload.php';

use Kuranea\Backoffice\Form\CopyLanguageLabelsExtension;
use PrestaShop\PrestaShop\Adapter\LegacyContext;
use PrestaShopBundle\Form\Admin\Improve\International\Translations\CopyLanguageType;
use PrestaShopBundle\Form\Admin\Type\LocaleChoiceType;
use Symfony\Component\Form\Extension\Core\Type\FormType;
use Symfony\Component\Form\Extension\Core\Type\TextType;
use Symfony\Component\Form\Extension\Csrf\CsrfExtension;
use Symfony\Component\Form\Forms;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\RequestStack;
use Symfony\Component\Security\Csrf\CsrfToken;
use Symfony\Component\Security\Csrf\CsrfTokenManagerInterface;
use Symfony\Component\Translation\Translator;

$checks = 0;
function check(bool $condition, string $label): void
{
    global $checks;
    ++$checks;
    if (!$condition) throw new RuntimeException($label);
}

check(iterator_to_array((static function (): iterable { yield from CopyLanguageLabelsExtension::getExtendedTypes(); })()) === [CopyLanguageType::class], 'Extension targets the native copy-language type only.');
$legacy = new class extends LegacyContext {
    public function getLanguages($active = true, $id_shop = false, $ids_only = false)
    {
        return [['name' => 'Japanese', 'iso_code' => 'ja'], ['name' => 'Korean', 'iso_code' => 'ko']];
    }
};
$tokens = new class implements CsrfTokenManagerInterface {
    public function getToken(string $tokenId): CsrfToken { return new CsrfToken($tokenId, 'synthetic-token'); }
    public function refreshToken(string $tokenId): CsrfToken { return $this->getToken($tokenId); }
    public function removeToken(string $tokenId): ?string { return null; }
    public function isTokenValid(CsrfToken $token): bool { return $token->getValue() === 'synthetic-token'; }
};
foreach ([['ko-KR', ['kuraneabackoffice'], true], ['ja-JP', ['kuraneabackoffice'], false], ['en-US', ['kuraneabackoffice'], false], ['ko-KR', [], false], [null, ['kuraneabackoffice'], false]] as [$locale, $active, $changes]) {
    $requests = new RequestStack();
    if ($locale !== null) {
        $request = Request::create('/');
        $request->setLocale($locale);
        $requests->push($request);
    }
    $extension = new CopyLanguageLabelsExtension($requests, $active);
    $factory = Forms::createFormFactoryBuilder()
        ->addExtension(new CsrfExtension($tokens))
        ->addType(new LocaleChoiceType($legacy))
        ->addType(new CopyLanguageType(new Translator('en-US'), [], ['Native theme' => 'native-theme']))
        ->addTypeExtension($extension)
        ->getFormFactory();
    $form = $factory->create(CopyLanguageType::class, ['from_language' => 'ja', 'to_language' => 'ko', 'from_theme' => 'native-theme', 'to_theme' => 'native-theme'], ['csrf_protection' => true]);
    $view = $form->createView();
    check($view['from_language']->vars['label'] === ($changes ? '원본 언어' : 'From'), 'Native form factory applies only Korean source-language label.');
    check($view['to_language']->vars['label'] === ($changes ? '대상 언어' : 'To'), 'Native form factory applies only Korean target-language label.');
    check($view['from_language']->vars['value'] === 'ja' && $view['to_language']->vars['value'] === 'ko', 'Selected native locale values remain unchanged.');
    check($view['_token']->vars['value'] === 'synthetic-token' && $form->getConfig()->getOption('csrf_protection') === true, 'Native CSRF view and configured protection remain present.');
    check(count($view['from_language']->vars['choices']) === 2 && $view['from_theme']->vars['label'] === false, 'Native choices and unrelated labels remain intact.');

    // Apply to an actual native view with raw/custom labels and compare every var.
    $view['from_language']->vars['label'] = 'From';
    $view['to_language']->vars['label'] = 'Custom target language';
    $before = $view->vars;
    $childVars = array_map(static fn ($child): array => $child->vars, $view->children);
    $extension->finishView($view, $form, []);
    check($view->vars === $before, 'Parent form vars are preserved exactly.');
    foreach ($view->children as $field => $child) {
        $expected = $childVars[$field];
        if ($changes && $field === 'from_language') $expected['label'] = '원본 언어';
        check($child->vars === $expected, 'Only the exact raw source label may change; all child vars remain intact.');
    }
    $date = $factory->createBuilder(FormType::class)->add('from', TextType::class, ['label' => 'From'])->add('to', TextType::class, ['label' => 'To'])->getForm()->createView();
    check($date['from']->vars['label'] === 'From' && $date['to']->vars['label'] === 'To', 'Global date-context labels and unrelated form types remain unchanged.');
}
$services = (string) file_get_contents($sourceRoot . '/modules/kuraneabackoffice/config/services.yml');
check(str_contains($services, 'Kuranea\\Backoffice\\Form\\CopyLanguageLabelsExtension:') && str_contains($services, 'name: form.type_extension'), 'Native Symfony form type extension is registered.');
echo "copy_language_labels: PASS {$checks} native form checks, exact Korean labels, custom labels/choices/values/CSRF preserved\n";
