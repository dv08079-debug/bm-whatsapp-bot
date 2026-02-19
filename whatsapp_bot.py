#!/usr/bin/env python3
"""
BalticMind AI WhatsApp Bot
Та же логика что и Telegram-бот, но через WATI + Flask
pip install flask anthropic requests gunicorn
"""

import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import anthropic

# ── НАСТРОЙКИ (читаются из переменных окружения Railway) ──
ANTHROPIC_KEY   = os.environ["ANTHROPIC_KEY"]       # sk-ant-...
WATI_API_URL    = os.environ["WATI_API_URL"]         # https://live-XXX.wati.io
WATI_API_TOKEN  = os.environ["WATI_API_TOKEN"]       # токен из WATI Settings → API
MANAGER_PHONE   = os.environ["MANAGER_PHONE"]        # номер менеджера без +

# ── СИСТЕМНЫЙ ПРОМПТ (тот же что в Telegram) ──
SYSTEM_PROMPT = """Ты — AI-ассистент компании BalticMind. 
Ты помогаешь клиентам узнать об услугах компании и записаться на консультацию.

О КОМПАНИИ:
- BalticMind — AI-автоматизация для бизнеса в Латвии, Эстонии и Литве
- Три направления: автоматизация бизнес-процессов, виртуальные ассистенты/чат-боты, консалтинг по цифровой трансформации
- Работаем на латышском, русском, английском, эстонском, литовском языках
- Пилотный проект запускаем за 4-6 недель
- Бесплатный экспресс-аудит для новых клиентов
- Сайт: balticmind.lv
- Email: hello@balticmind.lv

ЦЕНЫ (ориентировочно):
- Бесплатный аудит: 0€ (2 часа, без обязательств)
- Пилотный проект: от 4900€
- Масштабирование: по договорённости

ПРАВИЛА ОБЩЕНИЯ:
1. Определи язык клиента и отвечай на том же языке (LV/EN/RU)
2. Будь дружелюбным, профессиональным, кратким
3. Если клиент хочет записаться — спроси имя, компанию, email, удобное время
4. Если вопрос очень сложный или технический — скажи что передашь специалисту
5. Никогда не придумывай цены или факты которых не знаешь
6. Заканчивай разговор предложением записаться на бесплатный аудит

ВАЖНО: Ты представляешь реальную компанию. Будь точным и честным."""

# ── ХРАНИЛИЩЕ ДИАЛОГОВ (в памяти, как в Telegram-боте) ──
conversations = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


# ── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ──

def get_conversation(phone: str) -> list:
    """История диалога по номеру телефона"""
    if phone not in conversations:
        conversations[phone] = []
    return conversations[phone]


def add_message(phone: str, role: str, content: str):
    """Добавить сообщение в историю"""
    conv = get_conversation(phone)
    conv.append({"role": role, "content": content})
    if len(conv) > 20:
        conversations[phone] = conv[-20:]


def get_ai_response(phone: str, user_message: str) -> str:
    """Получить ответ от Claude — та же логика что в Telegram-боте"""
    add_message(phone, "user", user_message)
    try:
        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=get_conversation(phone)
        )
        ai_reply = response.content[0].text
        add_message(phone, "assistant", ai_reply)
        return ai_reply
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "Извините, техническая ошибка. Напишите нам: hello@balticmind.lv"


def send_whatsapp_message(phone: str, message: str):
    """Отправить сообщение через WATI"""
    url = f"{WATI_API_URL}/api/v1/sendSessionMessage/{phone}"
    headers = {
        "Authorization": f"Bearer {WATI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"messageText": message}
    try:
        r = requests.post(url, json=payload, headers=headers)
        r.raise_for_status()
        logger.info(f"Message sent to {phone}")
    except Exception as e:
        logger.error(f"WATI send error: {e}")


def notify_manager(phone: str, name: str, message: str):
    """Уведомить менеджера о горячем лиде"""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    text = (
        f"🔥 Горячий лид в WhatsApp!\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: +{phone}\n"
        f"💬 Сообщение: {message}\n"
        f"⏰ Время: {now}"
    )
    send_whatsapp_message(MANAGER_PHONE, text)


# ── WEBHOOK — сюда WATI шлёт входящие сообщения ──

@app.route("/whatsapp/webhook", methods=["POST"])
def webhook():
    data = request.json
    logger.info(f"Incoming: {data}")

    try:
        # Достаём данные из WATI webhook
        phone   = data.get("waId", "")           # номер клиента
        name    = data.get("senderName", "")      # имя клиента
        message = data.get("text", {}).get("body", "")  # текст сообщения

        if not phone or not message:
            return jsonify({"status": "ignored"}), 200

        # Приветствие при первом сообщении
        if phone not in conversations:
            greeting = (
                "👋 Sveiki / Hello / Здравствуйте!\n\n"
                "Я AI-ассистент компании *BalticMind* 🤖\n\n"
                "Помогу узнать об автоматизации бизнеса с помощью ИИ, "
                "расскажу об услугах и запишу на бесплатную консультацию.\n\n"
                "Пишите на латышском 🇱🇻, английском 🇬🇧 или русском 🇷🇺"
            )
            send_whatsapp_message(phone, greeting)

        # Горячие слова — уведомить менеджера
        hot_keywords = [
            'записаться', 'консультация', 'хочу', 'интересует', 'цена', 'стоимость',
            'appointment', 'interested', 'price', 'cost', 'contact',
            'pierakstīties', 'interesē', 'cena', 'vēlos'
        ]
        if any(kw in message.lower() for kw in hot_keywords):
            notify_manager(phone, name, message)

        # Получить ответ Claude и отправить клиенту
        reply = get_ai_response(phone, message)
        send_whatsapp_message(phone, reply)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "BalticMind WhatsApp Bot running ✅"}), 200


# ── ЗАПУСК ──

if __name__ == "__main__":
    print("🚀 BalticMind WhatsApp Bot запускается...")
    print(f"📡 Webhook URL: http://твой-сервер.com/whatsapp/webhook")
    print(f"🤖 Claude API: подключён")
    print("─" * 40)
    app.run(host="0.0.0.0", port=5000, debug=False)
