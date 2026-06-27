#!/usr/bin/env python3
"""
Lpicture 高才班 WhatsApp 語音訊息處理服務（非同步版本）
接收 ManyChat Webhook → 立即回應 200 OK → 背景處理語音 → ManyChat API 回覆
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
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
)

# ManyChat API Token
MANYCHAT_API_TOKEN = os.environ.get("MANYCHAT_API_TOKEN", "5050783:ecad251cad044a3b02714425dc66e7ca")

# Lpicture 高才班課程資訊
SYSTEM_PROMPT = """你係 Lpicture 高才班嘅智能助理，代表子龍老師回覆學員查詢。

【關於 Lpicture 高才班】
Lpicture 係一個專注於 AI 工具、WhatsApp 自動化、影片製作等實用技能嘅培訓課程。
講師：子龍
課程特色：陪你做到先下課、即學即用、完全免費工具

【最新課程】
課程名稱：免費無人駕駛 WhatsApp 炸 PM班
日期：7月7日
限額：30人（額滿即止）
費用：$500（見習生優惠：完成課程返還$300，實際只需$200）
報名方法：入group → https://chat.whatsapp.com/JfFZdFuy0PAG7bGBOVT1Zo

【回覆原則】
1. 用廣東話回覆，語氣親切友善
2. 回覆要簡短清晰，不要太長
3. 如果問到課程，提供上述資訊
4. 如果問題超出範圍，叫對方直接聯絡子龍老師
5. 不要捏造任何資訊"""


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
        print(f"[ManyChat] 發送結果: {response.status_code} - {response.text[:200]}")
        return response.json()
    except Exception as e:
        print(f"[ManyChat] 發送失敗: {e}")


def process_in_background(subscriber_id: str, media_url: str, last_input: str, first_name: str):
    """在背景執行緒處理語音或文字"""
    try:
        if media_url and media_url.strip():
            # 處理語音訊息
            print(f"[BG] 下載語音: {media_url}")
            response = requests.get(media_url, timeout=30)
            response.raise_for_status()

            # 判斷副檔名
            suffix = ".ogg"
            for ext in [".mp4", ".mp3", ".wav", ".m4a", ".ogg"]:
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
                    send_manychat_message(subscriber_id, "😅 唔好意思，我聽唔清楚，可以再說一次嗎？")
                    return

                # 用 ChatGPT 生成回覆
                chat = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=300
                )
                reply = chat.choices[0].message.content
                full_reply = f"🎙️ 我聽到你講：\n「{text}」\n\n{reply}"
                send_manychat_message(subscriber_id, full_reply)

            finally:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)

        elif last_input and last_input.strip():
            # 處理文字訊息（非關鍵字觸發）
            print(f"[BG] 處理文字: {last_input}")
            chat = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": last_input}
                ],
                max_tokens=300
            )
            reply = chat.choices[0].message.content
            send_manychat_message(subscriber_id, reply)

    except Exception as e:
        print(f"[BG] 背景處理錯誤: {e}")
        try:
            send_manychat_message(subscriber_id, "抱歉，處理您的訊息時出現問題，請稍後再試或用文字告訴我您的問題 😊")
        except:
            pass


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Lpicture Voice Bot is running!"}), 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """主要 Webhook 端點 - 立即回應 200 OK，背景處理"""
    if request.method == "GET":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(force=True, silent=True) or {}
        print(f"[WEBHOOK] 收到資料: {json.dumps(data, ensure_ascii=False)[:500]}")

        # 立即提取資料
        subscriber_id = str(data.get("id") or data.get("subscriber_id") or "")
        first_name = data.get("first_name", "客人")
        media_url = data.get("last_input_file_url", "") or ""
        last_input = data.get("last_input_text", "") or data.get("last_input", "") or ""

        print(f"[WEBHOOK] subscriber_id={subscriber_id}, media_url={media_url[:50] if media_url else ''}, last_input={last_input[:50] if last_input else ''}")

        # 立即啟動背景執行緒
        if subscriber_id and (media_url or last_input):
            t = threading.Thread(
                target=process_in_background,
                args=(subscriber_id, media_url, last_input, first_name),
                daemon=True
            )
            t.start()

        # 立即回應 200 OK（必須在 10 秒內）
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[WEBHOOK] 錯誤: {e}")
        return jsonify({"status": "ok"}), 200  # 即使出錯也回應 200


@app.route("/test", methods=["GET", "POST"])
def test():
    """測試端點"""
    return jsonify({
        "status": "ok",
        "message": "Lpicture Voice Bot 運作正常！",
        "received": request.get_json(silent=True) or {}
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Lpicture Voice Bot 啟動中... Port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
