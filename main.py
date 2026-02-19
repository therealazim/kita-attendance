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

# --- SOZLAMALAR ---
TOKEN = "8268187024:AAExyjArsQYeJJf1EOmy6Ho-E9H8Eoa4w_o"
ADMIN_GROUP_ID = -1003885800610
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150 # Bu masofani keyinchalik o'zgartirish mumkin

# Vaqtinchalik xotira (Ma'lumotlar bazasi o'rniga)
user_data = {} # {user_id: "Ism Sharif"}
attendance_log = set() # {(user_id, sana)}

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Registration(StatesGroup):
    waiting_for_name = State()

# --- WEB SERVER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()

# --- BOT LOGIKASI ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.answer("Xush kelibsiz! Davomatdan oldin iltimos, to'liq ism-sharifingizni yuboring:")
        await state.set_state(Registration.waiting_for_name)
    else:
        await show_main_menu(message)

@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    user_data[message.from_user.id] = message.text
    await state.clear()
    await message.answer(f"Rahmat, {message.text}! Endi davomat qilishingiz mumkin.")
    await show_main_menu(message)

async def show_main_menu(message: types.Message):
    button = types.KeyboardButton(text="📍 Kelganimni tasdiqlash", request_location=True)
    kb = types.ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)
    await message.answer("Tugmani bosing:", reply_markup=kb)

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Ismni tekshirish
    full_name = user_data.get(user_id, message.from_user.full_name)

    # 2. Takroriy davomatni tekshirish
    if (user_id, today) in attendance_log:
        await message.answer("⚠️ Siz bugun allaqachon davomatdan o'tgansiz!")
        return

    user_coords = (message.location.latitude, message.location.longitude)
    found_branch = None
    
    for branch in LOCATIONS:
        if geodesic((branch["lat"], branch["lon"]), user_coords).meters <= ALLOWED_DISTANCE:
            found_branch = branch["name"]
            break

    if found_branch:
        attendance_log.add((user_id, today))
        current_time = datetime.now().strftime("%H:%M")
        
        # Admin guruhiga hisobot
        report = (
            f"✅ **Yangi Davomat**\n"
            f"👤 **O'qituvchi:** {full_name}\n"
            f"📍 **Manzil:** {found_branch}\n"
            f"⏰ **Vaqt:** {current_time}"
        )
        await bot.send_message(chat_id=ADMIN_GROUP_ID, text=report, parse_mode="Markdown")
        await message.answer(f"✅ Rahmat, {full_name}! Davomat tasdiqlandi.")
        
        # 3. Google Sheets (Kelajakda shu yerga yoziladi)
        logging.info(f"Sheets Log: {full_name}, {found_branch}, {today}, {current_time}")

    else:
        await message.answer("❌ Xatolik! Siz belgilangan hududda emassiz.")

async def main():
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
