import requests, json, os

API_KEY = os.environ["GEMINI_API_KEY"]
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

test_keys = {
    "unsubscription-service-modal.terms": "구독 안내 및 환불 규정\n\u00b7 월간 구독은 취소 시 환불되지 않으며, 다음 정기 결제일까지 이용 가능합니다.\n\u00b7 연간 구독을 즉시 해지하는 경우, 남은 이용 기간에 대해 기존 결제수단으로 환불이 진행됩니다.\n\u00b7 취소된",
    "payment.free-trial.callout": "무료 체험이 <1>{remainingDays}</1>일 후 종료됩니다. <1>{expiredAt}</1>까지 요금이 청구되지 않습니다. 지금 구독을 예약하면 종료 시 자동 결제되어 서비스가 중단 없이 이어집니다.",
    "change-payment-date-modal.summary.payment-date": "{type, select, YEARLY {매년 {month}월 {day}일 결제} other {매월 {day}일 결제}}",
    "change-payment-date-modal.earlier-date-callout": "결제일을 기존 결제일 이전 날짜로 변경했습니다.\n다음 결제일에는 이미 선납된 기간을 제외한 금액만 결제됩니다.",
    "update-package-modal.uncontrollable-channel-package.yeogi-partner.callout": "해당 상품은 여기어때 자체 부킹엔진을 통해 생성된 상품입니다. VCMS에서는 요금 및 재고 조절이 불가합니다.",
    "subscription-service-detail-modal.inventory-and-rate-per-room.subscription-fee": "기본 {baseQuantity}객실까지 {baseFee} / 추가 객실 1개당 {additionalFee}",
    "change-subscription-service-modal.inventory-and-rate-per-room.callout": "현재 네이버 채널을 연동 중이어서, 요금 관리 중단 시 네이버 요금 설정에 영향을 줄 수 있습니다.",
    "payment.subscription-info.inventory-and-rate-per-room.description": "재고 연동을 포함해 요금까지 자동으로 관리하여 오버부킹과 요금 오류를 방지합니다.",
    "change-payment-date-modal.later-date-callout": "결제일을 기존 결제일보다 늦은 날짜로 변경했습니다. 늘어난 기간에 대한 이용 금액이 오늘 결제됩니다.",
    "payment-methods-modal.delete-button.tooltip": "서비스 구독 중으로 기본 카드를 삭제할 수 없습니다."
}

glossary = """CRITICAL GLOSSARY (must follow exactly):
- 상품 -> en:Package, ja:パッケージ, zh:套餐, es:Paquete (NOT Product)
- 예약 -> en:Booking, ja:予約, zh:预订, es:Reserva (NOT Reservation)
- 요금 -> en:Rate, ja:料金, zh:费率, es:Tarifa (NOT Price/Fee)
- 구독 -> en:Subscription, ja:サブスクリプション, zh:订阅, es:Suscripcion
- 해지 -> en:Unsubscribe, ja:解約, zh:取消订阅, es:Cancelar suscripcion
- 결제 -> en:Payment, ja:決済, zh:支付, es:Pago
- 환불 -> en:Refund, ja:返金, zh:退款, es:Reembolso
- 재고 -> en:Inventory, ja:在庫, zh:库存, es:Inventario
- 연동 -> en:Connect, ja:連携, zh:对接, es:Conectar
- 동기화 -> en:Sync, ja:同期, zh:同步, es:Sincronizacion
- 무료 체험 -> en:Free Trial, ja:無料トライアル, zh:免费试用, es:Prueba gratuita
- 정기 결제 -> en:Recurring Payment, ja:定期決済, zh:定期支付, es:Pago recurrente
- 알림 -> en:Notification, ja:通知, zh:通知, es:Notificacion"""

for lang, lang_name in [("en","English"),("ja","Japanese"),("zh","Chinese Simplified"),("es","Spanish")]:
    prompt = f"""You are a professional translator for a hospitality SaaS product (channel manager called VCMS).
Translate the following Korean UI strings into {lang_name} ({lang}).

{glossary}

RULES:
1. Follow the glossary EXACTLY
2. Preserve all {{variables}}, <1>tags</1>, ICU message format exactly
3. Preserve \\n line breaks in the same positions
4. Return ONLY valid JSON object: {{"key": "translated value"}}
5. Context: hotel/motel channel manager (like SiteMinder, Cloudbeds)

SOURCE (Korean):
{json.dumps(test_keys, ensure_ascii=False, indent=2)}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
    }

    try:
        resp = requests.post(URL, json=payload, timeout=60)
        data = resp.json()
    except Exception as e:
        print(f"\n=== {lang_name} ERROR: {e} ===")
        continue

    if "candidates" in data:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"\n{'='*60}")
        print(f"=== {lang_name} ({lang}) ===")
        print(f"{'='*60}")
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            result = json.loads(text[start:end])
            for k, v in result.items():
                print(f"  {k}")
                print(f"    -> {v}")
            print(f"\n  Keys translated: {len(result)}/10")
        except Exception as e:
            print(f"  Parse error: {e}")
            print("  Raw output:")
            print(text[:2000])

        if "usageMetadata" in data:
            um = data["usageMetadata"]
            print(f"  Tokens - input: {um.get('promptTokenCount',0)}, output: {um.get('candidatesTokenCount',0)}")
    else:
        print(f"\n=== {lang_name} ERROR ===")
        print(json.dumps(data, indent=2)[:500])

print("\n=== TEST COMPLETE ===")
