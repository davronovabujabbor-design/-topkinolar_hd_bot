import telebot
from telebot import types
import sqlite3

API_TOKEN = '8696461606:AAFECW9WAc63ubvVhM93sOTWUnW45owkngU'
ADMIN_ID = 1260436370

bot = telebot.TeleBot(API_TOKEN)

# --- BAZA ---
conn = sqlite3.connect('movies.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, name TEXT, link TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, invite_link TEXT)''')
conn.commit()

# Boshlang'ich kanalingizni xatosiz tekshirib qo'shish
cursor.execute("SELECT * FROM channels WHERE channel_id = ?", ("-1004383556829",))
if not cursor.fetchone():
    cursor.execute("INSERT INTO channels (channel_id, invite_link) VALUES (?, ?)", 
                   ("-1004383556829", "https://t.me/+KUfXmD3NAHs4Zjgy"))
    conn.commit()

user_states = {}
admin_data = {}

def check_sub(user_id):
    cursor.execute("SELECT channel_id FROM channels")
    rows = cursor.fetchall()
    for row in rows:
        channel = row[0]
        try:
            member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

def sub_keyboard():
    markup = types.InlineKeyboardMarkup()
    cursor.execute("SELECT invite_link FROM channels")
    rows = cursor.fetchall()
    for idx, row in enumerate(rows, 1):
        link = row[1]
        markup.add(types.InlineKeyboardButton(f"📢 {idx}-kanalga obuna bo'lish", url=link))
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return markup

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Kino qidirish", "📊 Statistika")
    if user_id == ADMIN_ID:
        markup.row("➕ Kino qo'shish", "❌ Kino o'chirish")
        markup.row("📢 Kanal qo'shish", "🗑 Kanal o'chirish")
        markup.row("📜 Kanallar ro'yxati", "📤 Rassilka (Reklama)")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    
    if not check_sub(uid):
        bot.send_message(
            message.chat.id, 
            "⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**", 
            parse_mode="Markdown",
            reply_markup=sub_keyboard()
        )
        return

    msg = "Salom! Topkinolar HD botiga xush kelibsiz!\n\nKino kodini yuboring yoki quyidagi tugmalardan foydalaning:"
    bot.send_message(message.chat.id, msg, reply_markup=main_keyboard(uid))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    uid = call.from_user.id
    if check_sub(uid):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.", reply_markup=main_keyboard(uid))
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video'])
def handle_all(message):
    uid = message.from_user.id
    text = message.text

    if uid != ADMIN_ID and not check_sub(uid):
        bot.send_message(
            message.chat.id, 
            "⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**", 
            parse_mode="Markdown",
            reply_markup=sub_keyboard()
        )
        return

    if uid == ADMIN_ID:
        if text == "➕ Kino qo'shish":
            user_states[uid] = "WAITING_CODE"
            bot.send_message(message.chat.id, "Kino uchun KOD kiriting (masalan: 102):")
            return
        elif text == "❌ Kino o'chirish":
            user_states[uid] = "WAITING_DELETE_CODE"
            bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan kino KODini kiriting:")
            return
        elif text == "📢 Kanal qo'shish":
            user_states[uid] = "WAITING_CHANNEL_ID"
            bot.send_message(message.chat.id, "Kanal ID raqamini yoki Username'ini kiriting (masalan: `-1001234567890` yoki `@kanal_nomi`):")
            return
        elif text == "🗑 Kanal o'chirish":
            user_states[uid] = "WAITING_DELETE_CHANNEL"
            bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan kanal ID raqami yoki username'ini kiriting:")
            return
        elif text == "📜 Kanallar ro'yxati":
            cursor.execute("SELECT channel_id, invite_link FROM channels")
            rows = cursor.fetchall()
            if not rows:
                bot.send_message(message.chat.id, "Hozircha majburiy obuna kanallari yo'q.")
            else:
                res = "📜 **Majburiy obuna kanallari:**\n\n"
                for r in rows:
                    res += f"🔹 **ID/User:** `{r[0]}`\n🔗 **Link:** {r[1]}\n\n"
                bot.send_message(message.chat.id, res, parse_mode="Markdown")
            return
        elif text == "📤 Rassilka (Reklama)":
            user_states[uid] = "WAITING_BROADCAST"
            bot.send_message(message.chat.id, "Barcha foydalanuvchilarga yubormoqchi bo'lgan reklama postini (matn, rasm yoki video) yuboring:")
            return

    state = user_states.get(uid)

    if state == "WAITING_CODE":
        admin_data[uid] = {'code': text}
        user_states[uid] = "WAITING_NAME"
        bot.send_message(message.chat.id, "Kino NOMI ni kiriting (masalan: Avatar 2):")
        return

    elif state == "WAITING_NAME":
        admin_data[uid]['name'] = text
        user_states[uid] = "WAITING_LINK"
        bot.send_message(message.chat.id, "Kino HAVOLASI ni kiriting:")
        return

    elif state == "WAITING_LINK":
        admin_data[uid]['link'] = text
        code = admin_data[uid]['code']
        name = admin_data[uid]['name']
        link = admin_data[uid]['link']

        cursor.execute("INSERT OR REPLACE INTO movies (code, name, link) VALUES (?, ?, ?)", (code, name, link))
        conn.commit()

        user_states[uid] = None
        bot.send_message(message.chat.id, f"✅ Kino muvaffaqiyatli saqlandi!\n\nKod: {code}\nNomi: {name}\nHavola: {link}")
        return

    elif state == "WAITING_DELETE_CODE":
        cursor.execute("DELETE FROM movies WHERE code = ?", (text,))
        conn.commit()
        user_states[uid] = None
        bot.send_message(message.chat.id, f"🗑 `{text}` kodli kino bazadan o'chirildi.")
        return

    elif state == "WAITING_CHANNEL_ID":
        admin_data[uid] = {'channel_id': text}
        user_states[uid] = "WAITING_CHANNEL_LINK"
        bot.send_message(message.chat.id, "Kanalning TAKLIF HAVOLASI (linki)ni kiriting:")
        return

    elif state == "WAITING_CHANNEL_LINK":
        ch_id = admin_data[uid]['channel_id']
        ch_link = text
        cursor.execute("INSERT OR REPLACE INTO channels (channel_id, invite_link) VALUES (?, ?)", (ch_id, ch_link))
        conn.commit()
        user_states[uid] = None
        bot.send_message(message.chat.id, f"✅ Yangi kanal majburiy obunaga qo'shildi!\n\nID: `{ch_id}`\nLink: {ch_link}", parse_mode="Markdown")
        return

    elif state == "WAITING_DELETE_CHANNEL":
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (text,))
        conn.commit()
        user_states[uid] = None
        bot.send_message(message.chat.id, f"🗑 `{text}` kanali majburiy obunadan olib tashlandi.")
        return

    elif state == "WAITING_BROADCAST":
        user_states[uid] = None
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        count = 0
        bot.send_message(message.chat.id, "🚀 Rassilka boshlandi...")
        for u in all_users:
            try:
                bot.copy_message(chat_id=u[0], from_chat_id=message.chat.id, message_id=message.message_id)
                count += 1
            except Exception:
                pass
        bot.send_message(message.chat.id, f"✅ Reklama xabari {count} ta foydalanuvchiga muvaffaqiyatli yetkazildi!")
        return

    if text == "📊 Statistika":
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM movies")
        movie_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM channels")
        channel_count = cursor.fetchone()[0]
        bot.send_message(message.chat.id, f"📈 **Bot statistikasi:**\n\n👤 Foydalanuvchilar: {user_count} ta\n🎬 Kinolar soni: {movie_count} ta\n📢 Obuna kanallari: {channel_count} ta", parse_mode="Markdown")
        return

    elif text == "🔍 Kino qidirish":
        bot.send_message(message.chat.id, "Kino kodini yuboring (masalan: 101, 102...):")
        return

    cursor.execute("SELECT name, link FROM movies WHERE code = ?", (text,))
    movie = cursor.fetchone()

    if movie:
        name, link = movie
        caption = f"🎬 {name}\n\n📥 Yuklab olish havolasi: {link}"
        bot.send_message(message.chat.id, caption)
    else:
        bot.send_message(message.chat.id, f"Afsuski, `{text}` kodli kino topilmadi.")

bot.infinity_polling()
