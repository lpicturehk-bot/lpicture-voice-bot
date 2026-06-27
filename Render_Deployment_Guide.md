# 🚀 Lpicture Voice Bot - Render.com 部署教學

你選擇了**自己寫程式開發（路線 B）**，這是一個非常專業且省錢的決定！

我已經幫你寫好了完整的後端程式碼（Python Flask），它完美實現了「**非同步處理 (Asynchronous Processing)**」：
1. 收到 ManyChat 請求後，**1 秒內立即回應 `200 OK`**（解決 10 秒 Timeout 問題）。
2. 在背景執行緒（Background Thread）慢慢下載語音、呼叫 OpenAI Whisper 轉文字、呼叫 ChatGPT 生成答案。
3. 最後透過 ManyChat API 把答案發送給用戶。

接下來，你只需要將這包程式碼部署到 **Render.com（永久免費）**。

---

## 🛠️ 部署步驟

### 步驟 1：下載程式碼並上傳到 GitHub
1. 下載我附上的 `lpicture-voice-bot.zip` 檔案並解壓縮。
2. 登入你的 [GitHub 帳號](https://github.com/)。
3. 點擊右上角的 **+** 號，選擇 **New repository**。
4. 命名為 `lpicture-voice-bot`（設定為 Private 或 Public 都可以），點擊 **Create repository**。
5. 點擊 **"uploading an existing file"**，將解壓縮後的所有檔案（`app.py`, `requirements.txt`, `render.yaml` 等）拖曳上傳，然後點擊 **Commit changes**。

### 步驟 2：在 Render.com 部署
1. 註冊並登入 [Render.com](https://render.com/)（可以直接用 GitHub 登入）。
2. 點擊右上角的 **New**，選擇 **Web Service**。
3. 選擇 **Build and deploy from a Git repository**，點擊 Next。
4. 授權連接你的 GitHub 帳號，並選擇剛剛建立的 `lpicture-voice-bot` repository。
5. 進入設定頁面，Render 會自動讀取 `render.yaml`，大部分設定都會自動填好：
   - **Name**: `lpicture-voice-bot`
   - **Environment**: `Python 3`
   - **Instance Type**: 選擇 **Free**（免費版）
6. 捲動到下方的 **Environment Variables（環境變數）**，點擊 **Add Environment Variable**，加入以下兩個變數：
   - **KEY**: `OPENAI_API_KEY`
     - **VALUE**: `你的 OpenAI API 金鑰`（例如：sk-proj-...）
   - **KEY**: `MANYCHAT_API_TOKEN`
     - **VALUE**: `你的 ManyChat API Token`（格式為 `page_id:token`，請到 ManyChat Settings > API 中產生）
7. 點擊最下方的 **Create Web Service**。

### 步驟 3：等待部署並取得 Webhook URL
1. Render 會開始建立你的服務（大約需要 2-3 分鐘），你可以看到終端機日誌。
2. 當顯示 `Your service is live 🎉` 時，表示部署成功！
3. 在頁面左上方，你會看到一個網址（例如 `https://lpicture-voice-bot.onrender.com`）。
4. **你的 Webhook URL 就是**：`https://lpicture-voice-bot.onrender.com/webhook`

### 步驟 4：更新 ManyChat 設定
1. 回到 ManyChat 的 Default Reply 流程。
2. 點擊 **Actions** 步驟中的 **External Request**。
3. 將原本的測試 URL 替換為你的 Render Webhook URL：`https://lpicture-voice-bot.onrender.com/webhook`
4. 點擊 **Test Request** 確認顯示 200 OK，然後點擊 **Save**。
5. 發布（Publish）你的流程。

---

🎉 **大功告成！** 現在你的 Lpicture Voice Bot 已經具備了專業的非同步架構，再也不會遇到 ManyChat 的 10 秒超時問題了！
