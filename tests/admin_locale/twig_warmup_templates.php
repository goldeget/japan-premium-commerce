<?php

declare(strict_types=1);
require dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';

use Kuranea\Backoffice\Cache\TwigWarmupTemplates;

$expected = ['@PrestaShop/Admin/layout.html.twig', '@Modules/fixture/views/admin/form.twig', '@MailThemes/classic/order.html.twig'];
$names = [
    '@Modules/fixture/vendor/phpstan/phpstan/phpstan.phar',
    '@Modules/fixture/vendor/monolog/src/Handler.php',
    '@Modules/fixture/composer.json', '@Modules/fixture/LICENSE',
    '@Modules/fixture/views/front/page.tpl', '@Modules/fixture/views/fake.twig.php',
    ...$expected,
];
$iterator = new TwigWarmupTemplates(new ArrayIterator($names));
if (iterator_to_array($iterator, false) !== $expected) throw new RuntimeException('Only real Twig filename patterns may be eagerly compiled.');
if (iterator_to_array(new TwigWarmupTemplates(new ArrayIterator([])), false) !== []) throw new RuntimeException('Empty native template iterators remain empty.');
$invalidRejected = false;
try { iterator_to_array(new TwigWarmupTemplates(new ArrayIterator([null]))); } catch (UnexpectedValueException) { $invalidRejected = true; }
if (!$invalidRejected) throw new RuntimeException('Malformed native template names must fail visibly.');
$failure = new class implements IteratorAggregate {
    public function getIterator(): Traversable { yield '@PrestaShop/valid.html.twig'; throw new RuntimeException('Synthetic native iterator failure'); }
};
$propagated = false;
try { iterator_to_array(new TwigWarmupTemplates($failure)); } catch (RuntimeException $error) { $propagated = $error->getMessage() === 'Synthetic native iterator failure'; }
if (!$propagated) throw new RuntimeException('Native enumeration failures must not be hidden.');
$services = (string) file_get_contents(dirname(__DIR__, 2) . '/modules/kuraneabackoffice/config/services.yml');
if (!str_contains($services, 'decorates: twig.template_iterator') || !str_contains($services, "'@Kuranea\\Backoffice\\Cache\\TwigWarmupTemplates.inner'")) throw new RuntimeException('Native optional warmer iterator must use the bounded decorator.');
echo "twig_warmup_templates: PASS native Twig names retained, non-template vendor files excluded, iterator errors preserved and service decoration wired\n";
