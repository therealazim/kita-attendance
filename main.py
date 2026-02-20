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
# Siz yuborgan oxirgi API token
TOKEN = "8268187024:AAGVlMOzOUTXMyrB8ePj9vHcayshkZ4PGW4"
ADMIN_GROUP_ID = -1003885800610 

LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150 

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_names = {}
attendance_log = set()

class Registration(StatesGroup):
    waiting_for_name = State()

# --- WEB SERVER (RENDER PORT FIX) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render'da "No open ports detected" chiqmasligi uchun:
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Server {port}-portda ishga tushdi")

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
    # O'qituvchi yozgan ismni saqlaymiz
    user_names[message.from_user.id] = message.text
    await state.clear()
    await message.answer(f"Rahmat, {message.text}! Endi davomat qilishingiz mumkin.")
    await show_menu(message)

async def show_menu(message: types.Message):
    kb = [[types.KeyboardButton(text="📍 Kelganimni tasdiqlash", request_location=True)]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Davomat qilish uchun pastdagi tugmani bosing:", reply_markup=keyboard)

@dp.message(F.location)
async def handle_loc(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    if (user_id, today) in attendance_log:
        await message.answer("⚠️ Siz bugun allaqachon davomatdan o'tgansiz!")
        return

    user_coords = (message.location.latitude, message
