import telebot
from telebot import types
import sqlite3

API_TOKEN = '8696461606:AAFECW9WAc63ubvVhM93sOTWUnW45owkngU'
ADMIN_ID = 1260436370

bot = telebot.TeleBot(API_TOKEN)

# --- MA'LUMOTLAR BAZASI (SQLite) ---
conn = sqlite3.connect('movies.db', check_same_thread=False)
cursor = conn.cursor()

# Jadvallarni yaratish
cursor.execute('''
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    name TEXT,
    link TEXT
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
''')
conn.commit()

# Vaqtinchalik xotira
user_states = {}
admin_data = {}

# --- MENU TUGMALARI ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Kino qidirish", "📊 Statistika")
    if user_id == ADMIN_ID:
        markup.row("➕ Kino qo'shish", "❌ Kino o'chirish")
    return markup

# --- HANDLERLAR ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    
    # Foydalanuvchini bazaga qo'shish
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    
    msg = "Salom! Topkinolar HD botiga xush kelibsiz!\n\nKino kodini yuboring yoki quyidagi tugmalardan foydalaning:"
    bot.send_message(message.chat.id, msg, reply_markup=main_keyboard(uid))

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    uid = message.from_user.id
    text = message.text

    # --- ADMIN FUNKSIYALARI ---
    if uid == ADMIN_ID:
        if text == "➕ Kino qo'shish":
            user_states[uid] = "WAITING_CODE"
            bot.send_message(message.chat.id, "Kino uchun **KOD** kiriting (masalan: 102):")
            return
        elif text == "❌ Kino o'chirish":
            user_states[uid] = "WAITING_DELETE_CODE"
            bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan kino KODini kiriting:")
            return

    # --- ADMIN QADAM-BA-QADAM KINO QO'SHISHI ---
    state = user_states.get(uid)

    if state == "WAITING_CODE":
        admin_data[uid] = {'code': text}
        user_states[uid] = "WAITING_NAME"
        bot.send_message(message.chat.id, "Kino **NOMI**ni kiriting (masalan: Avatar 2):")
        return

    elif state == "WAITING_NAME":
        admin_data[uid]['name'] = text
        user_states[uid] = "WAITING_LINK"
        bot.send_message(message.chat.id, "Kino **HAVOLASI** (link yoki t.me/...)ni kiriting:")
        return

    elif state == "WAITING_LINK":
        admin_data[uid]['link'] = text
        code = admin_data[uid]['code']
        name = admin_data[uid]['name']
        link = admin_data[uid]['link']

        # Bazaga saqlash
        cursor.execute("INSERT OR REPLACE INTO movies (code, name, link) VALUES (?, ?, ?)", (code, name, link))
        conn.commit()

        user_states[uid] = None
        bot.send_message(message.chat.id, f"✅ **Kino muvaffaqiyatli saqlandi!**\n\nKod: {code}\nNomi: {name}\nHavola: {link}")
        return

    elif state == "WAITING_DELETE_CODE":
        cursor.execute("DELETE FROM movies WHERE code = ?", (text,))
        conn.commit()
        user_states[uid] = None
        bot.send_message(message.chat.id, f"🗑 `{text}` kodli kino bazadan o'chirildi.")
        return

    # --- UMUMIY TUGMALAR ---
    if text == "📊 Statistika":
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM movies")
        movie_count = cursor.fetchone()[0]
        bot.send_message(message.chat.id, f"📈 **Bot statistikasi:**\n\n👤 Foydalanuvchilar: {user_count} ta\n🎬 Kinolar soni: {movie_count} ta")
        return

    elif text == "🔍 Kino qidirish":
        bot.send_message(message.chat.id, "Kino kodini yuboring (masalan: 101, 102...):")
        return

    # --- KINO QIDIRISH (KOD BO'YICHA) ---
    cursor.execute("SELECT name, link FROM movies WHERE code = ?", (text,))
    movie = cursor.fetchone()

    if movie:
        name, link = movie
        caption = f"🎬 **{name}**\n\n📥 Yuklab olish havolasi: {link}"
        bot.send_message(message.chat.id, caption)
    else:
        bot.send_message(message.chat.id, f"Afsuski, `{text}` kodli kino topilmadi.")

bot.infinity_polling()
