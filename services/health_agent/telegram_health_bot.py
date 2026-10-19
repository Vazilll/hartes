import sys
import time
import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime

# Set encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

BOT_TOKEN = "8359669053:AAHhDlCn3v7nOdEzsDyH0yH7kLd32gMX4dc"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
DB_PATH = r"/home/tarhes/Проекты/vazus/services/memory/vazus.db"

def make_request(method, payload=None):
    url = API_URL + method
    if payload:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"API Error ({method}): {e}")
        return None

def send_message(chat_id, text):
    return make_request("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def save_health_report(chat_id, raw_text, photo_info=None):
    conn = sqlite3.connect(DB_PATH)
    now_str = datetime.now().isoformat()
    record_id = f"health_report_{int(time.time())}"
    
    desc = raw_text if raw_text else "Скриншот / Картинка отчета"
    props = {
        "raw_input": raw_text,
        "chat_id": chat_id,
        "timestamp": now_str,
        "photo_info": photo_info
    }
    
    conn.execute(
        "INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            record_id,
            f"Отчет о здоровье ({now_str[:10]})",
            "health",
            "observation",
            desc,
            "mi_band,telegram_bot,user_report",
            json.dumps(props, ensure_ascii=False)
        )
    )
    conn.commit()
    conn.close()

def process_message(msg):
    chat_id = msg['chat']['id']
    text = msg.get('text', '')
    caption = msg.get('caption', '')
    photo = msg.get('photo', None)
    
    input_content = text if text else caption
    photo_info = None

    if photo:
        # Get highest resolution photo file_id
        highest_photo = photo[-1]
        photo_info = {
            "file_id": highest_photo.get("file_id"),
            "width": highest_photo.get("width"),
            "height": highest_photo.get("height")
        }
        if not input_content:
            input_content = "[Скриншот экрана Mi Fitness]"

    if text and text.startswith('/start'):
        reply = (
            "🧠 **Vazus Health Gateway Active!**\n\n"
            "Я на связи для приема твоих отчетов с **Mi Band 10 / Mi Fitness**.\n\n"
            "📌 **Как отправлять данные:**\n"
            "• Присылай текст (например: *Сон 7ч 30м, глубокий 1ч 40м, пульс 58*).\n"
            "• Присылай скриншоты из Mi Fitness.\n\n"
            "Все данные сразу записываются в центральную базу памяти `vazus.db`!"
        )
        send_message(chat_id, reply)
        return

    # Save report to DB
    save_health_report(chat_id, input_content, photo_info)
    
    # Formulate analysis response
    reply = (
        "✅ **Данные приняты и сохранены в базу `vazus.db`!**\n\n"
        f"📝 **Получено:** {input_content}\n\n"
        "📊 **Напоминание по твоему стеку БАДов на сегодня:**\n"
        "• ☀️ **Утро:** D3+K2 Maxler (4 капс) + Бор NOW (3 капс) + Омега-3 + Цинк + Йод.\n"
        "• 🥤 **День:** Креатин Maxler (5г с водой).\n"
        "• 💤 **Вечер:** Ашваганда + Магний за 40 мин до сна."
    )
    send_message(chat_id, reply)

def main():
    print("Starting Telegram Health Bot Gateway (@vazilxbot)...")
    offset = 0
    while True:
        try:
            res = make_request("getUpdates", {"offset": offset, "timeout": 10})
            if res and res.get("ok"):
                for update in res.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        process_message(update["message"])
        except Exception as e:
            print(f"Error in polling loop: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
