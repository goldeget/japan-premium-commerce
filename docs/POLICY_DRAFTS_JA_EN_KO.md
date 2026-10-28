# ORDENOWA 정책 검토 초안 — JA / EN / KO

**상태: DRAFT · 운영자 미승인 · 미게시.** 이 파일 작성으로 DB 정책이나 동의 문안이 저장·게시되지 않았다. 실제 법인·운영자 신원, 준거법·관할, 고용/위탁 등 관계의 법적 분류, 포인트 환산율·송금 기한·지급 보증을 임의로 정하지 않는다.

## 사용 방법과 작성 근거

[승인된 발주·수동 포인트 개념](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)과 현재 회원 인증, 상품 안내/요청, 수동 검토, 별도 포인트 지급/연결 정정, 문의, 선택 Push 구현을 기준으로 작성했다. 판매·배송·반품/상품 환불 조건을 추가하지 않았다. 개인정보 항목은 native 계정·요청 snapshot·검토/원장·문의·감사/알림 및 동의 기록 범위다. 자동 삭제나 법정 보존기간이 구현·확정됐다고 쓰지 않았다.

운영자는 아홉 문안을 새로 작성하는 대신 **아래 초안을 검토·수정하고, 기존 [단일 운영 입력 체크리스트](PRODUCTION_DEPLOYMENT.md#현재-서비스의-운영-입력-체크리스트)의 미확정 값만 보완**한다. 세 언어의 의미가 같은지 확인한 뒤 승인된 본문만 해당 `terms` / `privacy` / `points`의 `ja` / `en` / `ko`에 반영한다. 승인 전 초안이나 자리표시가 남은 문구를 운영 정책 입력란에 저장하지 않는다. 실제 공개 버전과 적용일은 승인·게시 시 정하며, 이 파일에 승인을 추정해 기록하지 않는다.

사용한 자리표시는 다음 다섯 종류뿐이다. 언어별 본문에 맞게 같은 승인 사실을 번역해 채운다.

- `{{operator_name}}`: 승인된 실제 서비스 운영자명. LOGISTEED 참조정보로 대체하지 않는다.
- `{{support_email}}`: 실제 운영·개인정보 문의를 받을 승인 연락처.
- `{{retention_rules}}`: 항목별 보존기간·기산점·이용 종료/삭제 요청 후 처리와 백업 처리 기준.
- `{{processors_and_countries}}`: 실제 호스팅·메일·Push·백업 등 처리 주체/위탁 내용·취급 국가와 필요한 이전 안내.
- `{{dispute_procedure}}`: 실제 문의·이의/분쟁 처리 절차와 필요한 적용 세부. 관할이나 처리 기한을 임의로 넣지 않는다.

---

## 1. 利用規約 — `terms.ja`

1. ORDENOWAは、{{operator_name}}が利用者に商品を案内し、利用者の発注依頼、運営者による確認、手当ポイントの記録を扱うサービスです。通常の商品販売・決済・配送・返品の受付を行う画面ではありません。

2. 利用者は自分のアカウントを使い、登録情報を正確に保ってください。他人のアカウントの利用、認証情報の共有、不正な依頼や他人の記録へのアクセスを行わないでください。

3. 案内された商品・選択肢・数量・期限・運営者の説明を確認し、確認画面から発注依頼を送信してください。商品情報や参考価格は依頼内容を確認するための情報です。この操作から外部ショップへの購入、決済、発送は自動実行されません。同じ商品案内に対する発注依頼は1件です。送信内容に誤りがある場合は、依頼に関連する問い合わせまたは{{support_email}}へ連絡してください。

4. 運営者が依頼を確認し、承認・却下などの結果を記録します。依頼の受付や承認だけでポイントは付与されません。承認された依頼へのポイントは、運営者が別の操作で内容と付与理由を確認して記録します。詳細はポイント取扱方針を確認してください。

5. 利用者は自分の依頼、確認結果、ポイント残高・履歴を確認できます。問い合わせ内容と運営者の公開回答は該当利用者に表示され、運営者の内部メモは利用者向け回答とは区別されます。通知の受信だけで外部での処理完了を判断せず、アカウント内の記録を確認してください。

6. 運営者・問い合わせ先は{{operator_name}}／{{support_email}}です。問い合わせ・異議・紛争の手続きは{{dispute_procedure}}です。個人情報の取扱いはプライバシー方針に従い、適用される文書はサービス上に掲載された承認済みの版を確認してください。

## 2. プライバシー方針 — `privacy.ja`

1. 運営者は{{operator_name}}、個人情報に関する連絡先は{{support_email}}です。アカウントの氏名・メールアドレス・認証情報・入力されたプロフィール情報を、本人のログイン、アカウント管理、連絡・復旧に利用します。

2. 商品案内、依頼の商品情報・数量・送信日時、確認結果・理由、ポイント付与・訂正・残高・履歴、問い合わせと回答、処理担当者の操作記録を、依頼の確認、記録の照合、問い合わせ対応、不正利用防止に利用します。利用者が参照する依頼・ポイント・問い合わせは本人の記録に制限し、運営担当者のアクセスも担当権限に基づきます。

3. ログイン状態、言語設定、セキュリティ、Webアプリの動作のため、Cookie・ブラウザー保存情報や接続・操作記録を扱います。依頼やポイントに関する案内をサービス内またはメールで送ることがあります。

4. Web Pushは選択制です。同意した場合、配信に必要なブラウザーの購読情報、選択言語、同意文面の版・日時、登録・解除と配信状態を扱います。通知を拒否・解除しても、依頼や残高照会の利用条件にはしません。ブラウザーの通知設定またはサービスの通知設定から解除でき、詳細はログインして確認します。

5. 当サービスで利用するホスティング、メール、Push、バックアップ等の処理主体・取扱範囲・取扱国は、{{processors_and_countries}}です。

6. 保管と利用終了後の処理基準は{{retention_rules}}です。閲覧・訂正・削除・同意撤回の希望は{{support_email}}へ連絡してください。本人確認のうえ、対象記録と保管基準に沿った対応を案内します。パスワードなどの認証用秘密情報を問い合わせに記載しないでください。

## 3. ポイント取扱方針 — `points.ja`

1. ポイント画面は、運営者が記録した手当ポイントの残高、付与、訂正の履歴を表示します。利用者がポイントを購入・チャージ・使用・譲渡したり、画面から換金・送金・出金申請したりする機能はありません。

2. 運営者が商品を案内し、利用者が発注依頼を送信した後、運営者が内容を確認します。受付・承認、商品参考価格や数量だけでポイントが自動計算・付与されることはありません。承認された依頼について、運営者が別途ポイント数と理由を確認し、手動で付与を記録します。

3. 誤りを確認した場合、運営者は元の付与に関連する訂正を理由とともに記録します。利用者は残高と付与・訂正履歴を確認できます。依頼の承認と付与済みの状態は区別して確認してください。

4. サービス外で別の処理が必要な場合は、運営者が別途案内して処理します。この画面はその処理を自動実行せず、外部での支払い完了を示すものでもありません。

5. 記録に異議や不明点がある場合は、該当依頼と問題のある履歴を示して、依頼の問い合わせまたは{{support_email}}へ連絡してください。運営者{{operator_name}}が関連する依頼・確認・付与・訂正記録を確認します。具体的な異議・紛争対応手続きは{{dispute_procedure}}です。

---

## 4. Terms of use — `terms.en`

1. ORDENOWA is a service operated by {{operator_name}} for operator-assigned product instructions, customer procurement requests, manual review, and allowance-point records. These screens do not provide ordinary retail purchasing, payment, delivery, or return processing.

2. Use your own account and keep your registration information accurate. Do not share authentication information, use another person's account, submit fraudulent requests, or try to access another customer's records.

3. Check the assigned product, options, quantity, deadline and instructions before explicitly submitting the confirmation form. Product information and reference prices describe the request. Submitting it does not automatically place a purchase, payment or shipment with an external store. Each product assignment accepts one request. Contact request-specific support or {{support_email}} if a submitted detail is wrong.

4. The operator reviews the request and records its decision. Submission or approval does not itself award points. For an approved request, the operator separately checks the point amount and reason and records a manual award. See the points policy for details.

5. You can view your own requests, review results, point balance and history. Your inquiry and the operator's public replies are distinguished from internal staff notes. Check your account records; a notification alone is not confirmation that any handling outside the platform has been completed.

6. The operator and contact are {{operator_name}} and {{support_email}}. The inquiry, objection and dispute procedure is {{dispute_procedure}}. Personal information is handled under the privacy policy. Refer to the approved policy version published in the service for the applicable text.

## 5. Privacy policy — `privacy.en`

1. The operator is {{operator_name}}. Contact {{support_email}} about personal information. Account names, email addresses, authentication information and profile details you provide are used for sign-in, account administration, communication and account recovery.

2. We use product assignments, submitted product details and quantities, submission times, review decisions and reasons, point awards, corrections, balances and history, support messages and replies, and staff action records to process requests, reconcile records, answer inquiries and prevent misuse. Customer access to requests, points and inquiries is limited to the customer's own records. Staff access follows assigned permissions.

3. Cookies, browser storage and access or action records support sign-in, language settings, security and web-app operation. Service messages about requests and points may be provided in the account or by email.

4. Web Push is optional. If you consent, we handle the browser subscription information needed for delivery, selected language, consent-text version and time, subscription or revocation records, and delivery status. Refusal or revocation is not a condition of submitting requests or viewing balances. You can revoke notifications in the service or browser settings. Sign in to view detailed records.

5. The processors and external services used for hosting, email, Push and backups, their processing scope and relevant countries are: {{processors_and_countries}}.

6. Retention and handling after use ends follow {{retention_rules}}. Contact {{support_email}} to request access, correction, deletion or withdrawal of consent. After checking identity, the operator will explain the handling of the relevant records under the retention rules. Do not include passwords or other authentication secrets in support messages.

## 6. Points policy — `points.en`

1. The points screen displays the allowance-point balance, awards and corrections recorded by the operator. It does not let customers buy, top up, spend or transfer points, convert them to money, send money or apply for a withdrawal.

2. After the operator assigns a product and the customer submits a procurement request, the operator reviews it. Submission, approval, reference product prices and quantities do not automatically calculate or award points. For an approved request, the operator separately checks the amount and reason and manually records the award.

3. When an error is identified, the operator records a correction linked to the original award, with a reason. You can view the resulting balance and award/correction history. Review approval and an actual point award are separate states.

4. Any handling outside the platform is explained and performed separately by the operator. This screen does not automatically execute that handling or confirm that an external payment has been completed.

5. If a record is unclear or disputed, identify the relevant request and entry through request-specific support or {{support_email}}. The operator, {{operator_name}}, reviews the related request, decision, award and correction records. The specific objection and dispute procedure is {{dispute_procedure}}.

---

## 7. 이용약관 — `terms.ko`

1. ORDENOWA는 {{operator_name}}가 고객에게 상품을 안내하고 발주 요청, 운영자의 수동 검토, 수당 포인트 기록을 처리하는 서비스입니다. 일반 상품 판매·결제·배송·반품을 접수하는 화면이 아닙니다.

2. 본인 계정을 사용하고 등록 정보를 정확하게 유지해 주세요. 인증 정보를 공유하거나 다른 사람의 계정을 사용하지 말고, 허위 요청이나 다른 고객의 기록에 접근하는 행위를 하지 마세요.

3. 배정된 상품·옵션·수량·기한과 운영자 안내를 확인한 뒤 확인 화면에서 발주 요청을 제출해 주세요. 상품 정보와 참고 가격은 요청 내용을 확인하기 위한 정보입니다. 제출만으로 외부 쇼핑몰 구매·결제·배송이 자동 실행되지는 않습니다. 같은 발주 안내에 대한 요청은 한 번만 접수합니다. 제출 내용에 오류가 있으면 요청별 문의 또는 {{support_email}}로 알려 주세요.

4. 운영자는 요청을 수동 검토하고 승인·반려 등 결과를 기록합니다. 요청 접수나 승인만으로 포인트가 지급되지는 않습니다. 승인된 요청에 대해 운영자가 별도 작업으로 포인트와 사유를 확인하고 수동 지급을 기록합니다. 자세한 내용은 포인트 운영정책을 확인해 주세요.

5. 고객은 본인의 요청, 검토 결과, 포인트 잔액과 내역을 확인할 수 있습니다. 고객 문의와 운영자의 공개 답변은 직원 내부 메모와 구분됩니다. 알림 수신만으로 서비스 밖의 처리가 완료됐다고 판단하지 말고 계정의 기록을 확인해 주세요.

6. 운영자와 연락처는 {{operator_name}} / {{support_email}}입니다. 문의·이의·분쟁 처리 절차는 {{dispute_procedure}}입니다. 개인정보는 개인정보처리방침에 따라 처리하며, 적용 문안은 서비스에 게시된 승인 버전을 확인해 주세요.

## 8. 개인정보처리방침 — `privacy.ko`

1. 운영자는 {{operator_name}}이며 개인정보 관련 연락처는 {{support_email}}입니다. 이름·이메일·계정 인증 정보와 직접 입력한 프로필 정보는 로그인, 계정 관리, 연락과 계정 복구에 이용합니다.

2. 상품 배정, 요청 상품 정보·수량·제출 시각, 검토 결과·사유, 포인트 지급·정정·잔액·내역, 문의·답변과 담당자의 처리 기록은 발주 요청 처리, 기록 대조, 문의 대응과 부정 이용 방지에 이용합니다. 고객이 조회하는 요청·포인트·문의는 본인 기록으로 제한하며 직원의 접근은 담당 권한을 따릅니다.

3. 로그인 상태, 언어 설정, 보안과 웹앱 동작을 위해 쿠키·브라우저 저장소 및 접속·처리 기록을 이용합니다. 발주 요청과 포인트에 관한 안내를 계정 내 알림이나 이메일로 제공할 수 있습니다.

4. Web Push는 선택 사항입니다. 동의하면 전달에 필요한 브라우저 구독 정보, 선택 언어, 동의 문안 버전·시각, 등록·철회와 전달 상태를 처리합니다. 거부하거나 철회해도 발주 요청과 잔액 조회의 이용 조건으로 삼지 않습니다. 서비스 또는 브라우저의 알림 설정에서 철회할 수 있으며 자세한 내역은 로그인 후 확인합니다.

5. 이 서비스에서 사용하는 호스팅·이메일·Push·백업 등의 처리 주체, 위탁 범위와 취급 국가는 다음과 같습니다: {{processors_and_countries}}.

6. 보관 및 이용 종료 후 처리 기준은 {{retention_rules}}입니다. 열람·정정·삭제·동의 철회 요청은 {{support_email}}로 보내 주세요. 본인 확인 후 해당 기록과 보관 기준에 따른 처리 방법을 안내합니다. 문의에 비밀번호 등 계정 인증에 사용하는 비밀정보를 기재하지 마세요.

## 9. 포인트 운영정책 — `points.ko`

1. 포인트 화면은 운영자가 기록한 수당 포인트의 잔액과 지급·정정 내역을 표시합니다. 고객이 포인트를 구매·충전·사용·양도하거나 화면에서 환전·송금·출금을 신청하는 기능은 없습니다.

2. 운영자가 상품을 배정하고 고객이 발주 요청을 제출하면 운영자가 내용을 검토합니다. 접수·승인 또는 상품 참고 가격·수량만으로 포인트가 자동 계산·적립되지는 않습니다. 승인된 요청에 대해 운영자가 별도로 포인트와 사유를 확인해 수동 지급을 기록합니다.

3. 오류가 확인되면 운영자는 원래 지급에 연결된 정정을 사유와 함께 기록합니다. 고객은 반영된 잔액과 지급·정정 내역을 확인할 수 있습니다. 검토 승인과 실제 포인트 지급은 서로 다른 상태입니다.

4. 서비스 밖에서 별도의 처리가 필요하면 운영자가 따로 안내하고 처리합니다. 이 화면은 그 처리를 자동 실행하거나 외부 지급 완료를 확인하는 기능을 제공하지 않습니다.

5. 기록에 이의나 불명확한 내용이 있으면 해당 요청과 내역을 지정해 요청별 문의 또는 {{support_email}}로 연락해 주세요. 운영자 {{operator_name}}는 관련 요청·검토·지급·정정 기록을 확인합니다. 구체적인 이의·분쟁 처리 절차는 {{dispute_procedure}}입니다.
