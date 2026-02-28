import asyncio
import os
import logging
import pytz 
import io
import aiohttp
import json
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

# Bot va Dispatcher obyektlarini yaratish
bot = Bot(token=TOKEN)
dp = Dispatcher()

# BARCHA LOKATSIYALAR RO'YXATI
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290},
    {"name": "126-Maktab", "lat": 41.260249, "lon": 69.153216},
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

# DARS JADVALI UCHUN MA'LUMOTLAR
WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
WEEKDAYS_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

# Soatlar ro'yxati (08:00 dan 20:00 gacha)
HOURS_LIST = [f"{h:02d}:00" for h in range(8, 21)]

# Foydalanuvchi dars jadvallari
# {user_id: {branch: {weekday: [hours]}}}
user_schedules = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

# Ob-havo shartlariga mos tavsiyalar
WEATHER_RECOMMENDATIONS = {
    "Clear": {
        "uz": "☀️ Bugun havo ochiq. Sayr qilish uchun ajoyib kun!",
        "ru": "☀️ Сегодня ясно. Отличный день для прогулки!",
        "kr": "☀️ 오늘은 맑은 날씨입니다. 산책하기 좋은 날이에요!"
    },
    "Clouds": {
        "uz": "☁️ Bugun havo bulutli. Salqin havo bilan ish kuningiz samarali o'tsin!",
        "ru": "☁️ Сегодня облачно. Пусть прохладная погода сделает ваш рабочий день продуктивным!",
        "kr": "☁️ 오늘은 흐린 날씨입니다. 시원한 날씨와 함께 즐거운 하루 되세요!"
    },
    "Rain": {
        "uz": "🌧️ Bugun yomg'ir yog'moqda. Soyabon olishni unutmang!",
        "ru": "🌧️ Сегодня идет дождь. Не забудьте взять зонтик!",
        "kr": "🌧️ 오늘은 비가 옵니다. 우산 챙기는 것 잊지마세요!"
    },
    "Thunderstorm": {
        "uz": "⛈️ Momaqaldiroq bo'lmoqda. Ehtiyot bo'ling!",
        "ru": "⛈️ Гроза. Будьте осторожны!",
        "kr": "⛈️ 천둥번개가 칩니다. 조심하세요!"
    },
    "Snow": {
        "uz": "❄️ Qor yog'moqda. Issiq kiyining!",
        "ru": "❄️ Идет снег. Одевайтесь теплее!",
        "kr": "❄️ 눈이 옵니다. 따뜻하게 입으세요!"
    },
    "Mist": {
        "uz": "🌫️ Tuman tushgan. Haydovchilar ehtiyot bo'ling!",
        "ru": "🌫️ Туман. Водители, будьте осторожны!",
        "kr": "🌫️ 안개가 끼었습니다. 운전자분들 조심하세요!"
    },
    "Fog": {
        "uz": "🌫️ Tuman tushgan. Haydovchilar ehtiyot bo'ling!",
        "ru": "🌫️ Туман. Водители, будьте осторожны!",
        "kr": "🌫️ 안개가 끼었습니다. 운전자분들 조심하세요!"
    },
    "Haze": {
        "uz": "🌫️ Havo tumanli. Ehtiyot bo'ling!",
        "ru": "🌫️ Дымка. Будьте осторожны!",
        "kr": "🌫️ 연무가 끼었습니다. 조심하세요!"
    }
}

# Tillar uchun matnlar
TRANSLATIONS = {
    'uz': {
        'welcome': "🌟 **HANCOM ACADEMYning o'qituvchilar uchun davomat botiga hush kelibsiz, {name}!**\n\nQuyidagi tugmalar orqali:\n• Davomat qilishingiz\n• Statistikangizni ko'rishingiz\n• Dars jadvalingizni kiritishingiz\n• Filiallar bilan tanishishingiz mumkin",
        'stats': "📊 **Sizning statistikangiz:**",
        'no_stats': "📭 Hali davomat qilmagansiz",
        'branches': "🏢 **Mavjud filiallar:**",
        'distance_info': "📍 Barcha filiallar {distance} metr masofada aniqlanadi",
        'help': "🤖 **Botdan foydalanish qo'llanmasi:**\n\n📍 **Davomat qilish uchun:**\n• Pastdagi \"📍 Kelganimni tasdiqlash\" tugmasini bosing\n• Joylashuvingizni yuboring\n\n📊 **Statistika:**\n• \"📊 Mening statistikam\" - shaxsiy davomat tarixingiz\n\n📅 **Dars jadvali:**\n• \"📅 Dars jadvali\" - dars vaqtlaringizni kiritish\n• \"📋 Mening jadvalim\" - kiritilgan jadvallarni ko'rish\n\n🏢 **Filiallar:**\n• \"🏢 Filiallar\" - barcha mavjud filiallar ro'yxati",
        'attendance_success': "✅ **Davomat tasdiqlandi!**\n\n🏫 **Filial:** {branch}\n📅 **Sana:** {date}\n⏰ **Vaqt:** {time}\n📊 **Bu oydagi tashriflar:** {count} marta\n📏 **Masofa:** {distance:.1f} metr",
        'already_attended': "⚠️ Siz bugun **{branch}** hududida allaqachon davomatdan o'tgansiz!",
        'not_in_area': "❌ Siz belgilangan ta'lim muassasalari hududida emassiz!",
        'daily_reminder': "⏰ **Eslatma!** Bugun hali davomat qilmagansiz. Ish kuningizni boshlash uchun davomatni tasdiqlang!",
        'weekly_top': "🏆 **Haftaning eng faol o'qituvchilari:**\n\n{top_list}",
        'monthly_report': "📊 **{month} oyi uchun hisobot**\n\n{report}",
        'language_changed': "✅ Til o'zgartirildi: O'zbek tili",
        'language_prompt': "Iltimos, tilni tanlang:",
        'schedule': "📅 **Dars jadvali**\n\nQaysi filial uchun jadval kiritmoqchisiz?",
        'select_weekday': "📅 **Kunni tanlang:**",
        'select_hours': "⏰ **Soatlarni tanlang:**\n\n{hours_text}\n\nTanlagan soatlaringiz: {selected}\n\nTugatish uchun ✅ Yakunlash tugmasini bosing.",
        'my_schedule': "📋 **Mening dars jadvallarim:**\n\n{schedule_text}",
        'no_schedule': "📭 Hali dars jadvali kiritilmagan",
        'schedule_saved': "✅ Dars jadvali saqlandi!",
        'buttons': {
            'attendance': "📍 Kelganimni tasdiqlash",
            'my_stats': "📊 Mening statistikam",
            'branches': "🏢 Filiallar",
            'help': "❓ Yordam",
            'top_week': "🏆 Hafta topi",
            'language': "🌐 Til",
            'schedule': "📅 Dars jadvali",
            'my_schedule': "📋 Mening jadvalim"
        }
    },
    'ru': {
        'welcome': "🌟 **Добро пожаловать в бот для отметок HANCOM ACADEMY для учителей, {name}!**\n\nС помощью кнопок ниже вы можете:\n• Отметиться\n• Посмотреть статистику\n• Ввести расписание\n• Ознакомиться с филиалами",
        'stats': "📊 **Ваша статистика:**",
        'no_stats': "📭 Вы еще не отмечались",
        'branches': "🏢 **Доступные филиалы:**",
        'distance_info': "📍 Все филиалы определяются в радиусе {distance} метров",
        'help': "🤖 **Руководство по использованию:**\n\n📍 **Для отметки:**\n• Нажмите кнопку \"📍 Подтвердить прибытие\"\n• Отправьте свою геолокацию\n\n📊 **Статистика:**\n• \"📊 Моя статистика\" - история отметок\n\n📅 **Расписание:**\n• \"📅 Расписание\" - ввести время занятий\n• \"📋 Мое расписание\" - посмотреть расписание\n\n🏢 **Филиалы:**\n• \"🏢 Филиалы\" - список всех филиалов",
        'attendance_success': "✅ **Отметка подтверждена!**\n\n🏫 **Филиал:** {branch}\n📅 **Дата:** {date}\n⏰ **Время:** {time}\n📊 **Посещений в этом месяце:** {count}\n📏 **Расстояние:** {distance:.1f} м",
        'already_attended': "⚠️ Вы уже отмечались сегодня в филиале **{branch}**!",
        'not_in_area': "❌ Вы не находитесь в зоне учебных заведений!",
        'daily_reminder': "⏰ **Напоминание!** Вы еще не отметились сегодня. Подтвердите свое прибытие для начала рабочего дня!",
        'weekly_top': "🏆 **Самые активные учителя недели:**\n\n{top_list}",
        'monthly_report': "📊 **Отчет за {month}**\n\n{report}",
        'language_changed': "✅ Язык изменен: Русский язык",
        'language_prompt': "Пожалуйста, выберите язык:",
        'schedule': "📅 **Расписание**\n\nДля какого филиала хотите ввести расписание?",
        'select_weekday': "📅 **Выберите день:**",
        'select_hours': "⏰ **Выберите часы:**\n\n{hours_text}\n\nВыбранные часы: {selected}\n\nНажмите ✅ Готово для завершения.",
        'my_schedule': "📋 **Мое расписание:**\n\n{schedule_text}",
        'no_schedule': "📭 Расписание еще не введено",
        'schedule_saved': "✅ Расписание сохранено!",
        'buttons': {
            'attendance': "📍 Подтвердить прибытие",
            'my_stats': "📊 Моя статистика",
            'branches': "🏢 Филиалы",
            'help': "❓ Помощь",
            'top_week': "🏆 Топ недели",
            'language': "🌐 Язык",
            'schedule': "📅 Расписание",
            'my_schedule': "📋 Мое расписание"
        }
    },
    'kr': {
        'welcome': "🌟 **HANCOM ACADEMY 교사용 출석 체크 봇에 오신 것을 환영합니다, {name}!**\n\n아래 버튼을 통해:\n• 출석 체크하기\n• 내 통계 보기\n• 시간표 입력하기\n• 지점 목록 보기",
        'stats': "📊 **내 통계:**",
        'no_stats': "📭 아직 출석 체크하지 않았습니다",
        'branches': "🏢 **등록된 지점:**",
        'distance_info': "📍 모든 지점은 {distance}미터 반경 내에서 확인됩니다",
        'help': "🤖 **사용 설명서:**\n\n📍 **출석 체크 방법:**\n• 하단의 \"📍 출석 확인\" 버튼을 누르세요\n• 위치를 전송하세요\n\n📊 **통계:**\n• \"📊 내 통계\" - 개인 출석 기록\n\n📅 **시간표:**\n• \"📅 시간표\" - 수업 시간 입력\n• \"📋 내 시간표\" - 시간표 보기\n\n🏢 **지점:**\n• \"🏢 지점\" - 모든 지점 목록",
        'attendance_success': "✅ **출석이 확인되었습니다!**\n\n🏫 **지점:** {branch}\n📅 **날짜:** {date}\n⏰ **시간:** {time}\n📊 **이번 달 출석:** {count}회\n📏 **거리:** {distance:.1f}미터",
        'already_attended': "⚠️ 오늘 이미 **{branch}** 지점에서 출석 체크하셨습니다!",
        'not_in_area': "❌ 지정된 교육 기관 구역 내에 있지 않습니다!",
        'daily_reminder': "⏰ **알림!** 오늘 아직 출석 체크하지 않으셨습니다. 업무 시작을 위해 출석을 확인하세요!",
        'weekly_top': "🏆 **이번 주 가장 활발한 교사:**\n\n{top_list}",
        'monthly_report': "📊 **{month}월 보고서**\n\n{report}",
        'language_changed': "✅ 언어가 변경되었습니다: 한국어",
        'language_prompt': "언어를 선택하세요:",
        'schedule': "📅 **시간표**\n\n어느 지점의 시간표를 입력하시겠습니까?",
        'select_weekday': "📅 **요일을 선택하세요:**",
        'select_hours': "⏰ **시간을 선택하세요:**\n\n{hours_text}\n\n선택한 시간: {selected}\n\n완료하려면 ✅ 완료 버튼을 누르세요.",
        'my_schedule': "📋 **내 시간표:**\n\n{schedule_text}",
        'no_schedule': "📭 아직 시간표가 없습니다",
        'schedule_saved': "✅ 시간표가 저장되었습니다!",
        'buttons': {
            'attendance': "📍 출석 확인",
            'my_stats': "📊 내 통계",
            'branches': "🏢 지점",
            'help': "❓ 도움말",
            'top_week': "🏆 주간 TOP",
            'language': "🌐 언어",
            'schedule': "📅 시간표",
            'my_schedule': "📋 내 시간표"
        }
    }
}

# Ma'lumotlarni saqlash
daily_attendance_log = set()  # {(user_id, branch_name, date, time)}
attendance_counter = {}       # {(user_id, branch_name, month): count}
user_languages = {}           # {user_id: 'uz' or 'ru' or 'kr'}
user_ids = set()              # Barcha foydalanuvchilar ID si

# Foydalanuvchi holati (dars jadvali kiritish uchun)
user_states = {}  # {user_id: {'branch': branch, 'weekday': weekday, 'hours': []}}

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

def get_weekdays(user_id: int):
    """Foydalanuvchi tiliga mos hafta kunlari"""
    lang = user_languages.get(user_id, 'uz')
    if lang == 'uz':
        return WEEKDAYS_UZ
    elif lang == 'ru':
        return WEEKDAYS_RU
    else:
        return WEEKDAYS_KR

async def main_keyboard(user_id: int):
    """Asosiy menyu tugmalarini yaratish"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text=get_button_text(user_id, 'attendance'), request_location=True),
        KeyboardButton(text=get_button_text(user_id, 'my_stats')),
        KeyboardButton(text=get_button_text(user_id, 'schedule')),
        KeyboardButton(text=get_button_text(user_id, 'my_schedule')),
        KeyboardButton(text=get_button_text(user_id, 'branches')),
        KeyboardButton(text=get_button_text(user_id, 'top_week')),
        KeyboardButton(text=get_button_text(user_id, 'help')),
        KeyboardButton(text=get_button_text(user_id, 'language'))
    )
    builder.adjust(1, 2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

async def language_selection_keyboard():
    """Til tanlash uchun keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇰🇷 한국어", callback_data="lang_kr")
    )
    return builder.as_markup()

def format_schedule_text(user_id: int):
    """Foydalanuvchi jadvalini formatlash"""
    if user_id not in user_schedules or not user_schedules[user_id]:
        return None
    
    weekdays = get_weekdays(user_id)
    text = ""
    
    for branch, branch_data in user_schedules[user_id].items():
        text += f"\n📍 **{branch}**\n"
        for weekday_idx, hours in branch_data.items():
            if hours:
                weekday_name = weekdays[int(weekday_idx)]
                hours_str = ", ".join(hours)
                text += f"   📅 {weekday_name}: ⏰ {hours_str}\n"
    
    return text

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
        return ""
    
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
    
    # Bosimni mmHg ga o'tkazish
    pressure_mmhg = pressure * 0.750062
    
    # Tilga mos ravishda matnlar
    temp_text = "Harorat" if lang == 'uz' else "Температура" if lang == 'ru' else "기온"
    feels_text = "his qilinadi" if lang == 'uz' else "ощущается" if lang == 'ru' else "체감"
    humidity_text = "Namlik" if lang == 'uz' else "Влажность" if lang == 'ru' else "습도"
    wind_text = "Shamol" if lang == 'uz' else "Ветер" if lang == 'ru' else "바람"
    pressure_text = "Bosim" if lang == 'uz' else "Давление" if lang == 'ru' else "기압"
    recommendation_title = "Tavsiya" if lang == 'uz' else "Рекомендация" if lang == 'ru' else "추천"
    time_text = "Vaqt" if lang == 'uz' else "Время" if lang == 'ru' else "시간"
    
    message = f"""
{emoji} **Ob-havo ma'lumoti**

📍 **Joy:** {city}
🌡️ **{temp_text}:** {temp:.1f}°C ({feels_text}: {feels_like:.1f}°C)
💧 **{humidity_text}:** {humidity}%
💨 **{wind_text}:** {wind_speed:.1f} m/s
📊 **{pressure_text}:** {pressure_mmhg:.1f} mmHg

💡 **{recommendation_title}:**
{recommendation}

📅 **{time_text}:** {datetime.now(UZB_TZ).strftime('%H:%M')}
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
    
    # Yangi foydalanuvchi bo'lsa, til tanlashni so'raymiz
    if user_id not in user_languages:
        keyboard = await language_selection_keyboard()
        await message.answer(
            "Iltimos, tilni tanlang:\nПожалуйста, выберите язык:\n언어를 선택하세요:",
            reply_markup=keyboard
        )
        return
    
    # Eski foydalanuvchi bo'lsa, to'g'ridan-to'g'ri menyuga o'tamiz
    user_ids.add(user_id)
    keyboard = await main_keyboard(user_id)
    name = message.from_user.full_name
    
    await message.answer(
        get_text(user_id, 'welcome', name=name),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("lang_"))
async def set_initial_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split("_")[1]
    
    # Tilni saqlash
    user_languages[user_id] = lang
    user_ids.add(user_id)
    
    await callback.answer()
    await callback.message.delete()
    
    # Asosiy menyuni ko'rsatish
    keyboard = await main_keyboard(user_id)
    name = callback.from_user.full_name
    
    await callback.message.answer(
        get_text(user_id, 'welcome', name=name),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'🌐 Til', '🌐 Язык', '🌐 언어'}))
async def change_language(message: types.Message):
    user_id = message.from_user.id
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="change_lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="change_lang_ru"),
        InlineKeyboardButton(text="🇰🇷 한국어", callback_data="change_lang_kr")
    )
    await message.answer("Tilni tanlang / Выберите язык / 언어를 선택하세요:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("change_lang_"))
async def set_changed_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split("_")[2]
    user_languages[user_id] = lang
    
    await callback.answer()
    await callback.message.delete()
    
    keyboard = await main_keyboard(user_id)
    await callback.message.answer(
        get_text(user_id, 'language_changed'),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# --- DARS JADVALI HANDLERLARI ---
@dp.message(F.text.in_({'📅 Dars jadvali', '📅 Расписание', '📅 시간표'}))
async def schedule_start(message: types.Message):
    """Dars jadvali kiritishni boshlash"""
    user_id = message.from_user.id
    
    # Filial tanlash uchun tugmalar
    builder = InlineKeyboardBuilder()
    for branch in LOCATIONS:
        builder.row(InlineKeyboardButton(
            text=branch['name'],
            callback_data=f"sch_branch_{branch['name']}"
        ))
    builder.row(InlineKeyboardButton(
        text="✅ Yakunlash" if user_languages.get(user_id) == 'uz' else 
             "✅ Готово" if user_languages.get(user_id) == 'ru' else "✅ 완료",
        callback_data="sch_done"
    ))
    
    await message.answer(
        get_text(user_id, 'schedule'),
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("sch_branch_"))
async def schedule_select_branch(callback: types.CallbackQuery):
    """Filial tanlanganda"""
    user_id = callback.from_user.id
    branch = callback.data.replace("sch_branch_", "")
    
    # Holatni saqlash
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['branch'] = branch
    
    # Kun tanlash uchun tugmalar
    weekdays = get_weekdays(user_id)
    builder = InlineKeyboardBuilder()
    for i, day in enumerate(weekdays):
        builder.row(InlineKeyboardButton(
            text=day,
            callback_data=f"sch_weekday_{i}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga" if user_languages.get(user_id) == 'uz' else 
             "🔙 Назад" if user_languages.get(user_id) == 'ru' else "🔙 뒤로",
        callback_data="sch_back_to_branches"
    ))
    
    await callback.message.edit_text(
        get_text(user_id, 'select_weekday'),
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("sch_weekday_"))
async def schedule_select_weekday(callback: types.CallbackQuery):
    """Kun tanlanganda"""
    user_id = callback.from_user.id
    weekday = callback.data.replace("sch_weekday_", "")
    
    # Holatni saqlash
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['weekday'] = weekday
    if 'hours' not in user_states[user_id]:
        user_states[user_id]['hours'] = []
    
    # Mavjud soatlarni olish
    branch = user_states[user_id]['branch']
    existing_hours = user_schedules[user_id][branch][weekday] if branch in user_schedules[user_id] and weekday in user_schedules[user_id][branch] else []
    user_states[user_id]['hours'] = existing_hours.copy()
    
    # Soat tanlash uchun tugmalar
    await show_hours_selection(callback.message, user_id)

async def show_hours_selection(message: types.Message, user_id: int):
    """Soat tanlash tugmalarini ko'rsatish"""
    state = user_states[user_id]
    selected = state['hours']
    
    # Tanlangan soatlarni formatlash
    selected_text = ", ".join(selected) if selected else "—"
    
    # Soat tugmalarini yaratish (3 qator)
    builder = InlineKeyboardBuilder()
    
    # Soatlarni 3 tadan qilib joylashtirish
    for i in range(0, len(HOURS_LIST), 3):
        row_hours = HOURS_LIST[i:i+3]
        row_buttons = []
        for hour in row_hours:
            # Agar soat tanlangan bo'lsa, ✅ belgisi qo'shamiz
            btn_text = f"✅ {hour}" if hour in selected else hour
            row_buttons.append(InlineKeyboardButton(
                text=btn_text,
                callback_data=f"sch_hour_{hour}"
            ))
        builder.row(*row_buttons)
    
    # Tugatish va orqaga tugmalari
    builder.row(
        InlineKeyboardButton(
            text="✅ Tugatish" if user_languages.get(user_id) == 'uz' else 
                 "✅ Готово" if user_languages.get(user_id) == 'ru' else "✅ 완료",
            callback_data="sch_save_weekday"
        ),
        InlineKeyboardButton(
            text="🔙 Orqaga" if user_languages.get(user_id) == 'uz' else 
                 "🔙 Назад" if user_languages.get(user_id) == 'ru' else "🔙 뒤로",
            callback_data="sch_back_to_weekdays"
        )
    )
    
    hours_text = "Soatlar:" if user_languages.get(user_id) == 'uz' else "Часы:" if user_languages.get(user_id) == 'ru' else "시간:"
    
    await message.edit_text(
        get_text(user_id, 'select_hours', hours_text=hours_text, selected=selected_text),
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("sch_hour_"))
async def schedule_toggle_hour(callback: types.CallbackQuery):
    """Soat tanlash yoki olib tashlash"""
    user_id = callback.from_user.id
    hour = callback.data.replace("sch_hour_", "")
    
    if user_id not in user_states:
        await callback.answer("Xatolik yuz berdi")
        return
    
    state = user_states[user_id]
    if 'hours' not in state:
        state['hours'] = []
    
    # Soatni qo'shish yoki olib tashlash
    if hour in state['hours']:
        state['hours'].remove(hour)
    else:
        state['hours'].append(hour)
    
    # Tugmalarni yangilash
    await show_hours_selection(callback.message, user_id)
    await callback.answer()

@dp.callback_query(F.data == "sch_save_weekday")
async def schedule_save_weekday(callback: types.CallbackQuery):
    """Kun uchun soatlarni saqlash"""
    user_id = callback.from_user.id
    
    if user_id not in user_states:
        await callback.answer("Xatolik yuz berdi")
        return
    
    state = user_states[user_id]
    branch = state['branch']
    weekday = state['weekday']
    hours = state['hours']
    
    # Ma'lumotlarni saqlash
    user_schedules[user_id][branch][weekday] = hours
    
    # Yangi kun tanlash uchun qaytish
    weekdays = get_weekdays(user_id)
    builder = InlineKeyboardBuilder()
    for i, day in enumerate(weekdays):
        # Agar shu kun uchun soatlar kiritilgan bo'lsa, ✅ belgisi qo'shamiz
        has_hours = branch in user_schedules[user_id] and str(i) in user_schedules[user_id][branch]
        btn_text = f"✅ {day}" if has_hours else day
        builder.row(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"sch_weekday_{i}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga" if user_languages.get(user_id) == 'uz' else 
             "🔙 Назад" if user_languages.get(user_id) == 'ru' else "🔙 뒤로",
        callback_data="sch_back_to_branches"
    ))
    
    await callback.message.edit_text(
        get_text(user_id, 'select_weekday'),
        reply_markup=builder.as_markup()
    )
    await callback.answer(get_text(user_id, 'schedule_saved'))

@dp.callback_query(F.data == "sch_back_to_weekdays")
async def schedule_back_to_weekdays(callback: types.CallbackQuery):
    """Kun tanlashga qaytish"""
    user_id = callback.from_user.id
    
    if user_id not in user_states:
        await callback.answer("Xatolik yuz berdi")
        return
    
    state = user_states[user_id]
    branch = state['branch']
    
    weekdays = get_weekdays(user_id)
    builder = InlineKeyboardBuilder()
    for i, day in enumerate(weekdays):
        # Agar shu kun uchun soatlar kiritilgan bo'lsa, ✅ belgisi qo'shamiz
        has_hours = branch in user_schedules[user_id] and str(i) in user_schedules[user_id][branch]
        btn_text = f"✅ {day}" if has_hours else day
        builder.row(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"sch_weekday_{i}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga" if user_languages.get(user_id) == 'uz' else 
             "🔙 Назад" if user_languages.get(user_id) == 'ru' else "🔙 뒤로",
        callback_data="sch_back_to_branches"
    ))
    
    await callback.message.edit_text(
        get_text(user_id, 'select_weekday'),
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data == "sch_back_to_branches")
async def schedule_back_to_branches(callback: types.CallbackQuery):
    """Filial tanlashga qaytish"""
    user_id = callback.from_user.id
    
    builder = InlineKeyboardBuilder()
    for branch in LOCATIONS:
        # Agar shu filial uchun jadval kiritilgan bo'lsa, ✅ belgisi qo'shamiz
        has_schedule = user_id in user_schedules and branch['name'] in user_schedules[user_id]
        btn_text = f"✅ {branch['name']}" if has_schedule else branch['name']
        builder.row(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"sch_branch_{branch['name']}"
        ))
    builder.row(InlineKeyboardButton(
        text="✅ Yakunlash" if user_languages.get(user_id) == 'uz' else 
             "✅ Готово" if user_languages.get(user_id) == 'ru' else "✅ 완료",
        callback_data="sch_done"
    ))
    
    await callback.message.edit_text(
        get_text(user_id, 'schedule'),
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data == "sch_done")
async def schedule_done(callback: types.CallbackQuery):
    """Dars jadvali kiritishni tugatish"""
    user_id = callback.from_user.id
    
    # Holatni tozalash
    if user_id in user_states:
        del user_states[user_id]
    
    await callback.message.delete()
    await callback.message.answer(
        get_text(user_id, 'schedule_saved'),
        reply_markup=await main_keyboard(user_id)
    )
    await callback.answer()

@dp.message(F.text.in_({'📋 Mening jadvalim', '📋 Мое расписание', '📋 내 시간표'}))
async def my_schedule(message: types.Message):
    """Mening jadvallarimni ko'rish"""
    user_id = message.from_user.id
    
    schedule_text = format_schedule_text(user_id)
    
    if schedule_text:
        await message.answer(
            get_text(user_id, 'my_schedule', schedule_text=schedule_text),
            parse_mode="Markdown"
        )
    else:
        await message.answer(get_text(user_id, 'no_schedule'))

# --- BOSHQA HANDLERLAR ---
@dp.message(F.text.in_({'📊 Mening statistikam', '📊 Моя статистика', '📊 내 통계'}))
async def my_stats(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    current_month = now_uzb.strftime("%Y-%m")
    
    # Foydalanuvchining barcha davomatlarini sanalar bilan saqlash
    user_attendances = defaultdict(list)  # {branch: [(date, time), ...]}
    
    for (uid, branch, date, time) in daily_attendance_log:
        if uid == user_id:
            user_attendances[branch].append((date, time))
    
    if not user_attendances:
        await message.answer(get_text(user_id, 'no_stats'), parse_mode="Markdown")
        return
    
    # Oylar bo'yicha saralash uchun
    month_names_uz = {
        "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
        "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
        "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
    }
    
    month_names_ru = {
        "01": "Январь", "02": "Февраль", "03": "Март", "04": "Апрель",
        "05": "Май", "06": "Июнь", "07": "Июль", "08": "Август",
        "09": "Сентябрь", "10": "Октябрь", "11": "Ноябрь", "12": "Декабрь"
    }
    
    month_names_kr = {
        "01": "1월", "02": "2월", "03": "3월", "04": "4월",
        "05": "5월", "06": "6월", "07": "7월", "08": "8월",
        "09": "9월", "10": "10월", "11": "11월", "12": "12월"
    }
    
    lang = user_languages.get(user_id, 'uz')
    if lang == 'uz':
        month_names = month_names_uz
        weekdays = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        current_month_text = "(joriy oy)"
    elif lang == 'ru':
        month_names = month_names_ru
        weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        current_month_text = "(текущий месяц)"
    else:  # kr
        month_names = month_names_kr
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        current_month_text = "(이번 달)"
    
    text = get_text(user_id, 'stats') + "\n\n"
    
    # Har bir filial uchun
    for branch, date_time_list in user_attendances.items():
        text += f"📍 **{branch}**\n"
        
        # Sanalarni yil-oy bo'yicha guruhlash
        dates_by_month = defaultdict(list)
        for date_str, time_str in date_time_list:
            year_month = date_str[:7]  # YYYY-MM
            dates_by_month[year_month].append((date_str, time_str))
        
        # Oylar bo'yicha chiqarish
        for year_month, month_data in sorted(dates_by_month.items(), reverse=True):
            year, month = year_month.split('-')
            month_name = month_names.get(month, month)
            
            # Agar joriy oy bo'lsa, maxsus belgi
            month_display = f"{month_name} {year}"
            if year_month == current_month:
                month_display += f" {current_month_text}"
            
            text += f"   📅 **{month_display}**\n"
            
            # Kunlar bo'yicha saralash (eng yangi birinchi)
            for date_str, time_str in sorted(month_data, reverse=True):
                date_parts = date_str.split('-')
                year, month, day = date_parts
                
                # Hafta kunini aniqlash
                date_obj = datetime(int(year), int(month), int(day), tzinfo=UZB_TZ)
                weekday = date_obj.weekday()
                weekday_name = weekdays[weekday]
                
                # Formatlash
                if lang == 'kr':
                    formatted_date = f"{year}년 {int(month):02d}월 {int(day):02d}일"
                else:
                    formatted_date = f"{int(day):02d}.{int(month):02d}.{year}"
                
                text += f"      • {formatted_date} ({weekday_name}) - ⏰ {time_str}\n"
            
            text += "\n"
        
        text += "\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({'🏢 Filiallar', '🏢 Филиалы', '🏢 지점'}))
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
    
    # Tilga mos sarlavhalar
    lang = user_languages.get(user_id, 'uz')
    if lang == 'uz':
        uni_title = "**🏛 Universitetlar:**"
        lyceum_title = "**📚 Litseylar:**"
        school_title = "**🏫 Maktablar:**"
    elif lang == 'ru':
        uni_title = "**🏛 Университеты:**"
        lyceum_title = "**📚 Лицеи:**"
        school_title = "**🏫 Школы:**"
    else:  # kr
        uni_title = "**🏛 대학교:**"
        lyceum_title = "**📚 고등학교:**"
        school_title = "**🏫 초중학교:**"
    
    if universities:
        text += f"{uni_title}\n"
        for uni in universities:
            text += f"• {uni}\n"
        text += "\n"
    
    if lyceums:
        text += f"{lyceum_title}\n"
        for lyceum in lyceums:
            text += f"• {lyceum}\n"
        text += "\n"
    
    if schools:
        text += f"{school_title}\n"
        for school in schools:
            text += f"• {school}\n"
        text += "\n"
    
    text += get_text(user_id, 'distance_info', distance=ALLOWED_DISTANCE)
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({'❓ Yordam', '❓ Помощь', '❓ 도움말'}))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        get_text(user_id, 'help', distance=ALLOWED_DISTANCE),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'🏆 Hafta topi', '🏆 Топ недели', '🏆 주간 TOP'}))
async def weekly_top(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    week_ago = now_uzb - timedelta(days=7)
    week_ago_str = week_ago.strftime("%Y-%m-%d")
    
    # Haftalik statistikani hisoblash
    weekly_stats = defaultdict(int)
    
    for (uid, branch, date, time) in daily_attendance_log:
        if date >= week_ago_str:
            weekly_stats[uid] += 1
    
    if not weekly_stats:
        # Tilga mos "ma'lumot yo'q" xabari
        lang = user_languages.get(user_id, 'uz')
        if lang == 'uz':
            no_data_msg = "📭 Bu hafta hali davomat yo'q"
        elif lang == 'ru':
            no_data_msg = "📭 На этой неделе еще нет отметок"
        else:  # kr
            no_data_msg = "📭 이번 주에는 아직 출석 기록이 없습니다"
        
        await message.answer(no_data_msg)
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

@dp.message(F.text)
async def handle_text(message: types.Message):
    """Matnli xabarlarni qayta ishlash"""
    user_id = message.from_user.id
    
    # Agar foydalanuvchi til tanlamagan bo'lsa
    if user_id not in user_languages:
        keyboard = await language_selection_keyboard()
        await message.answer(
            "Iltimos, tilni tanlang:\nПожалуйста, выберите язык:\n언어를 선택하세요:",
            reply_markup=keyboard
        )
        return

# ASOSIY LOKATSIYA HANDLERI
@dp.message(F.location)
async def handle_location(message: types.Message):
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

    # DAVOMAT QISMI
    if found_branch:
        attendance_key = (user_id, found_branch, today_date)
        
        # Tekshirish uchun (vaqtni hisobga olmasdan)
        already_attended = False
        for (uid, branch, date, time) in daily_attendance_log:
            if uid == user_id and branch == found_branch and date == today_date:
                already_attended = True
                break
        
        if already_attended:
            # Bugun allaqachon davomat qilgan
            await message.answer(
                get_text(user_id, 'already_attended', branch=found_branch),
                parse_mode="Markdown"
            )
            return

        # Yangi davomat
        counter_key = (user_id, found_branch, current_month)
        attendance_counter[counter_key] = attendance_counter.get(counter_key, 0) + 1
        visit_number = attendance_counter[counter_key]
        
        # Vaqt bilan saqlash
        daily_attendance_log.add((user_id, found_branch, today_date, now_time))
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
            # Adminga yuborish
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID, 
                text=report, 
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            
            # Foydalanuvchiga davomat xabari
            success_text = get_text(
                user_id, 
                'attendance_success',
                branch=found_branch,
                date=today_date,
                time=now_time,
                count=visit_number,
                distance=min_distance
            )
            
            # Ob-havo ma'lumotini olish va qo'shish
            weather_data = await get_weather_by_coords(user_coords[0], user_coords[1])
            weather_message = format_weather_message(weather_data, user_languages.get(user_id, 'uz'))
            
            full_response = f"{success_text}\n\n{weather_message}"
            await message.answer(full_response, parse_mode="Markdown")
            
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        # Filial topilmadi - faqat xato xabari
        await message.answer(
            get_text(user_id, 'not_in_area'),
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
        for (uid, branch, date, time) in daily_attendance_log:
            if date.startswith(current_month):
                monthly_stats[branch][uid] += 1
        
        report = f"📊 **{month_name} oyi uchun hisobot**\n\n"
        
        for branch, users in monthly_stats.items():
            total = sum(users.values())
            unique_users = len(users)
            report += f"📍 **{branch}**\n"
            report += f"   Jami: {total} ta davomat\n"
            report += f"   O'qituvchilar: {unique_users} ta\n\n"
        
        await callback.message.answer(report, parse_mode="Markdown")
    
    elif action == "excel":
        # Excel export qilish
        try:
            # Excel fayl yaratish
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Davomat"
            
            # Sarlavhalar
            headers = ["Sana", "Filial", "O'qituvchi ID", "O'qituvchi Ismi", "Vaqt"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            
            # Ma'lumotlarni yozish
            row = 2
            for (uid, branch, date, time) in sorted(daily_attendance_log):
                try:
                    user = await bot.get_chat(uid)
                    user_name = user.full_name
                except:
                    user_name = f"User_{uid}"
                
                ws.cell(row=row, column=1, value=date)
                ws.cell(row=row, column=2, value=branch)
                ws.cell(row=row, column=3, value=uid)
                ws.cell(row=row, column=4, value=user_name)
                ws.cell(row=row, column=5, value=time)
                row += 1
            
            # Faylni saqlash va yuborish
            excel_file = io.BytesIO()
            wb.save(excel_file)
            excel_file.seek(0)
            
            await callback.message.answer_document(
                types.BufferedInputFile(
                    excel_file.getvalue(),
                    filename=f"davomat_{now_uzb.strftime('%Y%m')}.xlsx"
                ),
                caption="📊 Oylik davomat hisoboti"
            )
        except Exception as e:
            logging.error(f"Excel export error: {e}")
            await callback.message.answer("❌ Excel fayl yaratishda xatolik yuz berdi.")
    
    elif action == "users":
        user_count = len(user_ids)
        active_today = len([k for k in daily_attendance_log if k[2] == now_uzb.strftime("%Y-%m-%d")])
        
        await callback.message.answer(
            f"👥 **Foydalanuvchilar statistikasi**\n\n"
            f"Jami foydalanuvchilar: {user_count}\n"
            f"Bugun faol: {active_today}",
            parse_mode="Markdown"
        )
    
    elif action == "stats":
        total_attendances = len(daily_attendance_log)
        monthly_attendances = len([k for k in daily_attendance_log if k[2].startswith(now_uzb.strftime("%Y-%m"))])
        
        await callback.message.answer(
            f"📈 **Umumiy statistika**\n\n"
            f"Jami davomatlar: {total_attendances}\n"
            f"Shu oyda: {monthly_attendances}\n"
            f"Faol filiallar: {len(set(k[1] for k in daily_attendance_log))}\n"
            f"Faol foydalanuvchilar: {len(set(k[0] for k in daily_attendance_log))}",
            parse_mode="Markdown"
        )
    
    await callback.answer()

# --- REMINDER LOOP ---
async def send_daily_reminders():
    """Har kuni soat 08:00 da eslatma yuborish"""
    now_uzb = datetime.now(UZB_TZ)
    today = now_uzb.strftime("%Y-%m-%d")
    
    # Bugun davomat qilmagan foydalanuvchilarga eslatma
    sent_count = 0
    for user_id in user_ids:
        user_attended = any(k[0] == user_id and k[2] == today for k in daily_attendance_log)
        if not user_attended:
            try:
                await bot.send_message(
                    user_id,
                    get_text(user_id, 'daily_reminder'),
                    parse_mode="Markdown"
                )
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logging.error(f"Reminder error for {user_id}: {e}")
    
    logging.info(f"Daily reminders sent: {sent_count} users")

async def reminder_loop():
    """Eslatmalar uchun doimiy loop"""
    while True:
        now_uzb = datetime.now(UZB_TZ)
        if now_uzb.hour == 8 and now_uzb.minute == 0:
            await send_daily_reminders()
            await asyncio.sleep(60)
        await asyncio.sleep(30)

# --- MAIN ---
async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(reminder_loop())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
