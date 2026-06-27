#!/usr/bin/env python3
"""
Lpicture 高才班 WhatsApp 聊天機械人（非同步版本）
接收 ManyChat Webhook → 立即回應 200 OK → 背景處理語音/文字 → ManyChat API 回覆
"""

import os
import json
import tempfile
import threading
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# OpenAI 客戶端
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

# ManyChat API Token
MANYCHAT_API_TOKEN = os.environ.get("MANYCHAT_API_TOKEN", "5050783:ecad251cad044a3b02714425dc66e7ca")

# ============================================================
# Lpicture 高才班 銷售漏斗 System Prompt
# ============================================================
SYSTEM_PROMPT = """你係 Lpicture 高才班嘅智能助理「小龍」，代表子龍老師回覆潛在學員查詢。
你嘅目標係：透過友善對話，引導對方一步一步成為付費學員。

【關於 Lpicture 高才班】
Lpicture 係一個專注於 AI 工具、WhatsApp 自動化、影片製作等實用技能嘅培訓課程。
講師：子龍（業界10年經驗，教過超過500名學員）
課程特色：陪你做到先下課、即學即用、完全免費工具、小班教學

【最新課程】
課程名稱：免費無人駕駛 WhatsApp 炸 PM班
日期：7月7日（星期一）晚上8時
地點：Zoom 網上課堂
限額：30人（額滿即止，已有18人報名）
費用：$500（見習生優惠：完成課程返還$300，實際只需$200）
報名方法：入group → https://chat.whatsapp.com/JfFZdFuy0PAG7bGBOVT1Zo

【銷售漏斗引導策略 - 非常重要！】
你要根據對話情況，循序漸進地引導對方：

第一步 - 建立興趣：
- 如果對方問「係咩課程」或「有咩學」，先講課程亮點，然後問「你而家係做咩行業嘅？」
- 了解對方背景，讓回覆更個人化

第二步 - 激發需求：
- 如果對方表示有興趣，問「你而家有冇用緊任何 AI 工具？」
- 根據答案，解釋點解呢個課程對佢特別有用

第三步 - 消除疑慮：
- 如果對方問費用，強調「見習生優惠」：完成課程返還$300，實際只需$200
- 如果對方猶豫，提醒「只剩12個名額」製造緊迫感

第四步 - 促成行動：
- 最後一定要引導：「你而家入埋個 group 先，入面有詳細資料：https://chat.whatsapp.com/JfFZdFuy0PAG7bGBOVT1Zo」
- 或者：「你想我幫你登記名額？只需要留低你個名同電話就得！」

【回覆原則】
1. 用廣東話回覆，語氣親切、有溫度，好似朋友咁
2. 每次回覆不超過150字，保持對話感
3. 每次回覆結尾一定要有一個問題或行動呼籲（CTA）
4. 如果問到課程以外嘅問題，先回答，然後自然地帶回課程話題
5. 不要捏造任何資訊，如果唔知，叫對方直接問子龍老師

【常見問題回覆】
Q: 係咩課程？
A: 呢個係「免費無人駕駛 WhatsApp 炸 PM班」！教你用 AI 自動化幫你做 WhatsApp 行銷，完全唔需要寫程式。你係做咩生意嘅？

Q: 幾錢？
A: 課程費用係$500，但有個特別優惠：完成課程可以返還$300，即係實際只需$200！而且名額唔多，你想了解更多嗎？

Q: 幾時？
A: 7月7日（星期一）晚上8時，Zoom 網上進行，唔需要出門！你方唔方便？

Q: 我唔識電腦/AI
A: 完全唔需要基礎！子龍老師會由零開始教，陪你做到識為止。好多學員都係零基礎入來，最後都做到！你想試試嗎？"""


def send_manychat_message(subscriber_id: str, text: str):
    """透過 ManyChat API 發送訊息"""
    url = "https://api.manychat.com/fb/sending/sendContent"
    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "subscriber_id": subscriber_id,
        "data": {
            "version": "v2",
            "content": {
                "messages": [{"type": "text", "text": text}]
            }
        },
        "message_tag": "ACCOUNT_UPDATE"
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"[ManyChat] 發送結果: {response.status_code} - {response.text[:300]}")
        return response.json()
    except Exception as e:
        print(f"[ManyChat] 發送失敗: {e}")


def extract_subscriber_id(data: dict) -> str:
    """從各種格式的 ManyChat JSON 中提取 subscriber_id"""
    invalid_values = ["None", "null", "{No field selected}", "", " "]
    # 嘗試各種可能的欄位名稱
    for key in ["id", "subscriber_id", "user_id", "contact_id"]:
        val = data.get(key)
        if val and str(val).strip() and str(val).strip() not in invalid_values:
            return str(val).strip()
    
    # 嘗試從 Full Contact Data 格式中提取
    if "data" in data and isinstance(data["data"], dict):
        for key in ["id", "subscriber_id", "contact_id"]:
            val = data["data"].get(key)
            if val and str(val).strip() and str(val).strip() not in invalid_values:
                return str(val).strip()
    
    # 嘗試從 contact 嵌套格式中提取
    if "contact" in data and isinstance(data["contact"], dict):
        for key in ["id", "subscriber_id"]:
            val = data["contact"].get(key)
            if val and str(val).strip() and str(val).strip() not in invalid_values:
                return str(val).strip()
    
    return ""


def extract_text_input(data: dict) -> str:
    """從各種格式的 ManyChat JSON 中提取用戶輸入文字"""
    invalid_values = ["None", "null", "{No field selected}", "", " "]
    for key in ["last_input_text", "last_text_input", "last_input", "text", "message", "input", "body"]:
        val = data.get(key)
        if val and str(val).strip() and str(val).strip() not in invalid_values:
            return str(val).strip()
    # 嘗試嵌套格式
    if "data" in data and isinstance(data["data"], dict):
        for key in ["last_input_text", "last_text_input", "text"]:
            val = data["data"].get(key)
            if val and str(val).strip() and str(val).strip() not in invalid_values:
                return str(val).strip()
    return ""


def extract_media_url(data: dict) -> str:
    """從各種格式的 ManyChat JSON 中提取媒體 URL"""
    invalid_values = ["None", "null", "{No field selected}", "", " "]
    for key in ["last_input_file_url", "media_url", "file_url", "audio_url", "voice_url", "attachment_url"]:
        val = data.get(key)
        if val and str(val).strip() and str(val).strip() not in invalid_values:
            url_val = str(val).strip()
            if url_val.startswith("http"):
                return url_val
    # 嘗試嵌套格式
    if "data" in data and isinstance(data["data"], dict):
        for key in ["last_input_file_url", "media_url", "file_url"]:
            val = data["data"].get(key)
            if val and str(val).strip() and str(val).strip() not in invalid_values:
                url_val = str(val).strip()
                if url_val.startswith("http"):
                    return url_val
    return ""


def process_in_background(subscriber_id: str, media_url: str, last_input: str, first_name: str):
    """在背景執行緒處理語音或文字"""
    try:
        if media_url and media_url.strip() and media_url.startswith("http"):
            # 處理語音訊息
            print(f"[BG] 下載語音: {media_url[:100]}")
            try:
                response = requests.get(media_url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                print(f"[BG] 下載語音失敗: {e}")
                send_manychat_message(subscriber_id, "😅 唔好意思，我收唔到你嘅語音，可以用文字再說一次嗎？")
                return

            # 判斷副檔名
            suffix = ".ogg"
            for ext in [".mp4", ".mp3", ".wav", ".m4a", ".ogg", ".webm"]:
                if ext in media_url.lower():
                    suffix = ext
                    break

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(response.content)
                audio_path = f.name

            try:
                print(f"[BG] 開始 Whisper 轉錄...")
                with open(audio_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="zh"
                    )
                text = transcript.text.strip()
                print(f"[BG] 轉錄結果: {text}")

                if not text:
                    send_manychat_message(subscriber_id, "😅 唔好意思，我聽唔清楚，可以再說一次或用文字嗎？")
                    return

                # 用 ChatGPT 生成回覆
                chat = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"[語音訊息轉文字] {text}"}
                    ],
                    max_tokens=400
                )
                reply = chat.choices[0].message.content
                full_reply = f"🎙️ 我聽到你講：「{text}」\n\n{reply}"
                send_manychat_message(subscriber_id, full_reply)

            finally:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)

        elif last_input and last_input.strip():
            # 處理文字訊息
            print(f"[BG] 處理文字: {last_input[:100]}")
            chat = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": last_input}
                ],
                max_tokens=400
            )
            reply = chat.choices[0].message.content
            send_manychat_message(subscriber_id, reply)
        
        else:
            print(f"[BG] 沒有可處理的內容 (subscriber_id={subscriber_id})")

    except Exception as e:
        print(f"[BG] 背景處理錯誤: {e}")
        import traceback
        traceback.print_exc()
        try:
            send_manychat_message(subscriber_id, "抱歉，處理您的訊息時出現問題，請稍後再試或用文字告訴我您的問題 😊")
        except:
            pass


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Lpicture Voice Bot is running! v3.0"}), 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """主要 Webhook 端點 - 立即回應 200 OK，背景處理"""
    if request.method == "GET":
        return jsonify({"status": "ok"}), 200

    try:
        # 嘗試解析 JSON，支援各種格式
        raw_body = request.get_data(as_text=True)
        print(f"[WEBHOOK] ===== 收到新請求 =====")
        print(f"[WEBHOOK] Content-Type: {request.content_type}")
        print(f"[WEBHOOK] 原始 Body: {raw_body[:2000]}")
        
        data = request.get_json(force=True, silent=True) or {}
        print(f"[WEBHOOK] 解析後資料鍵值: {list(data.keys())}")
        print(f"[WEBHOOK] 解析後資料: {json.dumps(data, ensure_ascii=False)[:1000]}")

        # 優先從 URL Query String 讀取（ManyChat URL 變數方式）
        qs_id = request.args.get("id", "").strip()
        qs_text = request.args.get("text", "").strip()
        qs_media = request.args.get("media", "").strip()
        qs_name = request.args.get("name", "").strip()
        if qs_id or qs_text or qs_media:
            print(f"[WEBHOOK] Query String 模式: id={qs_id}, text={qs_text[:50] if qs_text else 'EMPTY'}, media={qs_media[:50] if qs_media else 'EMPTY'}")

        # 使用強健的提取函數（Query String 優先，再 fallback 到 JSON Body）
        subscriber_id = qs_id or extract_subscriber_id(data)
        first_name = qs_name or data.get("first_name", "") or data.get("name", "") or "朋友"
        media_url = qs_media or extract_media_url(data)
        last_input = qs_text or extract_text_input(data)

        print(f"[WEBHOOK] 提取結果: subscriber_id={subscriber_id}, first_name={first_name}")
        print(f"[WEBHOOK] media_url={media_url[:80] if media_url else 'EMPTY'}")
        print(f"[WEBHOOK] last_input={last_input[:80] if last_input else 'EMPTY'}")

        # 立即啟動背景執行緒
        if subscriber_id and (media_url or last_input):
            t = threading.Thread(
                target=process_in_background,
                args=(subscriber_id, media_url, last_input, first_name),
                daemon=True
            )
            t.start()
            print(f"[WEBHOOK] 背景執行緒已啟動")
        else:
            print(f"[WEBHOOK] 跳過背景處理: subscriber_id={subscriber_id}, has_media={bool(media_url)}, has_text={bool(last_input)}")
            if not subscriber_id:
                print(f"[WEBHOOK] ⚠️ 警告：無法提取 subscriber_id！請檢查 ManyChat 設定")
                print(f"[WEBHOOK] 完整資料: {json.dumps(data, ensure_ascii=False)[:500]}")

        # 立即回應 200 OK（必須在 10 秒內）
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[WEBHOOK] 錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "ok"}), 200  # 即使出錯也回應 200


@app.route("/debug", methods=["POST", "GET"])
def debug():
    """Debug 端點 - 顯示收到的完整 JSON"""
    raw_body = request.get_data(as_text=True)
    data = request.get_json(force=True, silent=True) or {}
    result = {
        "status": "ok",
        "raw_body": raw_body[:2000],
        "parsed_data": data,
        "data_keys": list(data.keys()),
        "extracted": {
            "subscriber_id": extract_subscriber_id(data),
            "first_name": data.get("first_name", ""),
            "media_url": extract_media_url(data),
            "last_input": extract_text_input(data)
        }
    }
    print(f"[DEBUG] {json.dumps(result, ensure_ascii=False)[:1000]}")
    return jsonify(result), 200


@app.route("/echo", methods=["POST", "GET"])
def echo():
    """Echo 端點 - 回傳收到的所有資料（用於調試 ManyChat 發送的格式）"""
    raw_body = request.get_data(as_text=True)
    data = request.get_json(force=True, silent=True) or {}
    args = dict(request.args)
    headers = dict(request.headers)
    
    result = {
        "status": "ok",
        "method": request.method,
        "query_string": args,
        "body_raw": raw_body[:2000],
        "body_parsed": data,
        "body_keys": list(data.keys()),
        "headers": {k: v for k, v in headers.items() if k.lower() not in ["authorization", "cookie"]}
    }
    print(f"[ECHO] {json.dumps(result, ensure_ascii=False)[:2000]}")
    return jsonify(result), 200


@app.route("/test_send", methods=["GET"])
def test_send():
    """測試發送訊息到指定 subscriber_id"""
    subscriber_id = request.args.get("id", "")
    message = request.args.get("msg", "👋 Hello from Lpicture Bot！測試訊息")
    if not subscriber_id:
        return jsonify({"error": "請提供 ?id=subscriber_id"}), 400
    result = send_manychat_message(subscriber_id, message)
    return jsonify({"status": "ok", "result": result}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Lpicture Voice Bot v3.0 啟動中... Port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
