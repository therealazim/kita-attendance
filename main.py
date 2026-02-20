import asyncio
import os
import logging
import pytz 
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
UZB_TZ = pytz.timezone('Asia/Tashkent') 

# BARCHA LOKATSIYALAR RO'YXATI (YANGILANGAN)
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290},
    {"name": "290-Maktab", "lat": 41.234736, "lon": 69.350745},
    {"name": "348-Maktab", "lat": 41.214092, "lon": 69.340152},
    {"name": "347-Maktab", "lat": 41.236833, "lon": 69.372048},
    {"name": "358-Maktab", "lat": 41.240690, "lon": 69.366529},
    {"name": "346-Maktab", "lat": 41.216158, "lon": 69.323902},
    {"name": "293-Maktab", "lat": 41.253573, "lon": 69.377204},
    {"name": "345-Maktab", "lat": 41.220456, "lon": 69.333441},
    {"name": "IM.Gubkin Litseyi", "lat": 41.254183, "lon": 69.382270},
    {"name": "Narxoz universiteti", "lat": 41.308916, "lon": 69.247496},
    {"name": "Narxoz litseyi", "lat": 41.306951, "lon": 69.247667},
    {"name": "Tekstil litseyi", "lat": 41.284784, "lon": 69.249356},
    {"name": "200-Maktab", "lat": 41.263860, "lon": 69.181538},
    {"name": "Selxoz litseyi", "lat": 41.362532, "lon": 69.340768},
    {"name": "294-Maktab", "lat": 41.281633, "lon": 69.289237}
]
ALLOWED_DISTANCE = 150 # Metrda

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Ma'lumotlarni saqlash
daily_attendance_log = set() # {(user_id, branch_name, date)}
attendance_counter = {}      # {(user_id, branch_name, month): count}

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
    name = message.from_user.full_name
    await message.answer(
        f"Xush kelibsiz, {name}!\n\nDavomat qilish uchun pastdagi tugmani bosing:", 
        reply_markup=keyboard
    )

@dp.message(F.location)
async def handle_loc(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    today_date = now_uzb.strftime("%Y-%m-%d")
    current_month = now_uzb.strftime("%Y-%m")
    now_time = now_uzb.strftime("%H:%M:%S")

    user_coords = (message.location.latitude, message.location.longitude)
    found_branch = None
    
    for branch in LOCATIONS:
        dist = geodesic((branch["lat"], branch["lon"]), user_coords).meters
        if dist <= ALLOWED_DISTANCE:
            found_branch = branch["name"]
            break

    if found_branch:
        # Kunlik va filial bo'yicha cheklov
        attendance_key = (user_id, found_branch, today_date)
        if attendance_key in daily_attendance_log:
            await message.answer(f"⚠️ Siz bugun **{found_branch}** hududida allaqachon davomatdan o'tgansiz!")
            return

        # Hisoblagichni oshirish
        counter_key = (user_id, found_branch, current_month)
        attendance_counter[counter_key] = attendance_counter.get(counter_key, 0) + 1
        visit_number = attendance_counter[counter_key]
        
        daily_attendance_log.add(attendance_key)
        full_name = message.from_user.full_name
        
        # Admin guruhiga hisobot
        report = (
            f"✅ **Yangi Davomat**\n\n"
            f"👤 **O'qituvchi:** {full_name}\n"
            f"📍 **Manzil:** {found_branch}\n"
            f"📅 **Sana:** {today_date}\n"
            f"⏰ **Vaqt:** {now_time}\n"
            f"🔢 **Shu oydagi tashrif:** {visit_number}-marta"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="👤 Profilni ko'rish", url=f"tg://user?id={user_id}"))

        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID, 
                text=report, 
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            await message.answer(
                f"✅ Tasdiqlandi!\n\nFilial: {found_branch}\n"
                f"Sana: {today_date}\n"
                f"Ushbu oydagi tashrifingiz: {visit_number}-marta"
            )
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        await message.answer("❌ Siz belgilangan ta'lim muassasalari hududida emassiz!")

async def main():
    asyncio.create_task(start_web_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
