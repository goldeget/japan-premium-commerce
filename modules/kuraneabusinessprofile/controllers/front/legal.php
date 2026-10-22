<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\BusinessProfile\Customer\CommerceGate;
use Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder;
use Kuranea\BusinessProfile\Customer\PublishedProfileProvider;
use Kuranea\BusinessProfile\Domain\ProfileDefaults;

class KuraneabusinessprofileLegalModuleFrontController extends ModuleFrontController
{
    public function initContent(): void
    {
        parent::initContent();

        // Resolve only the published pointer. Unsaved drafts and historical versions stay private.
        $profile = $this->module->publicProfile();
        if ($profile === null) {
            $profile = ProfileDefaults::initial();
            $profile['_resolved_locale'] = PublishedProfileProvider::localeForIso(
                (string) ($this->context->language->iso_code ?? 'ja')
            );
        }

        $commerceEnabled = CommerceGate::isEnabled(
            $profile,
            getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'
        );
        $title = PublishedLegalPageBuilder::title($profile);

        header('Cache-Control: no-store, max-age=0');
        header('X-Content-Type-Options: nosniff');
        $this->context->smarty->assign([
            'ordenowaLegalPageTitle' => $title,
            'ordenowaLegalPageContent' => PublishedLegalPageBuilder::build($profile, $commerceEnabled),
        ]);
        $this->setTemplate('module:kuraneabusinessprofile/views/templates/front/legal.tpl');
    }
}
