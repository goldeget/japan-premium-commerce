<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\Catalog\Domain\ProductAdminDraft;
use Kuranea\Catalog\Integration\PrestaShopNativeProductManager;

class AdminOrdenowaProductManagerController extends ModuleAdminController
{
    private string $feedback = '';
    private bool $feedbackIsError = false;
    private int $editorProductId = 0;
    /** @var array<string,mixed> */
    private array $formValues = [];
    /** @var list<int> */
    private array $selectedImageIds = [];

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '상품 등록·관리';
    }

    public function initContent(): void
    {
        if (!$this->canView()) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">상품을 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        parent::initContent();
        $manager = new PrestaShopNativeProductManager();
        $this->editorProductId = max(0, (int) Tools::getValue('id_product', 0));

        try {
            $this->processProductSave($manager);
            if ($this->editorProductId > 0) {
                $editorData = $manager->editorData($this->editorProductId);
                $this->formValues = $this->formValues === []
                    ? $editorData
                    : array_merge($editorData, $this->formValues);
            }
            if ($this->formValues === []) {
                $this->formValues = $this->emptyFormValues();
            }
            $categories = $manager->categories();
            $taxRulesGroups = $manager->taxRulesGroups();
            $this->content .= $this->renderFeedback();
            $this->content .= $this->renderManager($manager, $categories, $taxRulesGroups);
        } catch (Throwable) {
            http_response_code(503);
            $this->content .= '<div class="alert alert-danger">상품 관리 화면을 불러오지 못했습니다. 쇼핑몰 설정과 권한을 확인해 주세요.</div>';
        }

        $this->context->smarty->assign('content', $this->content);
    }

    private function processProductSave(PrestaShopNativeProductManager $manager): void
    {
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST'
            || !Tools::isSubmit('submitKuraneaProductSave')) {
            return;
        }

        $this->editorProductId = max(0, (int) Tools::getValue('id_product', 0));
        $this->formValues = $this->submittedValues();
        $this->selectedImageIds = array_map('intval', (array) Tools::getValue('remove_image_ids', []));

        // Let PrestaShop's AdminController validate the token using the same
        // legacy/Symfony CSRF contract as the Back Office request itself.
        if (!$this->checkToken()) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.');

            return;
        }

        if ($this->editorProductId > 0 ? !$this->canEdit() : !$this->canAdd()) {
            $this->fail($this->editorProductId > 0 ? '상품을 수정할 권한이 없습니다.' : '상품을 등록할 권한이 없습니다.');

            return;
        }

        try {
            $draft = ProductAdminDraft::fromArray($this->formValues);
            $savedId = $manager->save(
                $this->editorProductId > 0 ? $this->editorProductId : null,
                $draft,
                $this->normalizedUploads(),
                $this->selectedImageIds
            );
            $this->editorProductId = $savedId;
            $this->formValues = $manager->editorData($savedId);
            $this->selectedImageIds = [];
            $this->succeed(sprintf('상품 ID %d를 비활성 상태로 저장했습니다.', $savedId));
        } catch (\InvalidArgumentException $exception) {
            $this->fail($exception->getMessage());
        } catch (Throwable) {
            $this->fail('상품 저장에 실패했습니다. 입력값, 이미지 파일 및 PrestaShop 상품 설정을 확인해 주세요.');
        }
    }

    /** @return array<string,mixed> */
    private function submittedValues(): array
    {
        return [
            'name_ja' => Tools::getValue('name_ja', ''),
            'name_en' => Tools::getValue('name_en', ''),
            'name_ko' => Tools::getValue('name_ko', ''),
            'price_jpy' => Tools::getValue('price_jpy', ''),
            'tax_rules_group_id' => Tools::getValue('tax_rules_group_id', null),
            'quantity' => Tools::getValue('quantity', '0'),
            'category_ids' => Tools::getValue('category_ids', []),
            'description_ja' => Tools::getValue('description_ja', ''),
            'description_en' => Tools::getValue('description_en', ''),
            'description_ko' => Tools::getValue('description_ko', ''),
            'options' => Tools::getValue('options', ''),
            'combination_quantities' => Tools::getValue('combination_quantities', []),
        ];
    }

    /** @return list<array{name:string,tmp_name:string,size:int,error:int}> */
    private function normalizedUploads(): array
    {
        $files = $_FILES['product_images'] ?? null;
        if (!is_array($files) || !is_array($files['name'] ?? null)) {
            return [];
        }

        $uploads = [];
        foreach ($files['name'] as $index => $name) {
            $uploads[] = [
                'name' => (string) $name,
                'tmp_name' => (string) ($files['tmp_name'][$index] ?? ''),
                'size' => (int) ($files['size'][$index] ?? 0),
                'error' => (int) ($files['error'][$index] ?? UPLOAD_ERR_NO_FILE),
            ];
        }

        return $uploads;
    }

    /** @param list<array{id_category:int,name:string}> $categories
     *  @param list<array{id_tax_rules_group:int,name:string}> $taxRulesGroups
     */
    private function renderManager(PrestaShopNativeProductManager $manager, array $categories, array $taxRulesGroups): string
    {
        $action = (string) $this->context->link->getAdminLink('AdminOrdenowaProductManager');
        $token = (string) Tools::getAdminTokenLite('AdminOrdenowaProductManager');
        $editing = $this->editorProductId > 0;
        $values = $this->formValues;
        $selectedTaxRulesGroupId = $values['tax_rules_group_id'] ?? '';
        $selectedCategories = array_map('intval', (array) ($values['category_ids'] ?? []));
        $imageIds = array_map('intval', (array) ($values['image_ids'] ?? []));
        $html = '<div class="row"><div class="col-lg-8"><section class="panel">'
            . '<h3>' . ($editing ? '상품 수정' : '새 상품 등록') . '</h3>'
            . '<p class="alert alert-info">상품은 기본적으로 비활성·비노출·주문 불가 상태로 저장됩니다. 이 화면에는 판매 활성화 기능이 없습니다.</p>'
            . '<form method="post" enctype="multipart/form-data" action="' . $this->escape($action) . '">'
            . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
            . '<input type="hidden" name="id_product" value="' . $this->editorProductId . '">'
            . $this->renderTextField('name_ja', '상품명 (일본어)', (string) ($values['name_ja'] ?? ''), true, '예: ORDENOWA CI 合成商品')
            . $this->renderTextField('name_en', '상품명 (영어)', (string) ($values['name_en'] ?? ''), false, '영어 고객 화면에 표시할 상품명입니다. 비워 두면 일본어 상품명을 사용합니다.')
            . $this->renderTextField('name_ko', '상품명 (한국어)', (string) ($values['name_ko'] ?? ''), false, '고객 언어별 상품명을 입력합니다.')
            . $this->renderTaxRulesGroupField($taxRulesGroups, $selectedTaxRulesGroupId)
            . $this->renderTextField('price_jpy', '세금 포함 판매 가격 (JPY)', (string) ($values['price_jpy'] ?? ''), true, '고객에게 표시할 세금 포함 가격입니다. 선택한 일본 세금 규칙 그룹으로 세전 금액을 환산합니다. 주소별 세율이 달라 하나의 가격으로 환산할 수 없으면 저장이 차단됩니다.')
            . $this->renderTextField('quantity', '기본 재고 수량', (string) ($values['quantity'] ?? '0'), true, '옵션이 없는 상품의 상품 재고로 적용됩니다. 옵션 조합을 새로 만들 때는 기본값으로 사용하며, 기존 조합은 아래 개별 재고가 우선합니다.')
            . $this->renderCategories($categories, $selectedCategories)
            . $this->renderTextArea('options', '상품 옵션', (string) ($values['options'] ?? ''), '그룹명:값1|값2 형식으로 한 줄씩 입력합니다. 예: 色:青|赤')
            . $this->renderCombinationQuantities(
                (array) ($values['combination_stock_rows'] ?? []),
                (array) ($values['combination_quantities'] ?? [])
            )
            . $this->renderTextArea('description_ja', '상세 설명 (일본어)', (string) ($values['description_ja'] ?? ''), '텍스트로 입력하며 HTML은 실행되지 않습니다.')
            . $this->renderTextArea('description_en', '상세 설명 (영어)', (string) ($values['description_en'] ?? ''), '영어 고객 화면에 표시할 상세 설명입니다. 비워 두면 일본어 상세 설명을 사용합니다.')
            . $this->renderTextArea('description_ko', '상세 설명 (한국어)', (string) ($values['description_ko'] ?? ''), '비워 두면 일본어 상세 설명을 사용합니다.')
            . $this->renderImages($imageIds, $this->selectedImageIds)
            . '<div class="form-group"><button class="btn btn-primary" type="submit" name="submitKuraneaProductSave" value="1">'
            . ($editing ? '상품 수정 저장' : '비활성 상품 등록') . '</button> '
            . ($editing ? '<a class="btn btn-default" href="' . $this->escape($action) . '">새 상품 등록</a>' : '')
            . '</div></form></section></div>';
        $html .= '<div class="col-lg-4"><section class="panel"><h3>ORDENOWA 관리 상품</h3>';

        try {
            $products = $manager->managedProducts();
        } catch (Throwable) {
            $products = [];
        }
        if ($products === []) {
            $html .= '<p>등록한 상품이 없습니다.</p>';
        } else {
            $html .= '<ul class="list-unstyled">';
            foreach ($products as $product) {
                $url = $action . (str_contains($action, '?') ? '&' : '?') . 'id_product=' . (int) $product['id_product'];
                $html .= '<li class="well"><a href="' . $this->escape($url) . '">' . $this->escape($product['name']) . '</a>'
                    . '<br><span>' . number_format((int) $product['price']) . ' JPY · ID ' . (int) $product['id_product'] . '</span>'
                    . '<br><small>비활성 · 비노출 · 주문 불가</small></li>';
            }
            $html .= '</ul>';
        }
        $html .= '</section></div></div>';

        return $html;
    }

    private function renderTextField(string $name, string $label, string $value, bool $required, string $hint): string
    {
        $requiredAttribute = $required ? ' required' : '';
        $type = $name === 'price_jpy' || $name === 'quantity' ? 'number' : 'text';
        $min = $name === 'price_jpy' ? ' min="1" step="1"' : ($name === 'quantity' ? ' min="0" step="1"' : '');

        return '<div class="form-group"><label for="' . $this->escape($name) . '">' . $this->escape($label) . '</label>'
            . '<input class="form-control" id="' . $this->escape($name) . '" name="' . $this->escape($name) . '" type="' . $type . '" value="' . $this->escape($value) . '"' . $requiredAttribute . $min . '>'
            . '<p class="help-block">' . $this->escape($hint) . '</p></div>';
    }

    /** @param list<array{id_category:int,name:string}> $categories
     *  @param list<int> $selected
     */
    private function renderCategories(array $categories, array $selected): string
    {
        $html = '<fieldset class="form-group"><legend>카테고리</legend>';
        foreach ($categories as $category) {
            $id = (int) $category['id_category'];
            $checked = in_array($id, $selected, true) ? ' checked' : '';
            $html .= '<label class="checkbox-inline"><input type="checkbox" name="category_ids[]" value="' . $id . '"' . $checked . '> '
                . $this->escape($category['name']) . '</label> ';
        }
        if ($categories === []) {
            $html .= '<p>사용 가능한 카테고리가 없습니다.</p>';
        }

        return $html . '</fieldset>';
    }

    private function renderTextArea(string $name, string $label, string $value, string $hint): string
    {
        $rows = $name === 'options' ? 4 : 7;

        return '<div class="form-group"><label for="' . $this->escape($name) . '">' . $this->escape($label) . '</label>'
            . '<textarea class="form-control" id="' . $this->escape($name) . '" name="' . $this->escape($name) . '" rows="' . $rows . '">'
            . $this->escape($value) . '</textarea><p class="help-block">' . $this->escape($hint) . '</p></div>';
    }

    /** @param list<array{id_tax_rules_group:int,name:string}> $taxRulesGroups */
    private function renderTaxRulesGroupField(array $taxRulesGroups, int|string $selectedId): string
    {
        $html = '<div class="form-group"><label for="tax_rules_group_id">세금 규칙 그룹</label>'
            . '<select class="form-control" id="tax_rules_group_id" name="tax_rules_group_id" required>';
        if ($selectedId === '') {
            $html .= '<option value="" disabled selected>세금 규칙 그룹을 선택해 주세요</option>';
        }
        foreach ($taxRulesGroups as $taxRulesGroup) {
            $id = (int) $taxRulesGroup['id_tax_rules_group'];
            $selected = (string) $id === (string) $selectedId ? ' selected' : '';
            $label = $id === 0
                ? (string) $taxRulesGroup['name']
                : (string) $taxRulesGroup['name'] . ' · ID ' . $id;
            $html .= '<option value="' . $id . '"' . $selected . '>' . $this->escape($label) . '</option>';
        }

        return $html . '</select><p class="help-block">현재 쇼핑몰에 등록된 PrestaShop 세금 규칙만 선택할 수 있습니다. 세금 규칙 미할당은 계산 규칙이 연결되지 않았다는 뜻이며 과세 여부를 법적으로 결정하지 않습니다. 실제 과세 처리는 판매자·상품의 세금 설정에 따라 별도로 확인해야 합니다.</p></div>';
    }

    /**
     * @param list<array{id_product_attribute:int,label:string,quantity:int}> $rows
     * @param array<int|string, mixed> $quantities
     */
    private function renderCombinationQuantities(array $rows, array $quantities): string
    {
        $html = '<fieldset class="form-group"><legend>옵션 조합별 재고</legend>';
        if ($rows === []) {
            return $html . '<p>상품과 옵션을 먼저 저장하면 조합마다 재고 수량을 입력할 수 있습니다.</p></fieldset>';
        }

        $html .= '<p class="help-block">각 옵션 조합의 실제 재고를 입력하세요. 수량은 0 이상이어야 합니다.</p>';
        foreach ($rows as $row) {
            $combinationId = (int) ($row['id_product_attribute'] ?? 0);
            if ($combinationId < 1) {
                continue;
            }
            $rawQuantity = $quantities[$combinationId] ?? $quantities[(string) $combinationId] ?? ($row['quantity'] ?? 0);
            $quantity = is_string($rawQuantity) || is_int($rawQuantity)
                ? trim((string) $rawQuantity)
                : (string) ($row['quantity'] ?? 0);
            if (preg_match('/\A[0-9]{1,7}\z/D', $quantity) !== 1) {
                $quantity = (string) ($row['quantity'] ?? 0);
            }
            $label = trim((string) ($row['label'] ?? '')) ?: '조합 ' . $combinationId;
            $html .= '<div class="form-group"><label for="combination-quantity-' . $combinationId . '">'
                . $this->escape($label) . '</label><input class="form-control" id="combination-quantity-'
                . $combinationId . '" name="combination_quantities[' . $combinationId
                . ']" type="number" min="0" max="9999999" step="1" required value="'
                . $this->escape($quantity) . '"></div>';
        }

        return $html . '</fieldset>';
    }

    /** @param list<int> $imageIds */
    private function renderImages(array $imageIds, array $selectedImageIds): string
    {
        $html = '<div class="form-group"><label for="product_images">상품 이미지</label>'
            . '<input class="form-control" id="product_images" name="product_images[]" type="file" accept="image/jpeg,image/png,image/webp" multiple>'
            . '<p class="help-block">JPEG, PNG, WEBP · 이미지당 최대 10MB · 한 번에 최대 5개</p>';
        if ($imageIds !== []) {
            $html .= '<div class="ordenowa-product-images">';
            foreach ($imageIds as $imageId) {
                if ($imageId < 1) {
                    continue;
                }
                $imageUrl = (string) $this->context->link->getImageLink('ordenowa-product', $imageId, 'small_default');
                $checked = in_array($imageId, $selectedImageIds, true) ? ' checked' : '';
                $html .= '<label class="ordenowa-product-image"><img src="' . $this->escape($imageUrl) . '" alt="상품 이미지 ' . $imageId . '" width="96" height="96"> '
                    . '<input type="checkbox" name="remove_image_ids[]" value="' . $imageId . '"' . $checked . '> 삭제</label> ';
            }
            $html .= '</div>';
        }

        return $html . '</div>';
    }

    private function emptyFormValues(): array
    {
        return [
            'name_ja' => '',
            'name_en' => '',
            'name_ko' => '',
            'price_jpy' => '',
            'tax_rules_group_id' => '',
            'quantity' => '0',
            'category_ids' => [],
            'description_ja' => '',
            'description_en' => '',
            'description_ko' => '',
            'options' => '',
            'image_ids' => [],
        ];
    }

    private function canView(): bool
    {
        return $this->viewAccess();
    }

    private function canAdd(): bool
    {
        return $this->canView() && $this->access('add');
    }

    private function canEdit(): bool
    {
        return $this->canView() && $this->access('edit');
    }

    private function fail(string $message): void
    {
        $this->feedback = $message;
        $this->feedbackIsError = true;
    }

    private function succeed(string $message): void
    {
        $this->feedback = $message;
        $this->feedbackIsError = false;
    }

    private function renderFeedback(): string
    {
        if ($this->feedback === '') {
            return '';
        }

        return '<div class="alert ' . ($this->feedbackIsError ? 'alert-danger' : 'alert-success') . '">' . $this->escape($this->feedback) . '</div>';
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
