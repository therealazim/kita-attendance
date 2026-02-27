import asyncio
import os
import logging
import pytz 
import io
import aiohttp
from datetime import datetime, timedelta
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from geopy.distance import geodesic
from aiohttp import web
import openpyxl
from openpyxl.styles import Font, Alignment

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
TOKEN = "8268187024:AAGVlMOzOUTXMyrB8ePj9vHcayshkZ4PGW4"
ADMIN_GROUP_ID = -1003885800610 
UZB_TZ = pytz.timezone('Asia/Tashkent') 

# --- OB-HAVO SOZLAMALARI ---
WEATHER_API_KEY = "2b7818365e4ac19cebd34c34a135a669"
WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/weather"

# BARCHA LOKATSIYALAR RO'YXATI
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
ALLOWED_DISTANCE = 500

# Ob-havo shartlariga mos tavsiyalar
WEATHER_RECOMMENDATIONS = {
    "Clear": {
        "uz": "☀️ Bugun havo ochiq. Sayr qilish uchun ajoyib kun! Quyoshdan saqlanish uchun soyabon olishni unutmang.",
        "ru": "☀️ Сегодня ясно. Отличный день для прогулки! Не забудьте взять зонтик от солнца."
    },
    "Clouds": {
        "uz": "☁️ Bugun havo bulutli. Salqin havo bilan ish kuningiz samarali o'tsin!",
        "ru": "☁️ Сегодня облачно. Пусть прохладная погода сделает ваш рабочий день продуктивным!"
    },
    "Rain": {
        "uz": "🌧️ Bugun yomg'ir yog'moqda. Soyabon olishni unutmang va issiq choy iching!",
        "ru": "🌧️ Сегодня идет дождь. Не забудьте взять зонтик и выпейте горячего чая!"
    },
    "Thunderstorm": {
        "uz": "⛈️ Momaqaldiroq bo'lmoqda. Ehtiyot bo'ling va imkon qadar uyda qoling!",
        "ru": "⛈️ Гроза. Будьте осторожны и по возможности оставайтесь дома!"
    },
    "Snow": {
        "uz": "❄️ Qor yog'moqda. Issiq kiyining va yo'llarda ehtiyot bo'ling!",
        "ru": "❄️ Идет снег. Одевайтесь теплее и будьте осторожны на дорогах!"
    },
    "Mist": {
        "uz": "🌫️ Tuman tushgan. Haydovchilar ehtiyot bo'ling!",
        "ru": "🌫️ Туман. Водители, будьте осторожны!"
    },
    "Fog": {
        "uz": "🌫️ Tuman tushgan. Haydovchilar ehtiyot bo'ling!",
        "ru": "🌫️ Туман. Водители, будьте осторожны!"
    },
    "Haze": {
        "uz": "🌫️ Havo tumanli. Ehtiyot bo'ling!",
        "ru": "🌫️ Дымка. Будьте осторожны!"
    }
}

# Haroratga mos tavsiyalar
TEMPERATURE_RECOMMENDATIONS = {
    "uz": [
        (35, "🥵 Juda issiq! Ko'p suv iching va soyada qoling. Engil kiyimlar tanlang."),
        (30, "🥵 Issiq! Quyoshdan saqlaning va ko'p suv iching."),
        (25, "😊 Issiq, ammo qulay. Yengil kiyining."),
        (20, "😊 Ajoyib harorat! Sayr qilish uchun ideal."),
        (15, "😌 Ob-havo mo''tadil. Yengil ko'ylagi olsangiz bo'ladi."),
        (10, "🥶 Salqin. Ko'ylagi kiyishni tavsiya qilaman."),
        (5, "🥶 Sovuq. Ko'ylagi olgan ma'qul."),
        (0, "🧥 Juda sovuq! Qalin kiyining."),
        (-10, "🧥 Qahraton! Qalin kiyining va qo'lqop taqing."),
        (-float('inf'), "🥶 Juda sovuq! Qalin kiyining, qo'lqop va sharf taqing.")
    ],
    "ru": [
        (35, "🥵 Очень жарко! Пейте больше воды и оставайтесь в тени."),
        (30, "🥵 Жарко! Избегайте солнца и пейте много воды."),
        (25, "😊 Тепло и комфортно. Одевайтесь легко."),
        (20, "😊 Прекрасная температура! Идеально для прогулки."),
        (15, "😌 Умеренная погода. Можно надеть легкую куртку."),
        (10, "🥶 Прохладно. Рекомендую надеть куртку."),
        (5, "🥶 Холодно. Лучше надеть куртку."),
        (0, "🧥 Очень холодно! Одевайтесь теплее."),
        (-10, "🧥 Мороз! Одевайтесь тепло и носите перчатки."),
        (-float('inf'), "🥶 Сильный мороз! Одевайтесь очень тепло, носите перчатки и шарф.")
    ]
}

# Tillar uchun matnlar
TRANSLATIONS = {
    'uz': {
        'welcome': "🌟 **Xush kelibsiz, {name}!**\n\nMen davomat botiman. Quyidagi tugmalar orqali:\n• Davomat qilishingiz\n• Statistikangizni ko'rishingiz\n• Filiallar bilan tanishishingiz mumkin\n\nBoshlash uchun pastdagi tugmalardan foydalaning!",
        'stats': "📊 **Sizning statistikangiz:**",
        'no_stats': "📭 Hali davomat qilmagansiz",
        'branches': "🏢 **Mavjud filiallar:**",
        'distance_info': "📍 Barcha filiallar {distance} metr masofada aniqlanadi",
        'help': "🤖 **Botdan foydalanish qo'llanmasi:**\n\n📍 **Davomat qilish uchun:**\n• Pastdagi \"📍 Kelganimni tasdiqlash\" tugmasini bosing\n• Joylashuvingizni yuboring\n\n📊 **Statistika:**\n• \"📊 Mening statistikam\" - shaxsiy davomat tarixingiz\n• \"🏢 Filiallar\" - barcha mavjud filiallar ro'yxati\n\n⚠️ **Eslatmalar:**\n• Kuniga faqat 1 marta davomat qilish mumkin\n• Filialdan {distance} metr masofada bo'lishingiz kerak\n• Davomat faqat Toshkent vaqti bilan hisoblanadi",
        'attendance_success': "✅ **Davomat tasdiqlandi!**\n\n🏫 **Filial:** {branch}\n📅 **Sana:** {date}\n⏰ **Vaqt:** {time}\n📊 **Bu oydagi tashriflar:** {count} marta\n📏 **Masofa:** {distance:.1f} metr\n\nEslatma: Ertaga yana davomat qilishingiz mumkin!",
        'already_attended': "⚠️ Siz bugun **{branch}** hududida allaqachon davomatdan o'tgansiz!",
        'not_in_area': "❌ Siz belgilangan ta'lim muassasalari hududida emassiz!",
        'daily_reminder': "⏰ **Eslatma!** Bugun hali davomat qilmagansiz. Ish kuningizni boshlash uchun davomatni tasdiqlang!",
        'weekly_top': "🏆 **Haftaning eng faol o'qituvchilari:**\n\n{top_list}",
        'monthly_report': "📊 **{month} oyi uchun hisobot**\n\n{report}",
        'language_changed': "✅ Til o'zgartirildi: O'zbek tili",
        'weather_info': "🌤️ **Ob-havo ma'lumoti**\n\n{weather}",
        'weather_error': "❌ Ob-havo ma'lumotini olishda xatolik yuz berdi. Qaytadan urinib ko'ring.",
        'weather_button': "🌤️ Ob-havo",
        'buttons': {
            'attendance': "📍 Kelganimni tasdiqlash",
            'my_stats': "📊 Mening statistikam",
            'branches': "🏢 Filiallar",
            'help': "❓ Yordam",
            'top_week': "🏆 Hafta topi",
            'language': "🌐 Til"
        }
    },
    'ru': {
        'welcome': "🌟 **Добро пожаловать, {name}!**\n\nЯ бот для отметок. С помощью кнопок ниже вы можете:\n• Отметиться\n• Посмотреть статистику\n• Ознакомиться с филиалами\n\nИспользуйте кнопки ниже для начала!",
        'stats': "📊 **Ваша статистика:**",
        'no_stats': "📭 Вы еще не отмечались",
        'branches': "🏢 **Доступные филиалы:**",
        'distance_info': "📍 Все филиалы определяются в радиусе {distance} метров",
        'help': "🤖 **Руководство по использованию:**\n\n📍 **Для отметки:**\n• Нажмите кнопку \"📍 Подтвердить прибытие\"\n• Отправьте свою геолокацию\n\n📊 **Статистика:**\n• \"📊 Моя статистика\" - история отметок\n• \"🏢 Филиалы\" - список всех филиалов\n\n⚠️ **Примечания:**\n• Можно отмечаться только 1 раз в день\n• Вы должны находиться в радиусе {distance} метров от филиала",
        'attendance_success': "✅ **Отметка подтверждена!**\n\n🏫 **Филиал:** {branch}\n📅 **Дата:** {date}\n⏰ **Время:** {time}\n📊 **Посещений в этом месяце:** {count}\n📏 **Расстояние:** {distance:.1f} м\n\nПримечание: Завтра вы сможете отметиться снова!",
        'already_attended': "⚠️ Вы уже отмечались сегодня в филиале **{branch}**!",
        'not_in_area': "❌ Вы не находитесь в зоне учебных заведений!",
        'daily_reminder': "⏰ **Напоминание!** Вы еще не отметились сегодня. Подтвердите свое прибытие для начала рабочего дня!",
        'weekly_top': "🏆 **Самые активные учителя недели:**\n\n{top_list}",
        'monthly_report': "📊 **Отчет за {month}**\n\n{report}",
        'language_changed': "✅ Язык изменен: Русский язык",
        'weather_info': "🌤️ **Информация о погоде**\n\n{weather}",
        'weather_error': "❌ Ошибка при получении данных о погоде. Попробуйте снова.",
        'weather_button': "🌤️ Погода",
        'buttons': {
            'attendance': "📍 Подтвердить прибытие",
            'my_stats': "📊 Моя статистика",
            'branches': "🏢 Филиалы",
            'help': "❓ Помощь",
            'top_week': "🏆 Топ недели",
            'language': "🌐 Язык"
        }
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Ma'lumotlarni saqlash
daily_attendance_log = set()  # {(user_id, branch_name, date)}
attendance_counter = {}       # {(user_id, branch_name, month): count}
user_languages = {}           # {user_id: 'uz' or 'ru'}
user_ids = set()              # Barcha foydalanuvchilar ID si

# --- YORDAMCHI FUNKSIYALAR ---
def get_text(user_id: int, key: str, **kwargs):
    """Foydalanuvchi tiliga mos matn qaytarish"""
    lang = user_languages.get(user_id, 'uz')
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS['uz'].get(key, ''))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text

def get_button_text(user_id: int, button_key: str):
    """Foydalanuvchi tiliga mos tugma matni qaytarish"""
    lang = user_languages.get(user_id, 'uz')
    return TRANSLATIONS[lang]['buttons'][button_key]

async def main_keyboard(user_id: int):
    """Asosiy menyu tugmalarini yaratish"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text=get_button_text(user_id, 'attendance'), request_location=True),
        KeyboardButton(text=get_button_text(user_id, 'my_stats')),
        KeyboardButton(text=get_button_text(user_id, 'branches')),
        KeyboardButton(text=get_button_text(user_id, 'top_week')),
        KeyboardButton(text="🌤️ Ob-havo"),
        KeyboardButton(text=get_button_text(user_id, 'help')),
        KeyboardButton(text=get_button_text(user_id, 'language'))
    )
    builder.adjust(1, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

# --- OB-HAVO FUNKSIYALAR ---
async def get_weather_by_coords(lat: float, lon: float):
    """Koordinatalar bo'yicha ob-havo ma'lumotini olish"""
    params = {
        "lat": lat,
        "lon": lon,
        "appid": WEATHER_API_KEY,
        "units": "metric",
        "lang": "uz"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEATHER_API_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logging.error(f"Weather API error: {response.status}")
                    return None
    except Exception as e:
        logging.error(f"Error fetching weather: {e}")
        return None

def get_temperature_recommendation(temp: float, lang: str = 'uz'):
    """Haroratga mos tavsiya qaytarish"""
    recommendations = TEMPERATURE_RECOMMENDATIONS.get(lang, TEMPERATURE_RECOMMENDATIONS['uz'])
    
    for threshold, message in recommendations:
        if temp >= threshold:
            return message
    return f"🌡️ Harorat: {temp:.1f}°C"

def get_weather_emoji(weather_condition: str) -> str:
    """Ob-havo holatiga mos emoji qaytarish"""
    emoji_map = {
        "Clear": "☀️",
        "Clouds": "☁️",
        "Rain": "🌧️",
        "Drizzle": "🌦️",
        "Thunderstorm": "⛈️",
        "Snow": "❄️",
        "Mist": "🌫️",
        "Fog": "🌫️",
        "Haze": "🌫️"
    }
    return emoji_map.get(weather_condition, "🌡️")

def format_weather_message(weather_data: dict, lang: str = 'uz') -> str:
    """Ob-havo ma'lumotlarini formatlash"""
    if not weather_data:
        return "❌ Ob-havo ma'lumotini olishda xatolik yuz berdi."
    
    city = weather_data.get('name', 'Noma\'lum')
    if city == "" or city is None:
        city = "Toshkent"
        
    main = weather_data.get('main', {})
    weather = weather_data.get('weather', [{}])[0]
    wind = weather_data.get('wind', {})
    
    temp = main.get('temp', 0)
    feels_like = main.get('feels_like', 0)
    humidity = main.get('humidity', 0)
    pressure = main.get('pressure', 0)
    condition = weather.get('main', 'Unknown')
    description = weather.get('description', '')
    wind_speed = wind.get('speed', 0)
    
    emoji = get_weather_emoji(condition)
    
    # Asosiy tavsiya
    recommendation = WEATHER_RECOMMENDATIONS.get(condition, {}).get(lang, "")
    if not recommendation:
        recommendation = WEATHER_RECOMMENDATIONS.get('Clear', {}).get(lang, "")
    
    # Harorat tavsiyasi
    temp_recommendation = get_temperature_recommendation(temp, lang)
    
    # Bosimni mmHg ga o'tkazish
    pressure_mmhg = pressure * 0.750062
    
    message = f"""
{emoji} **Ob-havo ma'lumoti**

📍 **Joy:** {city}
🌡️ **Harorat:** {temp:.1f}°C (his qilinadi: {feels_like:.1f}°C)
☁️ **Holat:** {description.title()}
💧 **Namlik:** {humidity}%
💨 **Shamol:** {wind_speed:.1f} m/s
📊 **Bosim:** {pressure_mmhg:.1f} mmHg

💡 **Tavsiya:**
{recommendation}

{temp_recommendation}

📅 **Vaqt:** {datetime.now(UZB_TZ).strftime('%H:%M')}
"""
    return message

# --- WEB SERVER ---
async def handle(request):
    now_uzb = datetime.now(UZB_TZ)
    return web.Response(
        text=f"Bot is running! ✅\n\n"
             f"📅 Sana: {now_uzb.strftime('%Y-%m-%d')}\n"
             f"⏰ Vaqt: {now_uzb.strftime('%H:%M:%S')}\n"
             f"👥 Foydalanuvchilar: {len(user_ids)} ta\n"
             f"📊 Bugungi davomatlar: {len([k for k in daily_attendance_log if k[2] == now_uzb.strftime('%Y-%m-%d')])} ta"
    )

async def health_check(request):
    now_uzb = datetime.now(UZB_TZ)
    logging.info(f"Cron-job.org tomonidan tekshirildi: {now_uzb.strftime('%Y-%m-%d %H:%M:%S')}")
    return web.Response(text=f"Bot healthy - {now_uzb.strftime('%H:%M:%S')}", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# --- HANDLERS ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_ids.add(user_id)
    
    if user_id not in user_languages:
        user_languages[user_id] = 'uz'
    
    keyboard = await main_keyboard(user_id)
    name = message.from_user.full_name
    
    await message.answer(
        get_text(user_id, 'welcome', name=name),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'🌐 Til', '🌐 Язык'}))
async def change_language(message: types.Message):
    user_id = message.from_user.id
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
    )
    await message.answer("Tilni tanlang / Выберите язык:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split("_")[1]
    user_languages[user_id] = lang
    
    await callback.answer()
    await callback.message.delete()
    
    keyboard = await main_keyboard(user_id)
    await callback.message.answer(
        get_text(user_id, 'language_changed'),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌤️ Ob-havo")
async def weather_button(message: types.Message):
    """Ob-havo tugmasi bosilganda"""
    user_id = message.from_user.id
    await message.answer(
        "📍 Ob-havo ma'lumotini olish uchun joylashuvingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@dp.message(Command("weather"))
async def cmd_weather(message: types.Message):
    """Joriy ob-havo ma'lumotini olish"""
    user_id = message.from_user.id
    await message.answer(
        "📍 Ob-havo ma'lumotini olish uchun joylashuvingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@dp.message(F.text.in_({'📊 Mening statistikam', '📊 Моя статистика'}))
async def my_stats(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    current_month = now_uzb.strftime("%Y-%m")
    
    # Foydalanuvchining barcha davomatlarini topish
    user_attendances = defaultdict(lambda: defaultdict(int))
    for (uid, branch, date) in daily_attendance_log:
        if uid == user_id:
            month = date[:7]
            user_attendances[branch][month] += 1
    
    if not user_attendances:
        await message.answer(get_text(user_id, 'no_stats'), parse_mode="Markdown")
        return
    
    text = get_text(user_id, 'stats') + "\n\n"
    for branch, months in user_attendances.items():
        text += f"📍 **{branch}**\n"
        for month, count in months.items():
            if month == current_month:
                text += f"   • {month}: **{count}** marta (joriy oy)\n"
            else:
                text += f"   • {month}: {count} marta\n"
        text += "\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({'🏢 Filiallar', '🏢 Филиалы'}))
async def show_branches(message: types.Message):
    user_id = message.from_user.id
    
    text = get_text(user_id, 'branches') + "\n\n"
    
    # Filiallarni guruhlarga ajratish
    schools = []
    universities = []
    lyceums = []
    
    for branch in LOCATIONS:
        if "Maktab" in branch['name']:
            schools.append(branch['name'])
        elif "Universitet" in branch['name']:
            universities.append(branch['name'])
        else:
            lyceums.append(branch['name'])
    
    if universities:
        text += "**🏛 Universitetlar:**\n"
        for uni in universities:
            text += f"• {uni}\n"
        text += "\n"
    
    if lyceums:
        text += "**📚 Litseylar:**\n"
        for lyceum in lyceums:
            text += f"• {lyceum}\n"
        text += "\n"
    
    if schools:
        text += "**🏫 Maktablar:**\n"
        for school in schools:
            text += f"• {school}\n"
        text += "\n"
    
    text += get_text(user_id, 'distance_info', distance=ALLOWED_DISTANCE)
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({'❓ Yordam', '❓ Помощь'}))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        get_text(user_id, 'help', distance=ALLOWED_DISTANCE),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'🏆 Hafta topi', '🏆 Топ недели'}))
async def weekly_top(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    week_ago = now_uzb - timedelta(days=7)
    week_ago_str = week_ago.strftime("%Y-%m-%d")
    
    # Haftalik statistikani hisoblash
    weekly_stats = defaultdict(int)
    
    for (uid, branch, date) in daily_attendance_log:
        if date >= week_ago_str:
            weekly_stats[uid] += 1
    
    if not weekly_stats:
        await message.answer("📭 Bu hafta hali davomat yo'q")
        return
    
    # Top 10 foydalanuvchini saralash
    top_users = sorted(weekly_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    top_list = ""
    for i, (uid, count) in enumerate(top_users, 1):
        try:
            user = await bot.get_chat(uid)
            name = user.full_name
        except:
            name = f"Foydalanuvchi {uid}"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        top_list += f"{medal} {name}: **{count}** marta\n"
    
    await message.answer(
        get_text(user_id, 'weekly_top', top_list=top_list),
        parse_mode="Markdown"
    )

@dp.message(F.location)
async def handle_loc(message: types.Message):
    user_id = message.from_user.id
    user_ids.add(user_id)
    
    now_uzb = datetime.now(UZB_TZ)
    today_date = now_uzb.strftime("%Y-%m-%d")
    current_month = now_uzb.strftime("%Y-%m")
    now_time = now_uzb.strftime("%H:%M:%S")

    user_coords = (message.location.latitude, message.location.longitude)
    found_branch = None
    min_distance = float('inf')
    
    for branch in LOCATIONS:
        dist = geodesic((branch["lat"], branch["lon"]), user_coords).meters
        if dist <= ALLOWED_DISTANCE:
            if dist < min_distance:
                min_distance = dist
                found_branch = branch["name"]

    # Ob-havo ma'lumotini olish
    weather_data = await get_weather_by_coords(user_coords[0], user_coords[1])
    weather_message = format_weather_message(weather_data, user_languages.get(user_id, 'uz'))

    if found_branch:
        attendance_key = (user_id, found_branch, today_date)
        if attendance_key in daily_attendance_log:
            await message.answer(
                get_text(user_id, 'already_attended', branch=found_branch),
                parse_mode="Markdown"
            )
            return

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
            f"🔢 **Shu oydagi tashrif:** {visit_number}-marta\n"
            f"📏 **Masofa:** {min_distance:.1f} metr"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="👤 Profilni ko'rish", url=f"tg://user?id={user_id}"))

        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID, 
                text=report, 
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            
            # Foydalanuvchiga davomat va ob-havo ma'lumotini yuborish
            success_text = get_text(
                user_id, 
                'attendance_success',
                branch=found_branch,
                date=today_date,
                time=now_time,
                count=visit_number,
                distance=min_distance
            )
            
            full_response = f"{success_text}\n\n{weather_message}"
            await message.answer(full_response, parse_mode="Markdown")
            
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        # Agar davomat qilmasa ham ob-havo ma'lumotini berish
        await message.answer(
            f"{get_text(user_id, 'not_in_area')}\n\n{weather_message}",
            parse_mode="Markdown"
        )

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.chat.id != ADMIN_GROUP_ID:
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Oylik hisobot", callback_data="admin_monthly"),
        InlineKeyboardButton(text="📥 Excel export", callback_data="admin_excel")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users"),
        InlineKeyboardButton(text="📈 Umumiy statistika", callback_data="admin_stats")
    )
    
    await message.answer(
        "👨‍💼 **Admin panel**\n\nKerakli bo'limni tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: types.CallbackQuery):
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Ruxsat yo'q!")
        return
    
    action = callback.data.split("_")[1]
    now_uzb = datetime.now(UZB_TZ)
    
    if action == "monthly":
        current_month = now_uzb.strftime("%Y-%m")
        month_name = now_uzb.strftime("%B %Y")
        
        # Oylik statistika
        monthly_stats = defaultdict(lambda: defaultdict(int))
        for (uid, branch, date) in daily_attendance_log:
            if date.startswith(current_month):
                monthly_stats[branch][uid] += 1
        
        report = f"📊 **{month_name} oyi uchun hisobot**\n\n"
        
        for branch, users in monthly_stats.items():
            total = sum(users.values())
            unique_users = len(users)
            report += f"📍 **{branch}**\n"
            report += f"   Jami
