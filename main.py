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
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- SOZLAMALAR ---
TOKEN = "8268187024:AAExyjArsQYeJJf1EOmy6Ho-E9H8Eoa4w_o"
ADMIN_GROUP_ID = -1003885800610
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150 

# --- GOOGLE SHEETS SOZLAMASI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
# Jadvalingiz nomi Google Sheets'da aynan shunday bo'lishi kerak:
sheet = client.open("Davomat_Log").sheet1 

# --- BOT VA XOTIRA ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
user_names = {} # {user_id: "Ism Sharif"}
attendance_log = set() # {(user_id, sana)}

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
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- BOT KOMANDALARI ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_names:
        await message.answer("Salom! Davomat botidan foydalanish uchun to'liq ism-sharifingizni yuboring:")
        await state.set_state(Registration.waiting_for_name)
    else:
        await show_menu(message)

@dp.message(Registration.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    user_names[message.from_user.id] = message.text
    await state.clear()
    await message.answer(f"Rahmat, {message.text}! Endi lokatsiya orqali davomat qilishingiz mumkin.")
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
        return await message.answer("⚠️ Siz bugun davomatdan o'tgansiz!")

    user_coords = (message.location.latitude, message.location.longitude)
    found_branch = None
    for branch in LOCATIONS:
        if geodesic((branch["lat"], branch["lon"]), user_coords).meters <= ALLOWED_DISTANCE:
            found_branch = branch["name"]
            break

    if found_branch:
        full_name = user_names.get(user_id, message.from_user.full_name)
        now_time = datetime.now().strftime("%H:%M")
        
        # 1. Google Sheets-ga yozish
        try:
            sheet.append_row([full_name, found_branch, today, now_time])
        except Exception as e:
            logging.error(f"Sheets error: {e}")

        # 2. Guruhga yozish
        report = f"✅ **Davomat**\n👤 {full_name}\n📍 {found_branch}\n⏰ {now_time}"
        await bot.send_message(ADMIN_GROUP_ID, report, parse_mode="Markdown")
        
        attendance_log.add((user_id, today))
        await message.answer("✅ Davomat tasdiq

