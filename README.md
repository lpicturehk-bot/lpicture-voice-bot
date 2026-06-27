# Lpicture 高才班 WhatsApp Voice Bot

## 功能
- 接收 ManyChat Webhook
- 自動轉錄語音訊息（OpenAI Whisper）
- AI 回覆課程查詢（GPT-4o-mini）
- 非同步處理（立即回應 200 OK，背景處理）

## 環境變數
- `OPENAI_API_KEY`：OpenAI API 金鑰
- `MANYCHAT_API_TOKEN`：ManyChat API Token（格式：`{page_id}:{token}`）

## 部署到 Render.com
1. 上傳此目錄到 GitHub
2. 在 Render.com 建立 Web Service，連接 GitHub repo
3. 設定環境變數
4. 部署完成後，將 Webhook URL 填入 ManyChat External Request

## Webhook URL
`https://your-service.onrender.com/webhook`
