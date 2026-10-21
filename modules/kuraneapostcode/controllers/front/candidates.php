<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/autoload.php';

use Kuranea\Postcode\Domain\CandidateSearchService;
use Kuranea\Postcode\Domain\PrefectureCatalog;
use Kuranea\Postcode\Infrastructure\DatabasePostalAddressLookup;

class KuraneapostcodeCandidatesModuleFrontController extends ModuleFrontController
{
    public function initContent()
    {
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store, private');
        header('X-Content-Type-Options: nosniff');

        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET')) !== 'GET') {
            header('Allow: GET');
            http_response_code(405);
            $this->ajaxDie(Tools::jsonEncode([
                'candidates' => [],
                'manual_entry_available' => true,
                'error' => 'method_not_allowed',
            ]));
        }

        $query = Tools::getValue('q', '');
        if (!is_string($query)) {
            $query = '';
        }

        try {
            $search = new CandidateSearchService(new DatabasePostalAddressLookup());
            $addresses = $search->search($query, 100);
            $stateIds = $this->prefectureStateIds();
            $candidates = [];

            foreach ($addresses as $address) {
                $native = $address->toNativeAddressFields($stateIds);
                $candidates[] = [
                    'candidate_id' => $address->candidateId,
                    'postcode' => $address->postcode,
                    'prefecture' => $address->prefecture,
                    'municipality' => $address->municipality,
                    'town' => $address->town,
                    'state_id' => $native['id_state'] ?? null,
                ];
            }

            $payload = ['candidates' => $candidates, 'manual_entry_available' => true];
            $this->ajaxDie(Tools::jsonEncode($payload));
        } catch (Throwable $exception) {
            http_response_code(503);
            $this->ajaxDie(Tools::jsonEncode([
                'candidates' => [],
                'manual_entry_available' => true,
                'error' => 'lookup_unavailable',
            ]));
        }
    }

    /** @return array<string, int> */
    private function prefectureStateIds(): array
    {
        $countryId = (int) Country::getByIso('JP');
        if ($countryId < 1) {
            return [];
        }

        $stateIds = [];
        $states = State::getStatesByIdCountry($countryId, true, 'iso_code', 'asc');
        if (!is_array($states)) {
            return [];
        }

        foreach ($states as $state) {
            $isoCode = (string) $state['iso_code'];
            if (preg_match('/^JP-([0-9]{2})$/D', $isoCode, $matches) === 1
                && isset(PrefectureCatalog::all()[$matches[1]])) {
                $stateIds[$matches[1]] = (int) $state['id_state'];
            }
        }

        return $stateIds;
    }
}
