import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from datetime import datetime
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- ASOSIY SOZLAMALAR ---
TOKEN = "8268187024:AAGVlMOzOUTXMyrB8ePj9vHcayshkZ4PGW4"
ADMIN_GROUP_ID = -1003885800610 

# Manzillar
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150 

# --- BOT VA XOTIRA ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
user_names = {}
attendance_log = set()

class Registration(StatesGroup):
    waiting_for_name = State()

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
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_names:
        await message.answer("Xush kelibsiz! Botdan foydalanish uchun ism-sharifingizni yuboring:")
        await state.set_state(Registration.waiting_for_name)
    else:
        await show_menu(message)

@dp.message(Registration.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    # Foydalanuvchi kiritgan ismni saqlaymiz
    user_names[message.from_user.id] = message.text
    await state.clear()
    await message.answer(f"Rahmat, {message.text}! Endi davomat qilishingiz mumkin.")
    await show_menu(message)

async def show_menu(message: types.Message):
    kb = [[types.KeyboardButton(text="📍 Kelganimni tasdiqlash", request_location=True)]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Tugmani bosing:", reply_markup=keyboard)

@dp.message(F.location)
async def handle_loc(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
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
        # MUHIM: Bu yerda faqat o'zi yozgan ismni olamiz, profil havolasini emas
        full_name = user_names.get(user_id, "Noma'lum foydalanuvchi")
        now_time = datetime.now().strftime("%H:%M")
        
        # Hisobot matni (Markdown'siz, oddiy matn ko'rinishida)
        report = (
            f"✅ Yangi Davomat\n"
            f"👤 O'qituvchi: {full_name}\n"
            f"📍 Manzil: {found_branch}\n"
            f"📅 Sana: {today}\n"
            f"⏰ Vaqt: {now_time}"
        )
        
        try:
            # parse_mode olib tashlandi, shunda ism ko'k link bo'lib qolmaydi
            await bot.send_message(ADMIN_GROUP_ID, report)
            attendance_log.add((user_id, today))
            await message.answer(f"✅ Tasdiqlandi! Siz {found_branch} hududidasiz.")
        except Exception as e:
            logging.error(f"Xato: {e}")
            await message.answer("❌ Xatolik yuz berdi.")
    else:
        await message.answer("❌ Siz belgilangan hududda emassiz!")

async def main():
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
