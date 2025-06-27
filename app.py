from flask import Flask, request # type: ignore
from linebot import LineBotApi, WebhookHandler # type: ignore
from linebot.exceptions import InvalidSignatureError # type: ignore
from linebot.models import TextMessage, MessageEvent, TextSendMessage # type: ignore

app = Flask(__name__)

line_bot_api = LineBotApi("YOUR_CHANNEL_ACCESS_TOKEN")
handler = WebhookHandler("YOUR_CHANNEL_SECRET")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="こんにちは！"))

if __name__ == "__main__":
    app.run()
