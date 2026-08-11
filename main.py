import asyncio
import logging
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '8696461606:AAFECW9WAc63ubvVhM93sOTWUnW45owkngU'
ADMIN_ID = 1260436370

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- BAZA SOZLAMALARI ---
def init_db():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, name TEXT, link TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, invite_link TEXT)''')
    
    cursor.execute("SELECT * FROM channels WHERE channel_id = ?", ("-1004383556829",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO channels (channel_id, invite_link) VALUES (?, ?)", 
                       ("-1004383556829", "https://t.me/+KUfXmD3NAHs4Zjgy"))
    conn.commit()
    conn.close()

init_db()

user_states = {}
admin_data = {}

# --- YORDAMCHI FUNKSIYALAR ---
async def check_sub(user_id: int) -> bool:
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM channels")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        try:
            member = await bot.get_chat_member(chat_id=row[0], user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True

def sub_keyboard():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT invite_link FROM channels")
    rows = cursor.fetchall()
    conn.close()

    markup = InlineKeyboardMarkup(row_width=1)
    for idx, row in enumerate(rows, 1):
        markup.add(InlineKeyboardButton(text=f"📢 {idx}-kanalga obuna bo'lish", url=row[0]))
    markup.add(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub"))
    return markup

def main_keyboard(user_id: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Kino qidirish", "📊 Statistika")
    if user_id == ADMIN_ID:
        markup.row("➕ Kino qo'shish", "❌ Kino o'chirish")
        markup.row("📢 Kanal qo'shish", "🗑 Kanal o'chirish")
        markup.row("📜 Kanallar ro'yxati", "📤 Rassilka (Reklama)")
    return markup

# --- KANAL ZAYAVKALARINI INSTANT TASDIQLASH ---
@dp.chat_join_request_handler()
async def auto_approve(chat_join_request: types.ChatJoinRequest):
    try:
        await chat_join_request.approve()
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (chat_join_request.from_user.id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Zayavka xatosi: {e}")

# --- HANDLERLAR ---
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    uid = message.from_user.id
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()

    if not await check_sub(uid):
        await message.answer("⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**", 
                             parse_mode="Markdown", reply_markup=sub_keyboard())
        return

    await message.answer("Salom! Topkinolar HD botiga xush kelibsiz!\n\nKino kodini yuboring:", 
                         reply_markup=main_keyboard(uid))

@dp.callback_query_handler(lambda call: call.data == "check_sub")
async def callback_check(call: types.CallbackQuery):
    uid = call.from_user.id
    if await check_sub(uid):
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer("✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.", 
                                 reply_markup=main_keyboard(uid))
    else:
        await call.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@dp.message_handler(content_types=types.ContentType.ANY)
async def handle_all(message: types.Message):
    uid = message.from_user.id
    text = message.text

    if uid != ADMIN_ID and not await check_sub(uid):
        await message.answer("⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**", 
                             parse_mode="Markdown", reply_markup=sub_keyboard())
        return

    if uid == ADMIN_ID:
        if text == "➕ Kino qo'shish":
            user_states[uid] = "WAITING_CODE"
            await message.answer("Kino uchun KOD kiriting (masalan: 102):")
            return
        elif text == "❌ Kino o'chirish":
            user_states[uid] = "WAITING_DELETE_CODE"
            await message.answer("O'chirmoqchi bo'lgan kino KODini kiriting:")
            return
        elif text == "📢 Kanal qo'shish":
            user_states[uid] = "WAITING_CHANNEL_ID"
            await message.answer("Kanal ID raqamini yoki Username'ini kiriting:")
            return
        elif text == "🗑 Kanal o'chirish":
            user_states[uid] = "WAITING_DELETE_CHANNEL"
            await message.answer("O'chirmoqchi bo'lgan kanal ID raqami yoki username'ini kiriting:")
            return
        elif text == "📜 Kanallar ro'yxati":
            conn = sqlite3.connect('movies.db')
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, invite_link FROM channels")
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                await message.answer("Hozircha majburiy obuna kanallari yo'q.")
            else:
                res = "📜 **Majburiy obuna kanallari:**\n\n"
                for r in rows:
                    res += f"🔹 **ID/User:** `{r[0]}`\n🔗 **Link:** {r[1]}\n\n"
                await message.answer(res, parse_mode="Markdown")
            return
        elif text == "📤 Rassilka (Reklama)":
            user_states[uid] = "WAITING_BROADCAST"
            await message.answer("Barcha foydalanuvchilarga yubormoqchi bo'lgan reklama postini yuboring:")
            return

    state = user_states.get(uid)

    if state == "WAITING_CODE":
        admin_data[uid] = {'code': text}
        user_states[uid] = "WAITING_NAME"
        await message.answer("Kino NOMI ni kiriting (masalan: Avatar 2):")
        return

    elif state == "WAITING_NAME":
        admin_data[uid]['name'] = text
        user_states[uid] = "WAITING_LINK"
        await message.answer("Kino HAVOLASI ni kiriting:")
        return

    elif state == "WAITING_LINK":
        code = admin_data[uid]['code']
        name = admin_data[uid]['name']
        link = text

        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO movies (code, name, link) VALUES (?, ?, ?)", (code, name, link))
        conn.commit()
        conn.close()

        user_states[uid] = None
        await message.answer(f"✅ Kino saqlandi!\n\nKod: {code}\nNomi: {name}\nHavola: {link}")
        return

    elif state == "WAITING_DELETE_CODE":
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE code = ?", (text,))
        conn.commit()
        conn.close()
        user_states[uid] = None
        await message.answer(f"🗑 `{text}` kodli kino bazadan o'chirildi.")
        return

    elif state == "WAITING_CHANNEL_ID":
        admin_data[uid] = {'channel_id': text}
        user_states[uid] = "WAITING_CHANNEL_LINK"
        await message.answer("Kanalning TAKLIF HAVOLASI (linki)ni kiriting:")
        return

    elif state == "WAITING_CHANNEL_LINK":
        ch_id = admin_data[uid]['channel_id']
        ch_link = text
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO channels (channel_id, invite_link) VALUES (?, ?)", (ch_id, ch_link))
        conn.commit()
        conn.close()
        user_states[uid] = None
        await message.answer(f"✅ Yangi kanal majburiy obunaga qo'shildi!\n\nID: `{ch_id}`\nLink: {ch_link}", parse_mode="Markdown")
        return

    elif state == "WAITING_DELETE_CHANNEL":
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (text,))
        conn.commit()
        conn.close()
        user_states[uid] = None
        await message.answer(f"🗑 `{text}` kanali majburiy obunadan olib tashlandi.")
        return

    elif state == "WAITING_BROADCAST":
        user_states[uid] = None
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        conn.close()
        
        count = 0
        await message.answer("🚀 Rassilka boshlandi...")
        for u in all_users:
            try:
                await message.copy_to(chat_id=u[0])
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await message.answer(f"✅ Reklama xabari {count} ta foydalanuvchiga yetkazildi!")
        return

    if text == "📊 Statistika":
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        u_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM movies")
        m_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM channels")
        c_count = cursor.fetchone()[0]
        conn.close()
        await message.answer(f"📈 **Bot statistikasi:**\n\n👤 Foydalanuvchilar: {u_count} ta\n🎬 Kinolar soni: {m_count} ta\n📢 Obuna kanallari: {c_count} ta", parse_mode="Markdown")
        return

    elif text == "🔍 Kino qidirish":
        await message.answer("Kino kodini yuboring (masalan: 101, 102...):")
        return

    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, link FROM movies WHERE code = ?", (text,))
    movie = cursor.fetchone()
    conn.close()

    if movie:
        await message.answer(f"🎬 **{movie[0]}**\n\n📥 Yuklab olish havolasi: {movie[1]}")
    else:
        await message.answer(f"Afsuski, `{text}` kodli kino topilmadi.")

# --- RENDER PORT HEALTH-CHECK ---
async def handle_ping(request):
    return web.Response(text="Bot ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def on_startup(dp):
    asyncio.create_task(start_web_server())

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
