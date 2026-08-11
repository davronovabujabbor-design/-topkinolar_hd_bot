import telebot
from telebot import types
import sqlite3
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- SERVERNI TIRIK USHLASH UCHUN ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# --- BOT VA BAZA ---
API_TOKEN = '8696461606:AAFECW9WAc63ubvVhM93sOTWUnW45owkngU'
ADMIN_ID = 1260436370

bot = telebot.TeleBot(API_TOKEN, threaded=True)

def get_db():
    conn = sqlite3.connect('movies.db', timeout=10)
    return conn, conn.cursor()

# Bazani boshlang'ich sozlash
conn, cursor = get_db()
cursor.execute('''CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, name TEXT, link TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, invite_link TEXT)''')
cursor.execute("SELECT * FROM channels WHERE channel_id = ?", ("-1004383556829",))
if not cursor.fetchone():
    cursor.execute("INSERT INTO channels (channel_id, invite_link) VALUES (?, ?)", 
                   ("-1004383556829", "https://t.me/+KUfXmD3NAHs4Zjgy"))
conn.commit()
conn.close()

user_states = {}
admin_data = {}

# --- KANALGA TUSHGAN ZAYAVKALARNI AVTOMATIK QABUL QILISH ---
@bot.chat_join_request_handler()
def auto_approve(chat_join_request):
    try:
        # Zayavkani tasdiqlaydi
        bot.approve_chat_join_request(chat_join_request.chat.id, chat_join_request.from_user.id)
        
        # Foydalanuvchini bazaga kiritib qo'yadi
        conn, cursor = get_db()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (chat_join_request.from_user.id,))
        conn.commit()
        conn.close()
    except Exception:
        pass

def check_sub(user_id):
    conn, cursor = get_db()
    cursor.execute("SELECT channel_id FROM channels")
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        try:
            member = bot.get_chat_member(chat_id=row[0], user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True

def sub_keyboard():
    markup = types.InlineKeyboardMarkup()
    conn, cursor = get_db()
    cursor.execute("SELECT invite_link FROM channels")
    rows = cursor.fetchall()
    conn.close()
    
    for idx, row in enumerate(rows, 1):
        markup.add(types.InlineKeyboardButton(f"📢 {idx}-kanalga obuna bo'lish", url=row[0]))
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
    try:
        conn, cursor = get_db()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        conn.close()
    except Exception:
        pass

    if not check_sub(uid):
        bot.send_message(message.chat.id, "⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**", parse_mode="Markdown", reply_markup=sub_keyboard())
        return

    bot.send_message(message.chat.id, "Salom! Topkinolar HD botiga xush kelibsiz!\n\nKino kodini yuboring:", reply_markup=main_keyboard(uid))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    uid = call.from_user.id
    if check_sub(uid):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, "✅ Obuna tasdiqlandi!", reply_markup=main_keyboard(uid))
    else:
        bot.answer_callback_query(call.id, "❌ Barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video'])
def handle_all(message):
    uid = message.from_user.id
    text = message.text

    if uid != ADMIN_ID and not check_sub(uid):
        bot.send_message(message.chat.id, "⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**", parse_mode="Markdown", reply_markup=sub_keyboard())
        return

    if uid == ADMIN_ID:
        if text == "➕ Kino qo'shish":
            user_states[uid] = "WAITING_CODE"
            bot.send_message(message.chat.id, "Kino KODini kiriting:")
            return
        elif text == "❌ Kino o'chirish":
            user_states[uid] = "WAITING_DELETE_CODE"
            bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan kino KODini kiriting:")
            return
        elif text == "📢 Kanal qo'shish":
            user_states[uid] = "WAITING_CHANNEL_ID"
            bot.send_message(message.chat.id, "Kanal ID raqami yoki Username kiriting:")
            return
        elif text == "🗑 Kanal o'chirish":
            user_states[uid] = "WAITING_DELETE_CHANNEL"
            bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan kanal ID'sini kiriting:")
            return
        elif text == "📜 Kanallar ro'yxati":
            conn, cursor = get_db()
            cursor.execute("SELECT channel_id, invite_link FROM channels")
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                bot.send_message(message.chat.id, "Kanallar yo'q.")
            else:
                res = "📜 **Kanallar:**\n\n" + "\n".join([f"🔹 `{r[0]}`: {r[1]}" for r in rows])
                bot.send_message(message.chat.id, res, parse_mode="Markdown")
            return
        elif text == "📤 Rassilka (Reklama)":
            user_states[uid] = "WAITING_BROADCAST"
            bot.send_message(message.chat.id, "Reklama postini yuboring:")
            return

    state = user_states.get(uid)

    if state == "WAITING_CODE":
        admin_data[uid] = {'code': text}
        user_states[uid] = "WAITING_NAME"
        bot.send_message(message.chat.id, "Kino NOMIni kiriting:")
        return

    elif state == "WAITING_NAME":
        admin_data[uid]['name'] = text
        user_states[uid] = "WAITING_LINK"
        bot.send_message(message.chat.id, "Kino HAVOLASI (linki)ni kiriting:")
        return

    elif state == "WAITING_LINK":
        conn, cursor = get_db()
        cursor.execute("INSERT OR REPLACE INTO movies (code, name, link) VALUES (?, ?, ?)", (admin_data[uid]['code'], admin_data[uid]['name'], text))
        conn.commit()
        conn.close()
        user_states[uid] = None
        bot.send_message(message.chat.id, "✅ Kino saqlandi!")
        return

    elif state == "WAITING_DELETE_CODE":
        conn, cursor = get_db()
        cursor.execute("DELETE FROM movies WHERE code = ?", (text,))
        conn.commit()
        conn.close()
        user_states[uid] = None
        bot.send_message(message.chat.id, f"🗑 `{text}` o'chirildi.")
        return

    elif state == "WAITING_CHANNEL_ID":
        admin_data[uid] = {'channel_id': text}
        user_states[uid] = "WAITING_CHANNEL_LINK"
        bot.send_message(message.chat.id, "Kanal LINKini kiriting:")
        return

    elif state == "WAITING_CHANNEL_LINK":
        conn, cursor = get_db()
        cursor.execute("INSERT OR REPLACE INTO channels (channel_id, invite_link) VALUES (?, ?, ?)" if False else "INSERT OR REPLACE INTO channels (channel_id, invite_link) VALUES (?, ?)", (admin_data[uid]['channel_id'], text))
        conn.commit()
        conn.close()
        user_states[uid] = None
        bot.send_message(message.chat.id, "✅ Kanal qo'shildi!")
        return

    elif state == "WAITING_DELETE_CHANNEL":
        conn, cursor = get_db()
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (text,))
        conn.commit()
        conn.close()
        user_states[uid] = None
        bot.send_message(message.chat.id, f"🗑 `{text}` o'chirildi.")
        return

    elif state == "WAITING_BROADCAST":
        user_states[uid] = None
        conn, cursor = get_db()
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        conn.close()
        count = 0
        bot.send_message(message.chat.id, "🚀 Rassilka boshlandi...")
        for u in all_users:
            try:
                bot.copy_message(chat_id=u[0], from_chat_id=message.chat.id, message_id=message.message_id)
                count += 1
            except Exception:
                pass
        bot.send_message(message.chat.id, f"✅ {count} kishiga yuborildi.")
        return

    if text == "📊 Statistika":
        conn, cursor = get_db()
        cursor.execute("SELECT COUNT(*) FROM users")
        u_c = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM movies")
        m_c = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM channels")
        c_c = cursor.fetchone()[0]
        conn.close()
        bot.send_message(message.chat.id, f"📈 **Statistika:**\n\n👤 Foydalanuvchilar: {u_c}\n🎬 Kinolar: {m_c}\n📢 Kanallar: {c_c}", parse_mode="Markdown")
        return

    elif text == "🔍 Kino qidirish":
        bot.send_message(message.chat.id, "Kino kodini yuboring:")
        return

    conn, cursor = get_db()
    cursor.execute("SELECT name, link FROM movies WHERE code = ?", (text,))
    movie = cursor.fetchone()
    conn.close()

    if movie:
        bot.send_message(message.chat.id, f"🎬 **{movie[0]}**\n\n📥 Yuklab olish: {movie[1]}")
    else:
        bot.send_message(message.chat.id, f"Afsuski, `{text}` kodli kino topilmadi.")

bot.infinity_polling(timeout=20, long_polling_timeout=5)
