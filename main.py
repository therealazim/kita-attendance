import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from geopy.distance import geodesic
from datetime import datetime
from aiohttp import web

# --- SOZLAMALAR ---
TOKEN = "8268187024:AAExyjArsQYeJJf1EOmy6Ho-E9H8Eoa4w_o"
ADMIN_GROUP_ID = -1003885800610
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- RENDER UCHUN WEB SERVER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render avtomatik beradigan PORT-dan foydalanamiz
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# --- BOT LOGIKASI ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    button = types.KeyboardButton(text="📍 Kelganimni tasdiqlash", request_location=True)
    kb = types.ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)
    await message.answer(
        f"Salom, {message.from_user.full_name}!\n"
        "O'quv markazi davomat botiga xush kelibsiz.\n"
        "Tasdiqlash uchun tugmani bosing.", 
        reply_markup=kb
    )

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_coords = (message.location.latitude, message.location.longitude)
    current_time = datetime.now().strftime("%H:%M")
    
    found_branch = None
    min_dist = 0

    for branch in LOCATIONS:
        dist = geodesic((branch["lat"], branch["lon"]), user_coords).meters
        if dist <= ALLOWED_DISTANCE:
            found_branch = branch["name"]
            min_dist = dist
            break

    if found_branch:
        user_mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
        report = (
            f"🔔 **Yangi davomat!**\n\n"
            f"👤 **O'qituvchi:** {user_mention}\n"
            f"📍 **Manzil:** {found_branch}\n"
            f"⏰ **Vaqt:** {current_time}\n"
            f"📏 **Masofa:** {int(min_dist)} m"
        )
        await bot.send_message(chat_id=ADMIN_GROUP_ID, text=report, parse_mode="Markdown")
        await message.answer(f"✅ Tasdiqlandi! Siz {found_branch} hududidasiz.")
    else:
        await message.answer("❌ Siz belgilangan manzillar hududida emassiz!")

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    # Web serverni alohida task qilib ishga tushiramiz
    asyncio.create_task(start_web_server())
    # Botni ishga tushiramiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())