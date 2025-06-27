import os
import threading
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import PostbackEvent, MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# === 環境変数からアクセストークンとシークレットを取得 ===
line_bot_api = LineBotApi(os.getenv("YOUR_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("YOUR_CHANNEL_SECRET"))

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    # === 非同期でイベント処理 ===
    def handle_event():
        try:
            handler.handle(body, signature)
        except InvalidSignatureError as e:
            print("署名エラー:", e)

    threading.Thread(target=handle_event).start()

    return "OK", 200

# === 例：ジャンル選択ボタンのPostback処理 ===
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data == "genre=real_estate":
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text="🏠 不動産ニュースをお送りします！")
        )
    elif data == "genre=it":
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text="💻 ITニュースをお届けします！")
        )
    else:
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text="⚠️ 不明なジャンルが選択されました")
        )

# === 動作確認用エンドポイント（オプション）===
@app.route("/", methods=["GET"])
def healthcheck():
    return "Bot is alive", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
