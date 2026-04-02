import logging
import os
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# =============================================
# SOZLAMALAR
# =============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set!")

# Admin Telegram ID lari (botdan barcha xabarlarni ko'rish uchun)
# O'z Telegram ID ingizni bilish uchun @userinfobot ga /start yozing
ADMIN_IDS = [123456789, 987654321]  # Admin ID larini shu yerga kiriting

# Klinika ma'lumotlari — shu yerni o'zgartiring
KLINIKA_INFO = """
KLINIKA NOMI: MedLife Klinikasi
MANZIL: Toshkent sh., Chilonzor tumani, 7-kvartal, 12-uy
ISH VAQTI: Dushanba-Shanba: 08:00 - 20:00 | Yakshanba: 09:00 - 15:00
TELEFON: +998 71 123-45-67
WEBSITE: www.medlife.uz

XIZMATLAR VA NARXLAR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
👨‍⚕️ KONSULTATSIYALAR:
• Terapevt — 80,000 so'm
• Kardiolog — 120,000 so'm
• Nevropatolog — 120,000 so'm
• Gastroenterolog — 120,000 so'm
• Endokrinolog — 130,000 so'm
• Ginekolog — 130,000 so'm
• Urolog — 130,000 so'm
• Oftalmolog (ko'z shifokori) — 100,000 so'm
• Dermatolog — 100,000 so'm
• Ortoped — 120,000 so'm

🔬 LABORATORIYA TAHLILLARI:
• Umumiy qon tahlili — 35,000 so'm
• Qon kimyosi (to'liq) — 120,000 so'm
• Qand (shakar) tahlili — 25,000 so'm
• Siydik tahlili — 25,000 so'm
• Gormonlar tahlili — 60,000-150,000 so'm
• COVID-19 PCR — 150,000 so'm

🏥 DIAGNOSTIKA:
• UZI (ultratovush) — 80,000-150,000 so'm
• EKG — 60,000 so'm
• Rentgen — 80,000 so'm
• FGDS (gastroskopiya) — 250,000 so'm

💉 PROTSEDURALAR:
• Dropper (kapelnitsa) — 50,000 so'm
• Ukol (in'eksiya) — 25,000 so'm
• Jarrohlik kichik — 100,000 so'm dan

TEZKOR KO'MAK: +998 90 123-45-67 (24/7)

MUHIM ESLATMA: Narxlar taxminiy. Aniq narx shifokor ko'rigidan keyin belgilanadi.
"""

FAQ = """
TEZKOR SAVOL-JAVOBLAR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q: Qabulga oldindan yozish kerakmi?
A: Ha, tavsiya etiladi. Bot orqali yoki +998 71 123-45-67 ga qo'ng'iroq qilib yozilsa bo'ladi.

Q: Sug'urta qabul qilinadi?
A: Ha, asosiy sug'urta kompaniyalari bilan ishlaymiz. Batafsil qo'ng'iroq qiling.

Q: Uy ga chiqib ko'rish xizmati bormi?
A: Ha, shahar ichida. Narx: 200,000 so'mdan. +998 90 123-45-67.

Q: Naqd puldan boshqa to'lov usullari?
A: Payme, Click, Uzcard, Visa/MasterCard qabul qilinadi.

Q: Natijalar qachon tayyor bo'ladi?
A: Tahlillar: 1-3 soat ichida. UZI: darhol. Rentgen: 30 daqiqa ichida.
"""
# =============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

openai_client = Groq(api_key=GROQ_API_KEY)
conversation_history = {}

SYSTEM_PROMPT = f"""Siz MedLife Klinikasining professional AI assistantsiz.

VAZIFANGIZ:
1. Bemorlar va mijozlarga yordam berish
2. Klinika xizmatlari haqida ma'lumot berish
3. Qabulga yozish uchun ma'lumot to'plash
4. Savollarga aniq, samimiy javob berish

KLINIKA MA'LUMOTLARI:
{KLINIKA_INFO}

{FAQ}

QOIDALAR:
- Foydalanuvchi qaysi tilda yozsa (O'zbek, Rus, Ingliz), o'sha tilda javob bering
- Doimo xushmuomala va professional bo'ling
- Tibbiy tashxis qo'ymang — doktor ko'rigiga yo'llang
- Qabulga yozmoqchi bo'lsa: Ism, telefon, kerakli shifokor va qulay vaqtni so'rang
- Javoblar aniq va qisqa bo'lsin
- Emoji lardan o'rinli foydalaning
- Bemor og'riq yoki muammo aytsa — AVVAL hamdardlik bildiring: "Tushunaman", "Kechirasiz", "Xavotir olmang" kabi so'zlar ishlating
- HECH QACHON "Qoyil!", "Zo'r!", "Ajoyib!" kabi maqtov so'zlarni ishlatmang — bu tibbiy muassasa uchun nomuvofiq
- Og'riq, kasallik, shikoyat kabi hollarda jiddiy va g'amxo'r ohangda gapiring

QABUL YOZISH JARAYONI:
Bemor qabulga yozmoqchi bo'lsa:
1. Ism familiyasini so'rang
2. Telefon raqamini so'rang
3. Qaysi shifokorga borishini so'rang
4. Qulay kun va vaqtni so'rang
5. Ma'lumotlarni tasdiqlang va "Tez orada administrator siz bilan bog'lanadi" de
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


async def notify_admins(bot, user, message_text, reply_text):
    """Adminlarga xabar yuborish"""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    admin_message = (
        f"🔔 Yangi xabar | {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Foydalanuvchi: {user.first_name} {user.last_name or ''}\n"
        f"🆔 ID: {user.id}\n"
        f"📱 Username: @{user.username or 'yoq'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Xabar: {message_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot javobi: {reply_text[:300] + ('...' if len(reply_text) > 300 else '')}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_message)
        except Exception as e:
            logger.error(f"Admin ga xabar yuborishda xatolik: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    conversation_history[user_id] = []

    await update.message.reply_text(
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "🏥 MedLife Klinikasiga xush kelibsiz!\n\n"
        "Men sizga klinikamiz xizmatlari, narxlar, ish vaqti haqida ma'lumot bera olaman "
        "va qabulga yozishda yordam beraman.\n\n"
        "Quyidagi bo'limlardan birini tanlang yoki savolingizni yozing:",
        reply_markup=get_main_menu()
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    responses = {
        "prices": (
            "👨‍⚕️ SHIFOKORLAR VA KONSULTATSIYA NARXLARI:\n\n"
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
            "🚨 Tezkor yordam: +998 90 123-45-67\n"
            "☎️ Qo'ng'iroq: +998 71 123-45-67"
        ),
        "location": (
            "📍 BIZNING MANZILIMIZ:\n\n"
            "Toshkent sh., Chilonzor tumani\n"
            "7-kvartal, 12-uy\n\n"
            "🚇 Metro: Chilonzor (5 daqiqa)\n"
            "🚌 Avtobus: 11, 23, 45\n\n"
            "🗺 Google Maps: maps.google.com/medlife"
        ),
        "lab": (
            "🔬 LABORATORIYA XIZMATLARI:\n\n"
            "• Umumiy qon tahlili — 35,000 so'm\n"
            "• Qon kimyosi (to'liq) — 120,000 so'm\n"
            "• Qand tahlili — 25,000 so'm\n"
            "• Siydik tahlili — 25,000 so'm\n"
            "• Gormonlar — 60,000-150,000 so'm\n\n"
            "🏥 DIAGNOSTIKA:\n"
            "• UZI — 80,000-150,000 so'm\n"
            "• EKG — 60,000 so'm\n"
            "• Rentgen — 80,000 so'm\n\n"
            "⏱ Natijalar: 1-3 soat ichida"
        ),
        "appointment": (
            "📅 QABULGA YOZILISH\n\n"
            "Qabulga yozilish uchun menga quyidagilarni yozing:\n\n"
            "1️⃣ Ism familiyangiz\n"
            "2️⃣ Telefon raqamingiz\n"
            "3️⃣ Qaysi shifokorga bormoqchisiz\n"
            "4️⃣ Qulay kun va vaqt\n\n"
            "Yoki to'g'ridan-to'g'ri yozing, men yordam beraman! 😊"
        ),
        "question": (
            "❓ Savolingizni yozing, men javob beraman!\n\n"
            "Klinika, xizmatlar, narxlar yoki boshqa mavzularda "
            "istalgan savolni berishingiz mumkin."
        ),
    }

    text = responses.get(query.data, "Iltimos, menyudan tanlang.")
    await query.edit_message_text(text=text, reply_markup=get_main_menu())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_text = update.message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    conversation_history[user_id].append({"role": "user", "content": user_text})

    if len(conversation_history[user_id]) > 30:
        conversation_history[user_id] = conversation_history[user_id][-30:]

    try:
        response = openai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[user_id],
        )
        reply = response.choices[0].message.content

        conversation_history[user_id].append({"role": "assistant", "content": reply})

        await update.message.reply_text(reply, reply_markup=get_main_menu())

        # Adminlarga xabar yuborish
        await notify_admins(context.bot, user, user_text, reply)

    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await update.message.reply_text(
            "⚠️ Kechirasiz, texnik xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring yoki qo'ng'iroq qiling:\n"
            "📞 +998 71 123-45-67"
        )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faqat adminlar uchun statistika"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    total_users = len(conversation_history)
    await update.message.reply_text(
        f"📊 STATISTIKA\n\n"
        f"👥 Faol foydalanuvchilar: {total_users}\n"
        f"🕐 Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
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