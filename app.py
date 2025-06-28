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

# 環境変数からLINE情報を取得
LINE_CHANNEL_SECRET = os.getenv("YOUR_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("YOUR_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 画像取得エラー時のデフォルト画像
DEFAULT_IMAGE_URL = "https://placehold.jp/600x400.png"

# === GIGAZINEなどの記事ページからog:imageを取得（IT・海外・ゲームなどで使用） ===
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

# === SUUMO用：summaryタグ内のimg要素から画像URLを抽出 ===
def extract_image_from_summary(summary):
    match = re.search(r'<img[^>]+src="([^"]+)"', summary)
    return match.group(1) if match else DEFAULT_IMAGE_URL

# === 各ニュースカード（バブル）共通生成 ===
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

def generate_real_estate_bubbles():
    bubbles = []
    
    # ① 不動産（SUUMO）
  　try:
        url = "https://suumo.jp/journal/feed/"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        cleaned = "\n".join(line for line in res.text.splitlines() if line.strip())
        feed = feedparser.parse(cleaned)
        suumo = [create_bubble(e.title, e.link, extract_image_from_summary(e.get("summary", ""))) for e in feed.entries[:5]]
        bubbles.extend(suumo)
     except Exception as e:
        print("SUUMO取得エラー:", e)

    # --- R.E.port ---
    try:
        url = "https://www.re-port.net/"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = soup.select(".newsList li")[:5]
        for a in articles:
            title = a.select_one("a").get_text(strip=True)
            link = "https://www.re-port.net" + a.select_one("a")["href"]
            bubbles.append(create_bubble(title, link, get_og_image(link)))
    except Exception as e:
        print("R.E.port取得エラー:", e)

    return bubbles

# ② IT（GIGAZINE）
def generate_it_news_bubbles():
    feed_url = "https://gigazine.net/news/rss_2.0/"
    feed = feedparser.parse(feed_url)
    return [create_bubble(e.title, e.link, get_og_image(e.link)) for e in feed.entries[:5]]

# ③ エンタメ（映画.com）
def generate_entertainment_bubbles():
    feed_url = "https://eiga.com/rss/news/"
    feed = feedparser.parse(feed_url)
    return [create_bubble(e.title, e.link, get_og_image(e.link)) for e in feed.entries[:5]]

# ④ 経済・ビジネス（日経ビジネス）
def generate_business_bubbles():
    feed_url = "https://toyokeizai.net/list/feed/rss"
    feed = feedparser.parse(feed_url)
    return [create_bubble(e.title, e.link, get_og_image(e.link)) for e in feed.entries[:5]]

# ⑤ 海外ニュース（NHK World 日本語）
def generate_world_news_bubbles():
    feed_url = "https://www3.nhk.or.jp/rss/news/cat0.xml"
    feed = feedparser.parse(feed_url)
    return [create_bubble(e.title, e.link, get_og_image(e.link)) for e in feed.entries[:5]]

# ⑥ ゲームニュース（4Gamer.net）
def generate_game_bubbles():
    feed_url = "https://www.4gamer.net/rss/index.xml"
    feed = feedparser.parse(feed_url)
    return [create_bubble(e.title, e.link, get_og_image(e.link)) for e in feed.entries[:5]]

# ⑦ 教育・学び（NHK for School）
def generate_education_bubbles():
    feed_url = "https://reseed.resemom.jp/rss/index.rdf"
    feed = feedparser.parse(feed_url)
    return [create_bubble(e.title, e.link, get_og_image(e.link)) for e in feed.entries[:5]]

# ジャンル選択Flexメッセージ
def send_genre_flex(user_id):
    def genre_bubble(title, label, data, icon, color):
        return {
            "type": "bubble",
            "hero": {
                "type": "image",
                "url": f"https://placehold.jp/600x400.png?text={icon}",
                "size": "full",
                "aspectMode": "cover",
                "aspectRatio": "1.51:1"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": title, "weight": "bold", "size": "lg"}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": color,
                        "action": {
                            "type": "postback",
                            "label": label,
                            "data": data
                        }
                    }
                ]
            }
        }

    bubbles = [
        genre_bubble("不動産ニュース", "不動産を見る", "genre=real_estate", "🏠", "#00B900"),
        genre_bubble("ITニュース", "ITを見る", "genre=it", "💻", "#0055FF"),
        genre_bubble("エンタメニュース", "エンタメを見る", "genre=entertainment", "🎬", "#FF4081"),
        genre_bubble("ビジネスニュース", "ビジネスを見る", "genre=business", "📈", "#FFA000"),
        genre_bubble("海外ニュース", "海外を見る", "genre=world", "🌍", "#7B1FA2"),
        genre_bubble("ゲームニュース", "ゲームを見る", "genre=game", "🎮", "#C2185B"),
        genre_bubble("教育・学び", "教育を見る", "genre=education", "📚", "#0288D1")
    ]

    carousel = {"type": "carousel", "contents": bubbles}

    line_bot_api.push_message(
        user_id,
        FlexSendMessage(alt_text="ジャンルを選んでください", contents=carousel)
    )

# Webhookエンドポイント
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

# ユーザーが何かメッセージを送ったとき → ジャンル選択Flexを送信
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    send_genre_flex(event.source.user_id)

# Postback処理：選ばれたジャンルに応じてFlexニュースを送信
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data

    if data == "genre=real_estate":
        bubbles = generate_real_estate_bubbles()
        alt = "🏠 不動産ニュースをお届け！"
    elif data == "genre=it":
        bubbles = generate_it_news_bubbles()
        alt = "💻 ITニュースをお届け！"
    elif data == "genre=entertainment":
        bubbles = generate_entertainment_bubbles()
        alt = "🎬 エンタメニュースをお届け！"
    elif data == "genre=business":
        bubbles = generate_business_bubbles()
        alt = "📈 ビジネスニュースをお届け！"
    elif data == "genre=world":
        bubbles = generate_world_news_bubbles()
        alt = "🌍 海外ニュースをお届け！"
    elif data == "genre=game":
        bubbles = generate_game_bubbles()
        alt = "🎮 ゲームニュースをお届け！"
    elif data == "genre=education":
        bubbles = generate_education_bubbles()
        alt = "📚 教育ニュースをお届け！"
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

# Renderでの稼働確認用エンドポイント（アクセスで "alive" を返す）
@app.route("/", methods=["GET"])
def healthcheck():
    return "Bot is alive", 200

# アプリを起動（Render用）
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
