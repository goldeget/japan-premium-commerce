<?php

declare(strict_types=1);
namespace Ordenowa\Procurement\Support;

final class SupportView
{
    public static function copy(string $locale): array
    {
        return match ($locale) {
            'en' => ['title'=>'Request support','back'=>'Back to request','intro'=>'Messages about this procurement request. Only you and support staff can read this conversation.',
                'empty'=>'No messages yet.','you'=>'You','operator'=>'Support','message'=>'Message','send'=>'Send message','limit'=>'Up to 2,000 characters. Attachments are unavailable.',
                'error'=>'This conversation could not be opened or updated. Check your request and try again.','latest'=>'The latest 100 public messages are displayed.'],
            'ko' => ['title'=>'발주 요청 문의','back'=>'발주 요청으로 돌아가기','intro'=>'이 발주 요청에 관한 문의입니다. 본인과 고객 지원 직원만 대화를 확인할 수 있습니다.',
                'empty'=>'아직 문의 내역이 없습니다.','you'=>'나','operator'=>'고객 지원','message'=>'문의 내용','send'=>'문의 보내기','limit'=>'2,000자 이내로 입력해 주세요. 첨부 파일은 지원하지 않습니다.',
                'error'=>'문의를 열거나 저장하지 못했습니다. 발주 요청을 확인한 뒤 다시 시도해 주세요.','latest'=>'최근 공개 메시지 100개를 표시합니다.'],
            default => ['title'=>'発注依頼のお問い合わせ','back'=>'発注依頼に戻る','intro'=>'この発注依頼についてのお問い合わせです。ご本人とサポート担当者が確認できます。',
                'empty'=>'お問い合わせはまだありません。','you'=>'あなた','operator'=>'サポート','message'=>'お問い合わせ内容','send'=>'送信する','limit'=>'2,000文字以内で入力してください。添付ファイルには対応していません。',
                'error'=>'お問い合わせを表示または保存できませんでした。発注依頼を確認して、もう一度お試しください。','latest'=>'直近100件の公開メッセージを表示します。'],
        };
    }
}
