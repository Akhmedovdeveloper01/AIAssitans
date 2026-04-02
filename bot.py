import logging
import os
import httpx
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

load_dotenv()

# =============================================
# SOZLAMALAR
# =============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
API_URL = os.getenv("API_URL", "http://localhost:8000")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set!")

KLINIKA_INFO = """
KLINIKA NOMI: MedLife Klinikasi
MANZIL: Toshkent sh., Chilonzor tumani, 7-kvartal, 12-uy
ISH VAQTI: Dushanba-Shanba: 08:00 - 20:00 | Yakshanba: 09:00 - 15:00
TELEFON: +998 71 123-45-67
WEBSITE: www.medlife.uz

XIZMATLAR VA NARXLAR:
👨‍⚕️ KONSULTATSIYALAR:
• Terapevt — 80,000 so'm
• Kardiolog — 120,000 so'm
• Nevropatolog — 120,000 so'm
• Gastroenterolog — 120,000 so'm
• Endokrinolog — 130,000 so'm
• Ginekolog — 130,000 so'm
• Urolog — 130,000 so'm
• Oftalmolog — 100,000 so'm
• Dermatolog — 100,000 so'm
• Ortoped — 120,000 so'm

🔬 LABORATORIYA TAHLILLARI:
• Umumiy qon tahlili — 35,000 so'm
• Qon kimyosi — 120,000 so'm
• Qand tahlili — 25,000 so'm
• Siydik tahlili — 25,000 so'm
• Gormonlar — 60,000-150,000 so'm

🏥 DIAGNOSTIKA:
• UZI — 80,000-150,000 so'm
• EKG — 60,000 so'm
• Rentgen — 80,000 so'm

TEZKOR KO'MAK: +998 90 123-45-67 (24/7)
"""

FAQ = """
TEZKOR SAVOL-JAVOBLAR:
Q: Qabulga oldindan yozish kerakmi?
A: Ha, tavsiya etiladi.

Q: To'lov usullari?
A: Payme, Click, Uzcard, Visa/MasterCard qabul qilinadi.

Q: Natijalar qachon tayyor?
A: Tahlillar: 1-3 soat. UZI: darhol. Rentgen: 30 daqiqa.
"""

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

groq_client = Groq(api_key=GROQ_API_KEY)
conversation_history = {}

SYSTEM_PROMPT = f"""Siz MedLife Klinikasining professional AI assistantsiz.

KLINIKA MA'LUMOTLARI:
{KLINIKA_INFO}

{FAQ}

QOIDALAR:
- Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob bering
- Doimo xushmuomala va professional bo'ling
- Tibbiy tashxis qo'ymang
- Bemor og'riq aytsa hamdardlik bildiring
- HECH QACHON "Qoyil!", "Zo'r!" kabi so'zlar ishlatmang
- Qabulga yozmoqchi bo'lsa: Ism, telefon, shifokor, vaqtni so'rang
"""


def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("👨‍⚕️ Shifokorlar va narxlar", callback_data="prices"),
            InlineKeyboardButton("📅 Qabulga yozilish", callback_data="appointment"),
        ],
        [
            InlineKeyboardButton("🕐 Ish vaqti", callback_data="hours"),
            InlineKeyboardButton("📍 Manzil", callback_data="location"),
        ],
        [
            InlineKeyboardButton("🔬 Tahlillar", callback_data="lab"),
            InlineKeyboardButton("❓ Savol berish", callback_data="question"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def save_to_backend(user, user_text, reply):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            base = {
                "telegram_id": str(user.id),
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
            }
            await client.post(f"{API_URL}/bot/message", json={**base, "role": "user", "content": user_text})
            await client.post(f"{API_URL}/bot/message", json={**base, "role": "bot", "content": reply})
            logger.info(f"Backend ga saqlandi: {user.first_name}")
    except Exception as e:
        logger.warning(f"Backend ga saqlashda xatolik: {e}")


async def notify_admins(bot, user, message_text, reply_text):
    if not ADMIN_IDS:
        return
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    text = (
        f"🔔 Yangi xabar | {now}\n"
        f"👤 {user.first_name} {user.last_name or ''}\n"
        f"🆔 ID: {user.id}\n"
        f"📱 @{user.username or 'yoq'}\n"
        f"💬 {message_text}\n"
        f"🤖 {reply_text[:300] + ('...' if len(reply_text) > 300 else '')}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            logger.error(f"Admin ga xabar yuborishda xatolik: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_history[user.id] = []
    await update.message.reply_text(
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "🏥 MedLife Klinikasiga xush kelibsiz!\n\n"
        "Quyidagi bo'limlardan birini tanlang yoki savolingizni yozing:",
        reply_markup=get_main_menu()
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    responses = {
        "prices": (
            "👨‍⚕️ SHIFOKORLAR VA NARXLAR:\n\n"
            "• Terapevt — 80,000 so'm\n"
            "• Kardiolog — 120,000 so'm\n"
            "• Nevropatolog — 120,000 so'm\n"
            "• Gastroenterolog — 120,000 so'm\n"
            "• Endokrinolog — 130,000 so'm\n"
            "• Ginekolog — 130,000 so'm\n"
            "• Urolog — 130,000 so'm\n"
            "• Oftalmolog — 100,000 so'm\n"
            "• Dermatolog — 100,000 so'm\n\n"
            "📌 Qabulga yozilish uchun '📅 Qabulga yozilish' tugmasini bosing"
        ),
        "hours": (
            "🕐 ISH VAQTIMIZ:\n\n"
            "📅 Dushanba — Shanba: 08:00 - 20:00\n"
            "📅 Yakshanba: 09:00 - 15:00\n\n"
            "🚨 Tezkor: +998 90 123-45-67\n"
            "☎️ Qo'ng'iroq: +998 71 123-45-67"
        ),
        "location": (
            "📍 MANZILIMIZ:\n\n"
            "Toshkent sh., Chilonzor tumani\n"
            "7-kvartal, 12-uy\n\n"
            "🚇 Metro: Chilonzor (5 daqiqa)"
        ),
        "lab": (
            "🔬 LABORATORIYA:\n\n"
            "• Umumiy qon tahlili — 35,000 so'm\n"
            "• Qon kimyosi — 120,000 so'm\n"
            "• Qand tahlili — 25,000 so'm\n"
            "• Siydik tahlili — 25,000 so'm\n"
            "• UZI — 80,000-150,000 so'm\n"
            "• EKG — 60,000 so'm\n"
            "• Rentgen — 80,000 so'm\n\n"
            "⏱ Natijalar: 1-3 soat ichida"
        ),
        "appointment": (
            "📅 QABULGA YOZILISH\n\n"
            "Quyidagilarni yozing:\n\n"
            "1️⃣ Ism familiyangiz\n"
            "2️⃣ Telefon raqamingiz\n"
            "3️⃣ Qaysi shifokorga\n"
            "4️⃣ Qulay kun va vaqt"
        ),
        "question": "❓ Savolingizni yozing, javob beraman!",
    }

    text = responses.get(query.data, "Iltimos, menyudan tanlang.")
    await query.edit_message_text(text=text, reply_markup=get_main_menu())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_text = update.message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    conversation_history[user_id].append({"role": "user", "content": user_text})

    if len(conversation_history[user_id]) > 30:
        conversation_history[user_id] = conversation_history[user_id][-30:]

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[user_id],
        )
        reply = response.choices[0].message.content
        conversation_history[user_id].append({"role": "assistant", "content": reply})

        await update.message.reply_text(reply, reply_markup=get_main_menu())

        await save_to_backend(user, user_text, reply)
        await notify_admins(context.bot, user, user_text, reply)

    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await update.message.reply_text(
            "⚠️ Kechirasiz, xatolik yuz berdi.\n"
            "📞 +998 71 123-45-67"
        )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    await update.message.reply_text(
        f"📊 STATISTIKA\n\n"
        f"👥 Faol foydalanuvchilar: {len(conversation_history)}\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )


def main():
    print("🏥 MedLife Bot ishga tushmoqda...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()