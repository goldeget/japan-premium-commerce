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
            $this->respond([
                'candidates' => [],
                'manual_entry_available' => true,
                'error' => 'method_not_allowed',
            ], 405);
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

            $this->respond(['candidates' => $candidates, 'manual_entry_available' => true]);
        } catch (Throwable $exception) {
            $this->respond([
                'candidates' => [],
                'manual_entry_available' => true,
                'error' => 'lookup_unavailable',
            ], 503);
        }
    }

    /** @param array<string, mixed> $payload */
    private function respond(array $payload, int $status = 200): void
    {
        $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if (!is_string($json)) {
            $status = 500;
            $json = '{"candidates":[],"manual_entry_available":true,"error":"response_encoding_failed"}';
        }

        http_response_code($status);
        $this->ajaxRender($json);
        exit;
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
