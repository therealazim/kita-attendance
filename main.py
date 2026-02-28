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

# Hafta kunlari
WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
WEEKDAYS_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

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
        'welcome': "🌟 **HANCOM ACADEMYning o'qituvchilar uchun davomat botiga hush kelibsiz, {name}!**\n\nQuyidagi tugmalar orqali:\n• 📅 Dars jadvalingizni yaratishingiz\n• 📍 Davomat qilishingiz\n• 📊 Statistikangizni ko'rishingiz\n• 🏢 Filiallar bilan tanishishingiz mumkin",
        'stats': "📊 **Sizning statistikangiz:**",
        'no_stats': "📭 Hali davomat qilmagansiz",
        'branches': "🏢 **Mavjud filiallar:**",
        'distance_info': "📍 Barcha filiallar {distance} metr masofada aniqlanadi",
        'help': "🤖 **Botdan foydalanish qo'llanmasi:**\n\n📅 **Dars jadvali yaratish:**\n• '📅 Mening jadvalim' tugmasini bosing\n• Darslaringizni qo'shing\n\n📍 **Davomat qilish:**\n• '📍 Davomat qilish' tugmasini bosing\n• Joylashuvingizni yuboring\n• Agar jadvalingiz bo'lsa, darsni tanlang\n\n📊 **Statistika:**\n• '📊 Mening statistikam' - shaxsiy davomat tarixingiz",
        'attendance_success': "✅ **Davomat tasdiqlandi!**\n\n🏫 **Filial:** {branch}\n📚 **Dars:** {lesson}\n📅 **Sana:** {date}\n⏰ **Vaqt:** {time}\n📊 **Bu oydagi tashriflar:** {count} marta\n📏 **Masofa:** {distance:.1f} metr",
        'already_attended': "⚠️ Siz bugun **{branch}** filialida **{lesson}** darsiga allaqachon davomat qilgansiz!",
        'not_in_area': "❌ Siz belgilangan ta'lim muassasalari hududida emassiz!",
        'no_schedule': "📭 Siz hali dars jadvalingizni yaratmadingiz. Avval jadval yarating!",
        'schedule_created': "✅ Dars jadvalingiz saqlandi! Endi davomat qilishingiz mumkin.",
        'schedule_empty': "⚠️ Jadvalingiz bo'sh. Dars qo'shing!",
        'choose_lesson': "📚 Davomat qilmoqchi bo'lgan darsingizni tanlang:",
        'add_lesson': "➕ Dars qo'shish",
        'my_schedule': "📅 Mening jadvalim",
        'lesson_name': "Dars nomi:",
        'choose_weekday': "Hafta kunini tanlang:",
        'choose_branch': "Filialni tanlang:",
        'choose_time': "Dars vaqtini kiriting (masalan: 09:00):",
        'invalid_time': "❌ Noto'g'ri vaqt formati. Qaytadan kiriting (masalan: 09:00):",
        'daily_reminder': "⏰ **Eslatma!** Bugun darslaringiz bor. Davomat qilishni unutmang!",
        'weekly_top': "🏆 **Haftaning eng faol o'qituvchilari:**\n\n{top_list}",
        'monthly_report': "📊 **{month} oyi uchun hisobot**\n\n{report}",
        'language_changed': "✅ Til o'zgartirildi: O'zbek tili",
        'language_prompt': "Iltimos, tilni tanlang:",
        'buttons': {
            'attendance': "📍 Davomat qilish",
            'my_stats': "📊 Mening statistikam",
            'branches': "🏢 Filiallar",
            'help': "❓ Yordam",
            'top_week': "🏆 Hafta topi",
            'language': "🌐 Til",
            'my_schedule': "📅 Mening jadvalim",
            'add_lesson': "➕ Dars qo'shish"
        }
    },
    'ru': {
        'welcome': "🌟 **Добро пожаловать в бот для отметок HANCOM ACADEMY для учителей, {name}!**\n\nС помощью кнопок ниже вы можете:\n• 📅 Создать расписание\n• 📍 Отметиться\n• 📊 Посмотреть статистику\n• 🏢 Ознакомиться с филиалами",
        'stats': "📊 **Ваша статистика:**",
        'no_stats': "📭 Вы еще не отмечались",
        'branches': "🏢 **Доступные филиалы:**",
        'distance_info': "📍 Все филиалы определяются в радиусе {distance} метров",
        'help': "🤖 **Руководство по использованию:**\n\n📅 **Создание расписания:**\n• Нажмите '📅 Мое расписание'\n• Добавьте уроки\n\n📍 **Отметка:**\n• Нажмите '📍 Отметиться'\n• Отправьте геолокацию\n• Выберите урок из расписания\n\n📊 **Статистика:**\n• '📊 Моя статистика' - история отметок",
        'attendance_success': "✅ **Отметка подтверждена!**\n\n🏫 **Филиал:** {branch}\n📚 **Урок:** {lesson}\n📅 **Дата:** {date}\n⏰ **Время:** {time}\n📊 **Посещений в этом месяце:** {count}\n📏 **Расстояние:** {distance:.1f} м",
        'already_attended': "⚠️ Вы уже отмечались сегодня в филиале **{branch}** на уроке **{lesson}**!",
        'not_in_area': "❌ Вы не находитесь в зоне учебных заведений!",
        'no_schedule': "📭 У вас еще нет расписания. Сначала создайте расписание!",
        'schedule_created': "✅ Ваше расписание сохранено! Теперь вы можете отмечаться.",
        'schedule_empty': "⚠️ Ваше расписание пусто. Добавьте урок!",
        'choose_lesson': "📚 Выберите урок для отметки:",
        'add_lesson': "➕ Добавить урок",
        'my_schedule': "📅 Мое расписание",
        'lesson_name': "Название урока:",
        'choose_weekday': "Выберите день недели:",
        'choose_branch': "Выберите филиал:",
        'choose_time': "Введите время урока (например: 09:00):",
        'invalid_time': "❌ Неверный формат времени. Введите заново (например: 09:00):",
        'daily_reminder': "⏰ **Напоминание!** Сегодня у вас есть уроки. Не забудьте отметиться!",
        'weekly_top': "🏆 **Самые активные учителя недели:**\n\n{top_list}",
        'monthly_report': "📊 **Отчет за {month}**\n\n{report}",
        'language_changed': "✅ Язык изменен: Русский язык",
        'language_prompt': "Пожалуйста, выберите язык:",
        'buttons': {
            'attendance': "📍 Отметиться",
            'my_stats': "📊 Моя статистика",
            'branches': "🏢 Филиалы",
            'help': "❓ Помощь",
            'top_week': "🏆 Топ недели",
            'language': "🌐 Язык",
            'my_schedule': "📅 Мое расписание",
            'add_lesson': "➕ Добавить урок"
        }
    },
    'kr': {
        'welcome': "🌟 **HANCOM ACADEMY 교사용 출석 체크 봇에 오신 것을 환영합니다, {name}!**\n\n아래 버튼을 통해:\n• 📅 시간표 만들기\n• 📍 출석 체크하기\n• 📊 내 통계 보기\n• 🏢 지점 목록 보기",
        'stats': "📊 **내 통계:**",
        'no_stats': "📭 아직 출석 체크하지 않았습니다",
        'branches': "🏢 **등록된 지점:**",
        'distance_info': "📍 모든 지점은 {distance}미터 반경 내에서 확인됩니다",
        'help': "🤖 **사용 설명서:**\n\n📅 **시간표 만들기:**\n• '📅 내 시간표' 버튼을 누르세요\n• 수업을 추가하세요\n\n📍 **출석 체크:**\n• '📍 출석 체크' 버튼을 누르세요\n• 위치를 전송하세요\n• 시간표에서 수업을 선택하세요\n\n📊 **통계:**\n• '📊 내 통계' - 개인 출석 기록",
        'attendance_success': "✅ **출석이 확인되었습니다!**\n\n🏫 **지점:** {branch}\n📚 **수업:** {lesson}\n📅 **날짜:** {date}\n⏰ **시간:** {time}\n📊 **이번 달 출석:** {count}회\n📏 **거리:** {distance:.1f}미터",
        'already_attended': "⚠️ 오늘 이미 **{branch}** 지점에서 **{lesson}** 수업에 출석하셨습니다!",
        'not_in_area': "❌ 지정된 교육 기관 구역 내에 있지 않습니다!",
        'no_schedule': "📭 아직 시간표가 없습니다. 먼저 시간표를 만들어주세요!",
        'schedule_created': "✅ 시간표가 저장되었습니다! 이제 출석 체크할 수 있습니다.",
        'schedule_empty': "⚠️ 시간표가 비어있습니다. 수업을 추가하세요!",
        'choose_lesson': "📚 출석 체크할 수업을 선택하세요:",
        'add_lesson': "➕ 수업 추가",
        'my_schedule': "📅 내 시간표",
        'lesson_name': "수업 이름:",
        'choose_weekday': "요일을 선택하세요:",
        'choose_branch': "지점을 선택하세요:",
        'choose_time': "수업 시간을 입력하세요 (예: 09:00):",
        'invalid_time': "❌ 잘못된 시간 형식입니다. 다시 입력하세요 (예: 09:00):",
        'daily_reminder': "⏰ **알림!** 오늘 수업이 있습니다. 출석 체크를 잊지마세요!",
        'weekly_top': "🏆 **이번 주 가장 활발한 교사:**\n\n{top_list}",
        'monthly_report': "📊 **{month}월 보고서**\n\n{report}",
        'language_changed': "✅ 언어가 변경되었습니다: 한국어",
        'language_prompt': "언어를 선택하세요:",
        'buttons': {
            'attendance': "📍 출석 체크",
            'my_stats': "📊 내 통계",
            'branches': "🏢 지점",
            'help': "❓ 도움말",
            'top_week': "🏆 주간 TOP",
            'language': "🌐 언어",
            'my_schedule': "📅 내 시간표",
            'add_lesson': "➕ 수업 추가"
        }
    }
}

# Foydalanuvchi ma'lumotlari
user_data = {
    'languages': {},           # {user_id: 'uz' or 'ru' or 'kr'}
    'schedules': {},           # {user_id: [{'lesson': str, 'weekday': int, 'branch': str, 'time': str}]}
    'attendance_log': set(),   # {(user_id, branch, lesson, date, time)}
    'attendance_counter': {},  # {(user_id, branch, lesson, month): count}
    'user_ids': set()          # Barcha foydalanuvchilar ID si
}

# FSM holatlari
class ScheduleState:
    waiting_for_lesson_name = "waiting_for_lesson_name"
    waiting_for_weekday = "waiting_for_weekday"
    waiting_for_branch = "waiting_for_branch"
    waiting_for_time = "waiting_for_time"

user_states = {}  # {user_id: state}
temp_schedule = {}  # {user_id: {'lesson': '', 'weekday': '', 'branch': '', 'time': ''}}

# --- YORDAMCHI FUNKSIYALAR ---
def get_text(user_id: int, key: str, **kwargs):
    """Foydalanuvchi tiliga mos matn qaytarish"""
    lang = user_data['languages'].get(user_id, 'uz')
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS['uz'].get(key, ''))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text

def get_button_text(user_id: int, button_key: str):
    """Foydalanuvchi tiliga mos tugma matni qaytarish"""
    lang = user_data['languages'].get(user_id, 'uz')
    return TRANSLATIONS[lang]['buttons'][button_key]

def get_weekdays(user_id: int):
    """Foydalanuvchi tiliga mos hafta kunlari"""
    lang = user_data['languages'].get(user_id, 'uz')
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
        KeyboardButton(text=get_button_text(user_id, 'my_schedule')),
        KeyboardButton(text=get_button_text(user_id, 'my_stats')),
        KeyboardButton(text=get_button_text(user_id, 'branches')),
        KeyboardButton(text=get_button_text(user_id, 'top_week')),
        KeyboardButton(text=get_button_text(user_id, 'help')),
        KeyboardButton(text=get_button_text(user_id, 'language'))
    )
    builder.adjust(1, 2, 2, 2)
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

def get_weekday_keyboard(user_id: int):
    """Hafta kunlari uchun keyboard"""
    weekdays = get_weekdays(user_id)
    builder = ReplyKeyboardBuilder()
    for day in weekdays:
        builder.add(KeyboardButton(text=day))
    builder.add(KeyboardButton(text="🔙 Bekor qilish" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Отмена" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 취소"))
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_branch_keyboard(user_id: int):
    """Filiallar uchun keyboard"""
    builder = ReplyKeyboardBuilder()
    for branch in LOCATIONS:
        builder.add(KeyboardButton(text=branch['name']))
    builder.add(KeyboardButton(text="🔙 Bekor qilish" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Отмена" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 취소"))
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_schedule_keyboard(user_id: int):
    """Foydalanuvchi jadvalidagi darslar uchun keyboard"""
    schedule = user_data['schedules'].get(user_id, [])
    if not schedule:
        return None
    
    weekdays = get_weekdays(user_id)
    builder = ReplyKeyboardBuilder()
    for lesson in schedule:
        weekday_name = weekdays[lesson['weekday']]
        button_text = f"{lesson['lesson']} | {weekday_name} | {lesson['time']}"
        builder.add(KeyboardButton(text=button_text))
    builder.add(KeyboardButton(text="🔙 Bekor qilish" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Отмена" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 취소"))
    builder.adjust(1)
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
             f"👥 Foydalanuvchilar: {len(user_data['user_ids'])} ta\n"
             f"📊 Bugungi davomatlar: {len([k for k in user_data['attendance_log'] if k[3] == now_uzb.strftime('%Y-%m-%d')])} ta"
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
    if user_id not in user_data['languages']:
        keyboard = await language_selection_keyboard()
        await message.answer(
            "Iltimos, tilni tanlang:\nПожалуйста, выберите язык:\n언어를 선택하세요:",
            reply_markup=keyboard
        )
        return
    
    # Eski foydalanuvchi bo'lsa, to'g'ridan-to'g'ri menyuga o'tamiz
    user_data['user_ids'].add(user_id)
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
    user_data['languages'][user_id] = lang
    user_data['user_ids'].add(user_id)
    
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
    user_data['languages'][user_id] = lang
    
    await callback.answer()
    await callback.message.delete()
    
    keyboard = await main_keyboard(user_id)
    await callback.message.answer(
        get_text(user_id, 'language_changed'),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# --- JADVAL HANDLERLARI ---
@dp.message(F.text.in_({'📅 Mening jadvalim', '📅 Мое расписание', '📅 내 시간표'}))
async def my_schedule(message: types.Message):
    user_id = message.from_user.id
    schedule = user_data['schedules'].get(user_id, [])
    
    if not schedule:
        # Jadval bo'sh bo'lsa, dars qo'shishni taklif qilamiz
        builder = ReplyKeyboardBuilder()
        builder.add(KeyboardButton(text=get_button_text(user_id, 'add_lesson')))
        builder.add(KeyboardButton(text="🔙 Orqaga" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Назад" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 뒤로"))
        await message.answer(
            get_text(user_id, 'schedule_empty'),
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        return
    
    # Jadvalni ko'rsatish
    weekdays = get_weekdays(user_id)
    text = f"**{get_text(user_id, 'my_schedule')}**\n\n"
    
    # Hafta kunlari bo'yicha guruhlash
    by_weekday = defaultdict(list)
    for lesson in schedule:
        by_weekday[lesson['weekday']].append(lesson)
    
    for weekday in range(7):
        if by_weekday[weekday]:
            text += f"**{weekdays[weekday]}:**\n"
            for lesson in sorted(by_weekday[weekday], key=lambda x: x['time']):
                text += f"   • {lesson['lesson']} | {lesson['branch']} | {lesson['time']}\n"
            text += "\n"
    
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=get_button_text(user_id, 'add_lesson')))
    builder.add(KeyboardButton(text="🔙 Orqaga" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Назад" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 뒤로"))
    
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.text.in_({'➕ Dars qo\'shish', '➕ Добавить урок', '➕ 수업 추가'}))
async def add_lesson_start(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = ScheduleState.waiting_for_lesson_name
    temp_schedule[user_id] = {}
    
    await message.answer(
        get_text(user_id, 'lesson_name'),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Bekor qilish" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Отмена" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 취소")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🔙 Bekor qilish" or F.text == "🔙 Отмена" or F.text == "🔙 취소" or F.text == "🔙 Orqaga" or F.text == "🔙 Назад" or F.text == "🔙 뒤로")
async def cancel_action(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_schedule:
        del temp_schedule[user_id]
    
    keyboard = await main_keyboard(user_id)
    await message.answer("Bekor qilindi / Отменено / 취소됨", reply_markup=keyboard)

@dp.message(F.text)
async def handle_schedule_input(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == ScheduleState.waiting_for_lesson_name:
        temp_schedule[user_id]['lesson'] = message.text
        user_states[user_id] = ScheduleState.waiting_for_weekday
        
        await message.answer(
            get_text(user_id, 'choose_weekday'),
            reply_markup=get_weekday_keyboard(user_id)
        )
    
    elif state == ScheduleState.waiting_for_weekday:
        weekdays = get_weekdays(user_id)
        if message.text in weekdays:
            temp_schedule[user_id]['weekday'] = weekdays.index(message.text)
            user_states[user_id] = ScheduleState.waiting_for_branch
            
            await message.answer(
                get_text(user_id, 'choose_branch'),
                reply_markup=get_branch_keyboard(user_id)
            )
        else:
            await message.answer("❌ Noto'g'ri tanlov / Неверный выбор / 잘못된 선택")
    
    elif state == ScheduleState.waiting_for_branch:
        branch_names = [b['name'] for b in LOCATIONS]
        if message.text in branch_names:
            temp_schedule[user_id]['branch'] = message.text
            user_states[user_id] = ScheduleState.waiting_for_time
            
            await message.answer(
                get_text(user_id, 'choose_time'),
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="🔙 Bekor qilish" if user_data['languages'].get(user_id, 'uz') == 'uz' else "🔙 Отмена" if user_data['languages'].get(user_id, 'uz') == 'ru' else "🔙 취소")]],
                    resize_keyboard=True
                )
            )
        else:
            await message.answer("❌ Noto'g'ri filial / Неверный филиал / 잘못된 지점")
    
    elif state == ScheduleState.waiting_for_time:
        # Vaqt formatini tekshirish (HH:MM)
        import re
        if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', message.text):
            temp_schedule[user_id]['time'] = message.text
            
            # Jadvalga qo'shish
            if user_id not in user_data['schedules']:
                user_data['schedules'][user_id] = []
            
            user_data['schedules'][user_id].append({
                'lesson': temp_schedule[user_id]['lesson'],
                'weekday': temp_schedule[user_id]['weekday'],
                'branch': temp_schedule[user_id]['branch'],
                'time': temp_schedule[user_id]['time']
            })
            
            del user_states[user_id]
            del temp_schedule[user_id]
            
            keyboard = await main_keyboard(user_id)
            await message.answer(
                get_text(user_id, 'schedule_created'),
                reply_markup=keyboard
            )
        else:
            await message.answer(get_text(user_id, 'invalid_time'))

# --- DAVOMAT HANDLERI ---
@dp.message(F.text.in_({'📍 Davomat qilish', '📍 Отметиться', '📍 출석 체크'}))
async def attendance_button(message: types.Message):
    user_id = message.from_user.id
    
    # Foydalanuvchi jadvali bormi?
    schedule = user_data['schedules'].get(user_id, [])
    if not schedule:
        await message.answer(get_text(user_id, 'no_schedule'))
        return
    
    # Bugungi hafta kunini aniqlash
    now_uzb = datetime.now(UZB_TZ)
    today_weekday = now_uzb.weekday()  # 0-Dushanba, 6-Yakshanba
    
    # Bugungi darslarni filtrlash
    today_lessons = [l for l in schedule if l['weekday'] == today_weekday]
    
    if not today_lessons:
        await message.answer("📭 Bugun darslaringiz yo'q")
        return
    
    # Foydalanuvchi holatiga bugungi darslarni saqlash
    user_states[user_id] = "waiting_attendance_location"
    temp_schedule[user_id] = {'lessons': today_lessons}
    
    await message.answer(
        "📍 Iltimos, joylashuvingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)]],
            resize_keyboard=True
        )
    )

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_states or user_states[user_id] != "waiting_attendance_location":
        # Agar davomat kutilmagan bo'lsa, xabar bermaymiz
        return
    
    now_uzb = datetime.now(UZB_TZ)
    today_date = now_uzb.strftime("%Y-%m-%d")
    current_month = now_uzb.strftime("%Y-%m")
    now_time = now_uzb.strftime("%H:%M:%S")

    user_coords = (message.location.latitude, message.location.longitude)
    
    # Lokatsiya bo'yicha filialni aniqlash
    found_branch = None
    min_distance = float('inf')
    
    for branch in LOCATIONS:
        dist = geodesic((branch["lat"], branch["lon"]), user_coords).meters
        if dist <= ALLOWED_DISTANCE:
            if dist < min_distance:
                min_distance = dist
                found_branch = branch["name"]
    
    if not found_branch:
        await message.answer(get_text(user_id, 'not_in_area'))
        del user_states[user_id]
        if user_id in temp_schedule:
            del temp_schedule[user_id]
        return
    
    # Bugungi darslardan filialga mosini topish
    today_lessons = temp_schedule[user_id]['lessons']
    matching_lessons = [l for l in today_lessons if l['branch'] == found_branch]
    
    if not matching_lessons:
        await message.answer(f"❌ Siz {found_branch} filialidasiz, lekin bugungi darslaringiz bu yerda emas.")
        del user_states[user_id]
        del temp_schedule[user_id]
        return
    
    # Agar bir nechta dars bo'lsa, tanlashni so'rash
    if len(matching_lessons) > 1:
        user_states[user_id] = "choosing_lesson"
        temp_schedule[user_id]['location'] = {
            'coords': user_coords,
            'branch': found_branch,
            'distance': min_distance
        }
        
        builder = ReplyKeyboardBuilder()
        for lesson in matching_lessons:
            builder.add(KeyboardButton(text=f"{lesson['lesson']} ({lesson['time']})"))
        builder.add(KeyboardButton(text="🔙 Bekor qilish"))
        builder.adjust(1)
        
        await message.answer(
            get_text(user_id, 'choose_lesson'),
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        return
    
    # Bitta dars bo'lsa, to'g'ridan-to'g'ri davomat
    lesson = matching_lessons[0]
    
    # Davomatni tekshirish
    attendance_key = (user_id, found_branch, lesson['lesson'], today_date)
    already_attended = any(k[0] == user_id and k[1] == found_branch and k[2] == lesson['lesson'] and k[3] == today_date for k in user_data['attendance_log'])
    
    if already_attended:
        await message.answer(
            get_text(user_id, 'already_attended', branch=found_branch, lesson=lesson['lesson'])
        )
        del user_states[user_id]
        del temp_schedule[user_id]
        return
    
    # Yangi davomat
    counter_key = (user_id, found_branch, lesson['lesson'], current_month)
    user_data['attendance_counter'][counter_key] = user_data['attendance_counter'].get(counter_key, 0) + 1
    visit_number = user_data['attendance_counter'][counter_key]
    
    user_data['attendance_log'].add((user_id, found_branch, lesson['lesson'], today_date, now_time))
    full_name = message.from_user.full_name
    
    # Admin guruhiga hisobot
    report = (
        f"✅ **Yangi Davomat**\n\n"
        f"👤 **O'qituvchi:** {full_name}\n"
        f"📍 **Manzil:** {found_branch}\n"
        f"📚 **Dars:** {lesson['lesson']}\n"
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
        
        # Foydalanuvchiga davomat xabari
        success_text = get_text(
            user_id,
            'attendance_success',
            branch=found_branch,
            lesson=lesson['lesson'],
            date=today_date,
            time=now_time,
            count=visit_number,
            distance=min_distance
        )
        
        # Ob-havo ma'lumotini olish va qo'shish
        weather_data = await get_weather_by_coords(user_coords[0], user_coords[1])
        weather_message = format_weather_message(weather_data, user_data['languages'].get(user_id, 'uz'))
        
        full_response = f"{success_text}\n\n{weather_message}"
        await message.answer(full_response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error: {e}")
    
    del user_states[user_id]
    del temp_schedule[user_id]
    
    # Asosiy menyuga qaytish
    keyboard = await main_keyboard(user_id)
    await message.answer("Asosiy menyu:", reply_markup=keyboard)

@dp.message(F.text)
async def handle_lesson_choice(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_states or user_states[user_id] != "choosing_lesson":
        return
    
    if message.text == "🔙 Bekor qilish":
        del user_states[user_id]
        del temp_schedule[user_id]
        keyboard = await main_keyboard(user_id)
        await message.answer("Bekor qilindi", reply_markup=keyboard)
        return
    
    # Tanlangan darsni topish
    selected_lesson = None
    for lesson in temp_schedule[user_id]['lessons']:
        if message.text.startswith(lesson['lesson']):
            selected_lesson = lesson
            break
    
    if not selected_lesson:
        await message.answer("❌ Noto'g'ri tanlov")
        return
    
    location_data = temp_schedule[user_id]['location']
    now_uzb = datetime.now(UZB_TZ)
    today_date = now_uzb.strftime("%Y-%m-%d")
    current_month = now_uzb.strftime("%Y-%m")
    now_time = now_uzb.strftime("%H:%M:%S")
    
    # Davomatni tekshirish
    already_attended = any(k[0] == user_id and k[1] == location_data['branch'] and k[2] == selected_lesson['lesson'] and k[3] == today_date for k in user_data['attendance_log'])
    
    if already_attended:
        await message.answer(
            get_text(user_id, 'already_attended', branch=location_data['branch'], lesson=selected_lesson['lesson'])
        )
        del user_states[user_id]
        del temp_schedule[user_id]
        return
    
    # Yangi davomat
    counter_key = (user_id, location_data['branch'], selected_lesson['lesson'], current_month)
    user_data['attendance_counter'][counter_key] = user_data['attendance_counter'].get(counter_key, 0) + 1
    visit_number = user_data['attendance_counter'][counter_key]
    
    user_data['attendance_log'].add((user_id, location_data['branch'], selected_lesson['lesson'], today_date, now_time))
    full_name = message.from_user.full_name
    
    # Admin guruhiga hisobot
    report = (
        f"✅ **Yangi Davomat**\n\n"
        f"👤 **O'qituvchi:** {full_name}\n"
        f"📍 **Manzil:** {location_data['branch']}\n"
        f"📚 **Dars:** {selected_lesson['lesson']}\n"
        f"📅 **Sana:** {today_date}\n"
        f"⏰ **Vaqt:** {now_time}\n"
        f"🔢 **Shu oydagi tashrif:** {visit_number}-marta\n"
        f"📏 **Masofa:** {location_data['distance']:.1f} metr"
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
        
        # Foydalanuvchiga davomat xabari
        success_text = get_text(
            user_id,
            'attendance_success',
            branch=location_data['branch'],
            lesson=selected_lesson['lesson'],
            date=today_date,
            time=now_time,
            count=visit_number,
            distance=location_data['distance']
        )
        
        # Ob-havo ma'lumotini olish va qo'shish
        weather_data = await get_weather_by_coords(location_data['coords'][0], location_data['coords'][1])
        weather_message = format_weather_message(weather_data, user_data['languages'].get(user_id, 'uz'))
        
        full_response = f"{success_text}\n\n{weather_message}"
        await message.answer(full_response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error: {e}")
    
    del user_states[user_id]
    del temp_schedule[user_id]
    
    # Asosiy menyuga qaytish
    keyboard = await main_keyboard(user_id)
    await message.answer("Asosiy menyu:", reply_markup=keyboard)

@dp.message(F.text.in_({'📊 Mening statistikam', '📊 Моя статистика', '📊 내 통계'}))
async def my_stats(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    current_month = now_uzb.strftime("%Y-%m")
    
    # Foydalanuvchining barcha davomatlarini sanalar bilan saqlash
    user_attendances = defaultdict(list)  # {branch: [(lesson, date, time), ...]}
    
    for (uid, branch, lesson, date, time) in user_data['attendance_log']:
        if uid == user_id:
            user_attendances[branch].append((lesson, date, time))
    
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
    
    lang = user_data['languages'].get(user_id, 'uz')
    if lang == 'uz':
        month_names = month_names_uz
        weekdays = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        current_month_text = "(joriy oy)"
        date_format = "{day:02d}.{month:02d}.{year}"
    elif lang == 'ru':
        month_names = month_names_ru
        weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        current_month_text = "(текущий месяц)"
        date_format = "{day:02d}.{month:02d}.{year}"
    else:  # kr
        month_names = month_names_kr
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        current_month_text = "(이번 달)"
        date_format = "{year}년 {month:02d}월 {day:02d}일"
    
    text = get_text(user_id, 'stats') + "\n\n"
    
    # Har bir filial uchun
    for branch, lesson_list in user_attendances.items():
        text += f"📍 **{branch}**\n"
        
        # Darslar bo'yicha guruhlash
        lessons_by_month = defaultdict(lambda: defaultdict(list))
        for lesson, date_str, time_str in lesson_list:
            year_month = date_str[:7]
            lessons_by_month[year_month][lesson].append((date_str, time_str))
        
        # Oylar bo'yicha chiqarish
        for year_month, lessons in sorted(lessons_by_month.items(), reverse=True):
            year, month = year_month.split('-')
            month_name = month_names.get(month, month)
            
            month_display = f"{month_name} {year}"
            if year_month == current_month:
                month_display += f" {current_month_text}"
            
            text += f"   📅 **{month_display}**\n"
            
            for lesson, dates in lessons.items():
                text += f"      📚 **{lesson}**\n"
                for date_str, time_str in sorted(dates, reverse=True):
                    date_parts = date_str.split('-')
                    year, month, day = date_parts
                    
                    date_obj = datetime(int(year), int(month), int(day), tzinfo=UZB_TZ)
                    weekday = date_obj.weekday()
                    weekday_name = weekdays[weekday]
                    
                    if lang == 'kr':
                        formatted_date = f"{year}년 {int(month):02d}월 {int(day):02d}일"
                    else:
                        formatted_date = f"{int(day):02d}.{int(month):02d}.{year}"
                    
                    text += f"         • {formatted_date} ({weekday_name}) - ⏰ {time_str}\n"
                text += "\n"
            
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
    lang = user_data['languages'].get(user_id, 'uz')
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
        get_text(user_id, 'help'),
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
    
    for (uid, branch, lesson, date, time) in user_data['attendance_log']:
        if date >= week_ago_str:
            weekly_stats[uid] += 1
    
    if not weekly_stats:
        # Tilga mos "ma'lumot yo'q" xabari
        lang = user_data['languages'].get(user_id, 'uz')
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
        for (uid, branch, lesson, date, time) in user_data['attendance_log']:
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
            headers = ["Sana", "Filial", "Dars", "O'qituvchi ID", "O'qituvchi Ismi", "Vaqt"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            
            # Ma'lumotlarni yozish
            row = 2
            for (uid, branch, lesson, date, time) in sorted(user_data['attendance_log']):
                try:
                    user = await bot.get_chat(uid)
                    user_name = user.full_name
                except:
                    user_name = f"User_{uid}"
                
                ws.cell(row=row, column=1, value=date)
                ws.cell(row=row, column=2, value=branch)
                ws.cell(row=row, column=3, value=lesson)
                ws.cell(row=row, column=4, value=uid)
                ws.cell(row=row, column=5, value=user_name)
                ws.cell(row=row, column=6, value=time)
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
        user_count = len(user_data['user_ids'])
        active_today = len([k for k in user_data['attendance_log'] if k[3] == now_uzb.strftime("%Y-%m-%d")])
        
        await callback.message.answer(
            f"👥 **Foydalanuvchilar statistikasi**\n\n"
            f"Jami foydalanuvchilar: {user_count}\n"
            f"Bugun faol: {active_today}",
            parse_mode="Markdown"
        )
    
    elif action == "stats":
        total_attendances = len(user_data['attendance_log'])
        monthly_attendances = len([k for k in user_data['attendance_log'] if k[3].startswith(now_uzb.strftime("%Y-%m"))])
        
        await callback.message.answer(
            f"📈 **Umumiy statistika**\n\n"
            f"Jami davomatlar: {total_attendances}\n"
            f"Shu oyda: {monthly_attendances}\n"
            f"Faol filiallar: {len(set(k[1] for k in user_data['attendance_log']))}\n"
            f"Faol foydalanuvchilar: {len(set(k[0] for k in user_data['attendance_log']))}",
            parse_mode="Markdown"
        )
    
    await callback.answer()

# --- REMINDER LOOP ---
async def send_daily_reminders():
    """Har kuni soat 08:00 da eslatma yuborish"""
    now_uzb = datetime.now(UZB_TZ)
    today = now_uzb.strftime("%Y-%m-%d")
    today_weekday = now_uzb.weekday()
    
    # Bugun darsi bor foydalanuvchilarga eslatma
    sent_count = 0
    for user_id in user_data['user_ids']:
        schedule = user_data['schedules'].get(user_id, [])
        today_lessons = [l for l in schedule if l['weekday'] == today_weekday]
        
        if today_lessons:
            # Bugun davomat qilganmi?
            attended = any(k[0] == user_id and k[3] == today for k in user_data['attendance_log'])
            if not attended:
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
