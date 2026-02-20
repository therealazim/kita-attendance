import asyncio
import os
import logging
import pytz  # Vaqt zonasi uchun
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from geopy.distance import geodesic
from datetime import datetime
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
TOKEN = "8268187024:AAGVlMOzOUTXMyrB8ePj9vHcayshkZ4PGW4"
ADMIN_GROUP_ID = -1003885800610 
UZB_TZ = pytz.timezone('Asia/Tashkent') # GMT+5 sozlamasi

LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150 

bot = Bot(token=TOKEN)
dp = Dispatcher()
attendance_log = set()

# --- WEB SERVER (RENDER UCHUN) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- HANDLERS ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = [[types.KeyboardButton(text="📍 Kelganimni tasdiqlash", request_location=True)]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        f"Xush kelibsiz, {message.from_user.full_name}!\n"
        f"Davomat qilish uchun pastdagi tugmani bosing:", 
        reply_markup=keyboard
    )

@dp.message(F.location)
async def handle_loc(message: types.Message):
    user_id = message.from_user.id
    # O'zbekiston vaqti bilan hozirgi sana va vaqt
    now_uzb = datetime.now(UZB_TZ)
    today = now_uzb.strftime("%Y-%m-%d")
    
    if (user_id, today) in attendance_log:
        await message.answer("⚠️ Siz bugun allaqachon davomatdan o'tgansiz!")
        return

    user_coords = (message.location.latitude, message.location.longitude)
    found_branch = None
    for branch in LOCATIONS:
        dist = geodesic((branch["lat"], branch["lon"]), user_coords).meters
        if dist <= ALLOWED_DISTANCE:
            found_branch = branch["name"]
            break

    if found_branch:
        # Telegram profildagi ism-familiya
        full_name = message.from_user.full_name
        now_time = now_uzb.strftime("%H:%M:%S")
        
        report = (
            f"✅ **Yangi Davomat**\n\n"
            f"👤 **O'qituvchi:** {full_name}\n"
            f"📍 **Manzil:** {found_branch}\n"
            f"📅 **Sana:** {today}\n"
            f"⏰ **Vaqt:** {now_time} (GMT+5)"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="👤 Profilni ko'rish", 
            url=f"tg://user?id={user_id}")
        )

        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID, 
                text=report, 
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            attendance_log.add((user_id, today))
            await message.answer(f"✅ Tasdiqlandi! ({found_branch})")
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        await message.answer("❌ Siz belgilangan hududda emassiz!")

async def main():
    asyncio.create_task(start_web_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
