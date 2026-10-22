<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneabusinessprofile/autoload.php';

function assertOrderConfirmationMailSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertOrderConfirmationMailTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$profile = [
    '_resolved_locale' => 'ko-KR',
    'brand' => [
        'name' => ['ko-KR' => '오데노와 <테스트>'],
        'description' => ['ko-KR' => '기업 <구매> & 판매'],
        'slogan' => ['ko-KR' => '안전한 주문'],
    ],
    'seller' => [
        'legal_name' => ['ko-KR' => '한국 판매자 <script>alert(1)</script>'],
        'corporate_number' => '1234567890123',
        'address' => ['ko-KR' => '서울 & 부산'],
        'representative' => ['ko-KR' => '홍길동'],
        'responsible_person' => ['ko-KR' => '김담당'],
        'support' => ['phone' => '02-1234-5678', 'email' => 'seller@example.invalid'],
    ],
    'customer_support' => [
        'phone' => '02-9876-5432',
        'email' => 'help@example.invalid',
        'hours' => ['ko-KR' => '평일 9:00-17:00'],
    ],
    'payment' => ['ko-KR' => '계좌이체 안내'],
    'shipping' => ['ko-KR' => '배송 안내'],
    'refund' => ['ko-KR' => '반품 및 환불 안내'],
    'content' => [
        'terms' => ['ko-KR' => '이용약관'],
        'privacy' => ['ko-KR' => '개인정보 처리방침'],
        'specified_commercial_act' => ['ko-KR' => '특정상거래법 표시'],
    ],
    'bank_accounts' => [],
];

$originalHtml = '<!doctype html><html><body><h1>{order_name}</h1><div>{products}</div><p>{total_paid}</p></body></html>';
$originalText = "주문 {order_name}\n{products_txt}\n{total_paid}";
$html = $originalHtml;
$text = $originalText;

assertOrderConfirmationMailTrue(
    \Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent::append('order_conf', $html, $text, $profile, true),
    'The customer order confirmation should receive its published profile block.'
);

$htmlBlockPosition = strpos($html, '<section class="ordenowa-public-brand"');
$bodyClosePosition = stripos($html, '</body>');
assertOrderConfirmationMailTrue($htmlBlockPosition !== false && $bodyClosePosition !== false, 'The profile block should be placed before the closing body tag.');
assertOrderConfirmationMailTrue($htmlBlockPosition < $bodyClosePosition, 'The profile block must remain inside the existing HTML document body.');
assertOrderConfirmationMailSame(
    substr($originalHtml, 0, stripos($originalHtml, '</body>')),
    substr($html, 0, $htmlBlockPosition),
    'Existing HTML bytes and core placeholders before the insertion point must be preserved.'
);
assertOrderConfirmationMailSame(
    substr($originalHtml, stripos($originalHtml, '</body>')),
    substr($html, stripos($html, '</body>')),
    'Existing HTML closing bytes must be preserved.'
);
foreach (['{order_name}', '{products}', '{total_paid}'] as $corePlaceholder) {
    assertOrderConfirmationMailTrue(str_contains($html, $corePlaceholder), 'The core HTML placeholder must remain untouched: ' . $corePlaceholder);
}
assertOrderConfirmationMailTrue(str_contains($html, '결제 안내'), 'Published profile content must use the mail language locale.');
assertOrderConfirmationMailTrue(str_contains($html, '&lt;script&gt;alert(1)&lt;/script&gt;'), 'Published profile values must be escaped for HTML email output.');
assertOrderConfirmationMailTrue(!str_contains($html, '<script>alert(1)</script>'), 'Raw profile markup must not be emitted into the HTML email.');

assertOrderConfirmationMailSame($originalText, substr($text, 0, strlen($originalText)), 'Existing plain text bytes and placeholders must be preserved.');
foreach (['{order_name}', '{products_txt}', '{total_paid}', '결제 안내', '계좌이체 안내'] as $textContent) {
    assertOrderConfirmationMailTrue(str_contains($text, $textContent), 'The plain text email should retain core placeholders and append localized profile content: ' . $textContent);
}

$unrelatedHtml = '<html><body>{order_name}</body></html>';
$unrelatedText = 'Order {order_name}';
assertOrderConfirmationMailSame(
    false,
    \Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent::append('new_order', $unrelatedHtml, $unrelatedText, $profile, true),
    'Other email templates must not be modified.'
);
assertOrderConfirmationMailSame('<html><body>{order_name}</body></html>', $unrelatedHtml, 'An unrelated HTML template must remain byte-for-byte unchanged.');
assertOrderConfirmationMailSame('Order {order_name}', $unrelatedText, 'An unrelated text template must remain byte-for-byte unchanged.');

$bodylessHtml = '<html><main>{order_name}</main></html>';
$bodylessText = 'Order {order_name}';
assertOrderConfirmationMailSame(
    false,
    \Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent::append('order_conf', $bodylessHtml, $bodylessText, $profile, true),
    'A malformed HTML template without a body end marker should fail closed.'
);
assertOrderConfirmationMailSame('<html><main>{order_name}</main></html>', $bodylessHtml, 'A bodyless HTML template must remain unchanged.');
assertOrderConfirmationMailSame('Order {order_name}', $bodylessText, 'A bodyless HTML template must not cause a text-only partial modification.');

$unapprovedHtml = '<html><body>{order_name}</body></html>';
$unapprovedText = 'Order {order_name}';
assertOrderConfirmationMailTrue(
    \Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent::append('order_conf', $unapprovedHtml, $unapprovedText, $profile, false),
    'Published brand identity may be included while commerce disclosures remain gated.'
);
assertOrderConfirmationMailTrue(str_contains($unapprovedHtml, '오데노와'), 'Published brand identity should remain available in the email.');
foreach (['한국 판매자', '1234567890123', '계좌이체 안내', '반품 및 환불 안내'] as $gatedValue) {
    assertOrderConfirmationMailTrue(!str_contains($unapprovedHtml, $gatedValue), 'Unapproved commerce data must not appear in HTML: ' . $gatedValue);
    assertOrderConfirmationMailTrue(!str_contains($unapprovedText, $gatedValue), 'Unapproved commerce data must not appear in plain text: ' . $gatedValue);
}

echo "PASS: order confirmation mail appends localized published profile content without replacing core template bytes\n";
