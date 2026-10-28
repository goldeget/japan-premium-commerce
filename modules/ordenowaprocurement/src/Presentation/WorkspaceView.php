<?php

declare(strict_types=1);

namespace Ordenowa\Procurement\Presentation;

/** Only customer-visible fields cross this boundary. All text is escaped by Smarty. */
final class WorkspaceView
{
    private string $locale;

    public function __construct(string $locale)
    {
        $this->locale = in_array($locale, ['ja', 'en', 'ko'], true) ? $locale : 'ja';
    }

    public function copy(): array
    {
        $rows = [
            'title' => ['発注ワークスペース', 'Procurement workspace', '발주 워크스페이스'],
            'intro' => ['ご案内の商品を確認し、発注リクエストとポイントの状況をご覧いただけます。', 'Review your assigned products, procurement requests and allowance points.', '안내받은 상품을 확인하고 발주 요청과 수당 포인트 내역을 조회하세요.'],
            'assignments' => ['発注案内商品', 'Assigned products', '발주 안내 상품'],
            'requests' => ['発注リクエスト', 'My requests', '내 발주 요청'],
            'points' => ['ポイント', 'Points', '포인트'],
            'notifications' => ['お知らせ', 'Notifications', '알림'],
            'account' => ['アカウント', 'Account', '계정'],
            'support' => ['お問い合わせ', 'Contact support', '문의'],
            'request_support' => ['このリクエストについて問い合わせる', 'Contact support about this request', '이 요청에 대해 문의'],
            'empty_assignments' => ['現在、ご案内の商品はありません。新しい案内が届くと、こちらに表示されます。', 'There are no assigned products yet. New assignments will appear here.', '현재 안내받은 상품이 없습니다. 새 안내가 도착하면 여기에 표시됩니다.'],
            'empty_requests' => ['発注リクエストはまだありません。', 'You have no procurement requests yet.', '아직 발주 요청이 없습니다.'],
            'empty_points' => ['ポイントの履歴はまだありません。', 'There are no point entries yet.', '아직 포인트 내역이 없습니다.'],
            'empty_notifications' => ['お知らせはまだありません。', 'There are no notifications yet.', '아직 알림이 없습니다.'],
            'details' => ['商品を確認', 'View product', '상품 확인'],
            'back' => ['案内商品へ戻る', 'Back to assigned products', '안내 상품으로 돌아가기'],
            'instructions' => ['運営者からのご案内', 'Instructions from the operator', '운영자 안내'],
            'description' => ['商品について', 'About this product', '상품 설명'],
            'quantity' => ['数量', 'Quantity', '수량'],
            'max_quantity' => ['数量の上限', 'Maximum quantity', '허용 최대 수량'],
            'deadline' => ['受付期限', 'Request deadline', '요청 기한'],
            'reference' => ['商品参照番号', 'Product reference', '상품 참조 번호'],
            'variant' => ['指定オプション番号', 'Assigned variant reference', '지정 옵션 번호'],
            'continue' => ['リクエスト内容を確認', 'Review request', '요청 내용 확인'],
            'confirm_title' => ['発注リクエストの確認', 'Confirm procurement request', '발주 요청 확인'],
            'confirm_help' => ['商品と数量、ご案内を確認し、発注リクエストを送信してください。送信後は内容を変更できません。', 'Check the product, quantity and instructions before submitting. The submitted details cannot be changed.', '상품, 수량, 안내 내용을 확인한 뒤 발주 요청을 제출하세요. 제출 후에는 내용을 변경할 수 없습니다.'],
            'submit' => ['発注リクエストを送信', 'Submit procurement request', '발주 요청 제출'],
            'edit' => ['数量を変更', 'Change quantity', '수량 변경'],
            'request_number' => ['リクエスト番号', 'Request number', '요청 번호'],
            'submitted_at' => ['リクエスト日時', 'Submitted', '요청 일시'],
            'status' => ['検討状況', 'Review status', '검토 상태'],
            'reason' => ['ご案内・理由', 'Reason', '안내 및 사유'],
            'request_details' => ['リクエスト詳細', 'Request details', '요청 상세'],
            'balance' => ['現在のポイント残高', 'Current point balance', '현재 포인트 잔액'],
            'point_help' => ['ポイントは運営者が承認済みリクエストを確認して手動で反映します。別途の処理については運営者へお問い合わせください。', 'The operator manually awards allowance points after reviewing an approved request. Contact the operator about any separate processing.', '운영자가 승인된 발주 요청을 확인하여 수당 포인트를 수동 반영합니다. 별도 처리는 운영자에게 문의하세요.'],
            'point_history' => ['ポイント履歴', 'Point history', '포인트 내역'],
            'point_award' => ['ポイント付与', 'Points awarded', '포인트 지급'],
            'point_correction' => ['ポイント訂正', 'Point correction', '포인트 정정'],
            'original_entry' => ['元の付与履歴', 'Original award entry', '원본 지급 내역'],
            'entry' => ['履歴番号', 'Entry', '내역 번호'],
            'date' => ['日時', 'Date', '일시'],
            'paid' => ['ポイント付与済み', 'Points awarded', '포인트 지급 완료'],
            'awaiting_points' => ['承認済み・ポイント付与待ち', 'Approved · awaiting point award', '검토 승인 · 포인트 지급 대기'],
            'unpaid' => ['ポイント未付与', 'No points awarded', '포인트 미지급'],
            'ACTIVE' => ['受付中', 'Available', '요청 가능'],
            'REQUESTED' => ['リクエスト済み', 'Requested', '요청 완료'],
            'EXPIRED' => ['期限終了', 'Expired', '기한 만료'],
            'CANCELLED' => ['取り消し', 'Cancelled', '취소'],
            'REVOKED' => ['案内取り消し', 'Assignment withdrawn', '안내 회수'],
            'SUBMITTED' => ['運営者の検討待ち', 'Awaiting operator review', '운영자 검토 대기'],
            'APPROVED' => ['承認済み', 'Approved', '승인'],
            'REJECTED' => ['承認されませんでした', 'Rejected', '반려'],
            'unknown' => ['確認中', 'Pending confirmation', '확인 중'],
            'unavailable' => ['この案内は現在リクエストできません。最新の案内をご確認ください。', 'This assignment is currently unavailable. Please check your latest assignments.', '현재 요청할 수 없는 안내입니다. 최신 안내를 확인하세요.'],
            'error_403' => ['アクセス権限を確認できません。再度ログインしてお試しください。', 'Access could not be verified. Please sign in again.', '접근 권한을 확인할 수 없습니다. 다시 로그인해 주세요.'],
            'error_404' => ['ご指定の情報は見つかりません。', 'The requested information was not found.', '요청한 정보를 찾을 수 없습니다.'],
            'error_409' => ['案内の内容が更新されたか、すでにリクエストされています。最新の状況をご確認ください。', 'The assignment has changed or was already requested. Please check the latest status.', '안내가 변경되었거나 이미 요청되었습니다. 최신 상태를 확인하세요.'],
            'error_422' => ['入力内容をご確認ください。数量は案内された上限までの整数で入力してください。', 'Please check your input. Quantity must be a whole number within the assigned limit.', '입력 내용을 확인하세요. 수량은 안내된 한도 내의 정수여야 합니다.'],
            'error_503' => ['現在情報を読み込めません。しばらくしてからもう一度お試しください。', 'The workspace is temporarily unavailable. Please try again later.', '현재 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.'],
            'error_title' => ['情報を表示できません', 'Unable to display this information', '정보를 표시할 수 없습니다'],
            'no_image' => ['商品画像なし', 'Product image unavailable', '상품 이미지 없음'],
            'photos' => ['商品写真', 'Product photos', '상품 사진'],
            'photo' => ['商品写真', 'Product photo', '상품 사진'],
            'untitled' => ['ご案内の商品', 'Assigned product', '안내 상품'],
            'notification_assignment' => ['新しい商品発注のご案内', 'A product has been assigned to you', '새 상품 발주 안내'],
            'notification_revoked' => ['商品発注のご案内が取り消されました', 'A product assignment was withdrawn', '상품 발주 안내 회수'],
            'notification_request' => ['発注リクエストを受け付けました', 'Your procurement request was received', '발주 요청 접수'],
            'notification_review' => ['発注リクエストの検討結果が届きました', 'Your request review is available', '발주 요청 검토 결과'],
            'notification_points' => ['ポイント履歴が更新されました', 'Your point history was updated', '포인트 내역 갱신'],
            'notification_general' => ['ワークスペースが更新されました', 'Your workspace was updated', '워크스페이스 갱신'],
            'latest_history' => ['最新200件を表示しています。', 'Showing the latest 200 entries.', '최근 200건을 표시합니다.'],
            'categories' => ['商品カテゴリー', 'Product categories', '상품 카테고리'],
            'all_categories' => ['すべての商品', 'All assigned products', '전체 안내 상품'],
            'reference_price' => ['参考価格', 'Reference price', '참고 가격'],
            'search' => ['商品名・参照番号で検索', 'Search product name or reference', '상품명 · 참조 번호 검색'],
            'search_button' => ['検索', 'Search', '검색'],
            'all_statuses' => ['すべての状態', 'All statuses', '전체 상태'],
            'filter_status' => ['状態', 'Status', '상태'],
            'pagination' => ['ページ切り替え', 'Page navigation', '페이지 이동'],
            'next_page' => ['次の50件', 'Next 50', '다음 50건'],
            'first_page' => ['最初のページ', 'First page', '첫 페이지'],
            'empty_search' => ['条件に一致する情報はありません。', 'No entries match these filters.', '조건에 맞는 내역이 없습니다.'],
        ];
        $index = ['ja' => 0, 'en' => 1, 'ko' => 2][$this->locale];
        return array_map(static fn (array $row): string => $row[$index], $rows);
    }

    public function assignment(array $row): array
    {
        $product = $row['product_snapshot'] ?? $row['product'] ?? [];
        $copy = $this->copy();
        $status = (string) ($row['status'] ?? '');
        $deadline = (string) ($row['deadline'] ?? '');
        $expired = $deadline !== '' && strtotime($deadline . ' UTC') !== false && strtotime($deadline . ' UTC') < time();
        if ($status === 'ACTIVE' && $expired) {
            $status = 'EXPIRED';
        }
        $categories = [];
        foreach (($product['categories'] ?? []) as $category) {
            if (is_array($category) && (int) ($category['id_category'] ?? 0) > 0) {
                $name = $this->localized($category['names'] ?? []);
                if ($name !== '') {
                    $categories[] = ['id' => (int) $category['id_category'], 'parent' => (int) ($category['id_parent'] ?? 0), 'name' => $name];
                }
            }
        }
        $price = $product['reference_price'] ?? '';
        $currency = (string) ($product['currency'] ?? '');
        $images = [];
        $candidates = array_merge([$product['image_url'] ?? ''], is_array($product['image_urls'] ?? null) ? $product['image_urls'] : []);
        foreach ($candidates as $candidate) {
            $image = is_string($candidate) ? self::publicImage($candidate) : '';
            if ($image !== '') {
                $images[$image] = $image;
            }
            if (count($images) >= 20) {
                break;
            }
        }
        $images = array_values($images);
        return [
            'id' => (int) ($row['id_assignment'] ?? 0),
            'version' => (int) ($row['version'] ?? 0),
            'name' => $this->localized($product['names'] ?? []) ?: $copy['untitled'],
            'description' => $this->localized($product['descriptions'] ?? []),
            'image' => $images[0] ?? '',
            'images' => $images,
            'image_count' => count($images),
            'reference' => (string) ($product['reference'] ?? ''),
            'variant' => (int) ($row['id_product_attribute'] ?? $product['id_product_attribute'] ?? 0),
            'instructions' => (string) ($row['instructions'] ?? ''),
            'deadline' => $deadline,
            'default_quantity' => (int) ($row['default_quantity'] ?? 1),
            'max_quantity' => (int) ($row['max_quantity'] ?? 1),
            'status' => $status,
            'status_label' => $copy[$status] ?? $copy['unknown'],
            'available' => $status === 'ACTIVE',
            'categories' => $categories,
            'reference_price' => is_string($price) && preg_match('/\A[0-9]{1,12}(?:\.[0-9]{1,4})?\z/D', $price) && preg_match('/\A[A-Z]{3}\z/D', $currency) ? $price . ' ' . $currency : '',
        ];
    }

    public function request(array $row, array $paidRequestIds): array
    {
        $view = $this->assignment($row);
        $copy = $this->copy();
        $view['id'] = (int) ($row['id_request'] ?? 0);
        $view['quantity'] = (int) ($row['quantity'] ?? 0);
        $view['submitted_at'] = (string) ($row['submitted_at'] ?? '');
        $view['review_reason'] = (string) ($row['review_reason'] ?? '');
        $view['reviewed_at'] = (string) ($row['reviewed_at'] ?? '');
        $view['point_status'] = isset($paidRequestIds[$view['id']]) ? $copy['paid'] : ($view['status'] === 'APPROVED' ? $copy['awaiting_points'] : $copy['unpaid']);
        return $view;
    }

    public function categories(array $rows): array
    {
        $result = [];
        foreach ($rows as $row) {
            $id = (int) ($row['id_category'] ?? $row['id'] ?? 0);
            $name = $this->localized($row['names'] ?? []);
            if ($id > 0 && $name !== '') {
                $result[$id] = ['id' => $id, 'parent' => (int) ($row['id_parent'] ?? $row['parent'] ?? 0), 'name' => $name];
            }
        }
        return $result;
    }

    public function categoryTree(array $categories): array
    {
        $visited = [];
        $build = function (int $id, int $depth = 0) use (&$build, &$visited, $categories): array {
            $visited[$id] = true;
            $node = $categories[$id];
            $node['children'] = [];
            if ($depth < 12) {
                foreach ($categories as $childId => $candidate) {
                    if ($candidate['parent'] === $id && !isset($visited[$childId])) {
                        $node['children'][] = $build($childId, $depth + 1);
                    }
                }
            }
            return $node;
        };
        $tree = [];
        foreach ($categories as $id => $category) {
            if (!isset($categories[$category['parent']]) || $category['parent'] === $id) {
                $tree[] = $build($id);
            }
        }
        // Preserve disconnected/cyclic source paths without recursion or dropped entries.
        foreach ($categories as $id => $category) {
            if (!isset($visited[$id])) {
                $tree[] = $build($id);
            }
        }
        return $tree;
    }

    public static function publicImage(string $url): string
    {
        // Only the canonical native public product-image tree may use same-app paths.
        if (preg_match('~\A/img/p/(?:[0-9]+/)+[0-9]+(?:-[a-zA-Z0-9_]+)?\.(?:jpg|jpeg|png|webp)\z~D', $url)) {
            return $url;
        }
        $parts = parse_url($url);
        if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || isset($parts['user']) || isset($parts['pass']) || isset($parts['port']) || !empty($parts['fragment'])) {
            return '';
        }
        $host = strtolower((string) ($parts['host'] ?? ''));
        if ($host === '' || strpos($host, '.') === false || preg_match('/[\x00-\x20\x7f\\\\]/', $url) || preg_match('/(?:^|\.)(?:localhost|local|internal|test|invalid|example)$/', $host)) {
            return '';
        }
        if (filter_var($host, FILTER_VALIDATE_IP) !== false && filter_var($host, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) === false) {
            return '';
        }
        return filter_var($url, FILTER_VALIDATE_URL) !== false ? $url : '';
    }

    private function localized(array $values): string
    {
        foreach (array_unique([$this->locale, 'ja', 'en', 'ko']) as $locale) {
            if (isset($values[$locale]) && is_string($values[$locale]) && trim($values[$locale]) !== '') {
                return $values[$locale];
            }
        }
        return '';
    }
}
