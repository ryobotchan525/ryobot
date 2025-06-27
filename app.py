import os
import threading
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    PostbackEvent, MessageEvent, TextMessage, TextSendMessage,
    PostbackAction, FlexSendMessage
)

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.getenv("YOUR_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("YOUR_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

DEFAULT_IMAGE_URL = "https://placehold.jp/600x400.png"

# GIGAZINE: 記事ページから og:image を取得
def get_og_image(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        tag = soup.find("meta", property="og:image")
        return tag["content"] if tag else DEFAULT_IMAGE_URL
    except:
        return DEFAULT_IMAGE_URL

# SUUMO: summaryタグ内から画像抽出
def extract_image_from_summary(summary):
    match = re.search(r'<img[^>]+src="([^"]+)"', summary)
    return match.group(1) if match else DEFAULT_IMAGE_URL

# Flexバブル生成（共通）
def create_bubble(title, link, image_url):
    return {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": image_url,
            "size": "full",
            "aspectMode": "cover",
            "aspectRatio": "20:13"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "wrap": True,
                    "size": "md"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "続きを読む",
                        "uri": link
                    },
                    "style": "link"
                }
            ]
        }
    }

# SUUMO 不動産ニュース
def generate_real_estate_bubbles():
    url = "https://suumo.jp/journal/feed/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        cleaned = "\n".join(line for line in res.text.splitlines() if line.strip())
        feed = feedparser.parse(cleaned)
    except Exception as e:
        print("SUUMO取得エラー:", e)
        return []

    bubbles = []
    for entry in feed.entries[:5]:
        title = entry.title.strip()
        link = entry.link
        summary = entry.get("summary", "")
        image_url = extract_image_from_summary(summary)
        bubbles.append(create_bubble(title, link, image_url))
    return bubbles

# GIGAZINE ITニュース
def generate_it_news_bubbles():
    feed_url = "https://gigazine.net/news/rss_2.0/"
    feed = feedparser.parse(feed_url)
    bubbles = []
    for entry in feed.entries[:5]:
        title = entry.title
        link = entry.link
        image_url = get_og_image(link)
        bubbles.append(create_bubble(title, link, image_url))
    return bubbles

# Flexでジャンル選択を送信
def send_genre_flex(user_id):
    bubble_real_estate = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": "https://placehold.jp/600x400.png?text=🏠",
            "size": "full",
            "aspectMode": "cover",
            "aspectRatio": "1.51:1"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "不動産ニュース", "weight": "bold", "size": "lg"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#00B900",
                    "action": {
                        "type": "postback",
                        "label": "不動産を見る",
                        "data": "genre=real_estate"
                    }
                }
            ]
        }
    }

    bubble_it = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": "https://placehold.jp/600x400.png?text=💻",
            "size": "full",
            "aspectMode": "cover",
            "aspectRatio": "1.51:1"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "ITニュース", "weight": "bold", "size": "lg"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#0055FF",
                    "action": {
                        "type": "postback",
                        "label": "ITを見る",
                        "data": "genre=it"
                    }
                }
            ]
        }
    }

    carousel = {"type": "carousel", "contents": [bubble_real_estate, bubble_it]}
    line_bot_api.push_message(
        user_id,
        FlexSendMessage(alt_text="ジャンルを選んでください", contents=carousel)
    )

# Webhook
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    def process():
        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            print("Invalid signature")

    threading.Thread(target=process).start()
    return "OK", 200

# テキスト送信 → Flexジャンル選択を表示
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    send_genre_flex(event.source.user_id)

# Postback → Flexでニュース配信
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data

    if data == "genre=it":
        bubbles = generate_it_news_bubbles()
        alt = "💻 ITニュースをお届け！"
    elif data == "genre=real_estate":
        bubbles = generate_real_estate_bubbles()
        alt = "🏠 不動産ニュースをお届け！"
    else:
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text="⚠️ 不明なジャンルが選択されました")
        )
        return

    if not bubbles:
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text="⚠️ ニュースが取得できませんでした。")
        )
        return

    carousel = {"type": "carousel", "contents": bubbles}
    line_bot_api.push_message(
        event.source.user_id,
        FlexSendMessage(alt_text=alt, contents=carousel)
    )

# Render用の簡易チェック
@app.route("/", methods=["GET"])
def healthcheck():
    return "Bot is alive", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
