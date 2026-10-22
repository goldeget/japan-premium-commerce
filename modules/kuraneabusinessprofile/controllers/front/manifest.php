<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Customer\PwaManifestBuilder;

class KuraneabusinessprofileManifestModuleFrontController extends ModuleFrontController
{
    public function initContent(): void
    {
        $profile = $this->module->publicProfile();
        if ($profile === null) {
            $profile = ProfileDefaults::initial();
            $profile['_resolved_locale'] = 'ja-JP';
        }

        $manifest = PwaManifestBuilder::build($profile, (string) $this->context->link->getBaseLink());

        http_response_code(200);
        header('Content-Type: application/manifest+json; charset=utf-8');
        header('Cache-Control: no-store, max-age=0');
        header('X-Content-Type-Options: nosniff');
        echo json_encode($manifest, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        exit;
    }

}
