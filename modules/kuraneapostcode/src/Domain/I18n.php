<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class I18n
{
    /** @var array<string, array<string, string>> */
    private const STRINGS = [
        'ja' => [
            'search_label' => '郵便番号・住所検索',
            'search_placeholder' => '郵便番号または住所を入力',
            'search_button' => '住所を検索',
            'no_results' => '候補が見つかりません。住所を直接入力できます。',
            'choose_hint' => '該当する住所を選択してください。',
            'invalid_postcode' => '郵便番号は7桁で入力してください。',
        ],
        'en' => [
            'search_label' => 'Postcode or address search',
            'search_placeholder' => 'Enter a postcode or Japanese address',
            'search_button' => 'Search address',
            'no_results' => 'No matches. You can enter the address manually.',
            'choose_hint' => 'Choose the matching address.',
            'invalid_postcode' => 'Enter a valid 7-digit Japanese postcode.',
        ],
        'ko' => [
            'search_label' => '우편번호·주소 검색',
            'search_placeholder' => '우편번호 또는 일본 주소 입력',
            'search_button' => '주소 검색',
            'no_results' => '검색 결과가 없습니다. 주소를 직접 입력할 수 있습니다.',
            'choose_hint' => '해당하는 주소를 선택하세요.',
            'invalid_postcode' => '일본 우편번호 7자리를 입력해 주세요.',
        ],
    ];

    public static function text(string $key, string $locale): string
    {
        $language = strtolower((string) strtok($locale, '-_'));
        $language = isset(self::STRINGS[$language]) ? $language : 'ja';

        return self::STRINGS[$language][$key] ?? $key;
    }

    /** @return array<string, string> */
    public static function all(string $locale): array
    {
        $language = strtolower((string) strtok($locale, '-_'));
        $language = isset(self::STRINGS[$language]) ? $language : 'ja';

        return self::STRINGS[$language];
    }
}
