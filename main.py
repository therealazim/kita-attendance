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
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
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
WEEKDAYS = {
    'uz': ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'],
    'ru': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
    'kr': ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
}

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

# Tillar uchun matnlar - Unicode kodlari bilan
TRANSLATIONS = {
    'uz': {
        'welcome': "\U0001F31F **HANCOM ACADEMYning o'qituvchilar uchun davomat botiga hush kelibsiz, {name}!**\n\nQuyidagi tugmalar orqali:\n• Davomat qilishingiz\n• Statistikangizni ko'rishingiz\n• Filiallar bilan tanishishingiz mumkin",
        'stats': "\U0001F4CA **Sizning statistikangiz:**",
        'no_stats': "\U0001F4AD Hali davomat qilmagansiz",
        'branches': "\U0001F3E2 **Mavjud filiallar (lokatsiya):**",
        'help': "\U0001F916 **Botdan foydalanish qo'llanmasi:**\n\n\U0001F4CD **Davomat qilish uchun:**\n• Pastdagi \"📍 Kelganimni tasdiqlash\" tugmasini bosing\n• Joylashuvingizni yuboring\n\n\U0001F4CA **Statistika:**\n• \"📊 Mening statistikam\" - shaxsiy davomat tarixingiz\n• \"🏢 Filiallar\" - barcha mavjud filiallar ro'yxati\n\n⚠️ **Eslatmalar:**\n• Har bir filialda kuniga faqat 1 marta davomat qilish mumkin\n• Davomat faqat Toshkent vaqti bilan hisoblanadi",
        'attendance_success': "✅ **Davomat tasdiqlandi!**\n\n\U0001F3EB **Filial:** {branch}\n\U0001F4C5 **Sana:** {date}\n⏰ **Vaqt:** {time}\n\U0001F4CA **Bu oydagi tashriflar:** {count} marta\n\U0001F4CD **Masofa:** {distance:.1f} metr",
        'already_attended': "⚠️ Siz bugun **{branch}** hududida allaqachon davomatdan o'tgansiz!",
        'not_in_area': "❌ Siz belgilangan ta'lim muassasalari hududida emassiz!",
        'daily_reminder': "⏰ **Eslatma!** Bugun hali davomat qilmagansiz. Ish kuningizni boshlash uchun davomatni tasdiqlang!",
        'weekly_top': "\U0001F3C6 **Haftaning eng faol o'qituvchilari:**\n\n{top_list}",
        'monthly_report': "\U0001F4CA **{month} oyi uchun hisobot**\n\n{report}",
        'language_changed': "✅ Til o'zgartirildi: O'zbek tili",
        'language_prompt': "Iltimos, tilni tanlang:",
        'view_schedules': "\U0001F4CB **Dars jadvallaringiz**",
        'no_schedules': "\U0001F4AD Sizda hali dars jadvallari mavjud emas.\n\n\U00002795 Jadval qo'shish tugmasi orqali yangi jadval qo'shishingiz mumkin.",
        'add_schedule_start': "\U0001F4C5 **Yangi dars jadvali qo'shish**\n\nQaysi filialda dars berasiz?",
        'select_weekdays': "\U0001F4C5 **Qaysi kunlarda dars berasiz?**\n\nQuyidagi kunlardan tanlang (bir nechta tanlashingiz mumkin):",
        'next_button': "➡️ Keyingisi",
        'done_button': "✅ Tugatish",
        'enter_time': "⏰ **{weekday} kuni soat nechida dars boshlanadi?**\n\nFormat: HH:MM (masalan: 09:00)",
        'schedule_saved': "✅ **Dars jadvali muvaffaqiyatli saqlandi!**\n\n\U0001F4C5 Filial: {branch}\n\U0001F4C6 Kunlar: {days}\n⏰ Vaqtlar: {times}",
        'schedule_detail': "\U0001F4C5 **{branch}**\n\n{days_times}",
        'schedule_deleted': "✅ **Dars jadvali o'chirildi!**\n\n\U0001F4C5 {branch} filialidagi jadval o'chirildi.",
        'confirm_delete': "❓ **Haqiqatan ham bu jadvalni o'chirmoqchimisiz?**",
        'reminder': "⏰ **Eslatma!**\n\nBugun soat {time} da {branch} filialida darsingiz bor.\nDavomat qilishni unutmang!",
        'buttons': {
            'attendance': "\U0001F4CD Kelganimni tasdiqlash",
            'my_stats': "\U0001F4CA Mening statistikam",
            'branches': "\U0001F3E2 Filiallar",
            'top_week': "\U0001F3C6 Hafta topi",
            'view_schedules': "\U0001F4CB Dars jadvallari",
            'add_schedule': "\u2795 Jadval qo'shish",
            'help': "\u2753 Yordam",
            'language': "\U0001F310 Til"
        }
    },
    'ru': {
        'welcome': "\U0001F31F **Добро пожаловать в бот для отметок HANCOM ACADEMY для учителей, {name}!**\n\nС помощью кнопок ниже вы можете:\n• Отметиться\n• Посмотреть статистику\n• Ознакомиться с филиалами",
        'stats': "\U0001F4CA **Ваша статистика:**",
        'no_stats': "\U0001F4AD Вы еще не отмечались",
        'branches': "\U0001F3E2 **Доступные филиалы (локация):**",
        'help': "\U0001F916 **Руководство по использованию:**\n\n\U0001F4CD **Для отметки:**\n• Нажмите кнопку \"📍 Подтвердить прибытие\"\n• Отправьте свою геолокацию\n\n\U0001F4CA **Статистика:**\n• \"📊 Моя статистика\" - история отметок\n• \"🏢 Филиалы\" - список всех филиалов\n\n⚠️ **Примечания:**\n• В каждом филиале можно отмечаться только 1 раз в день\n• Отметки записываются по ташкентскому времени",
        'attendance_success': "✅ **Отметка подтверждена!**\n\n\U0001F3EB **Филиал:** {branch}\n\U0001F4C5 **Дата:** {date}\n⏰ **Время:** {time}\n\U0001F4CA **Посещений в этом месяце:** {count}\n\U0001F4CD **Расстояние:** {distance:.1f} м",
        'already_attended': "⚠️ Вы уже отмечались сегодня в филиале **{branch}**!",
        'not_in_area': "❌ Вы не находитесь в зоне учебных заведений!",
        'daily_reminder': "⏰ **Напоминание!** Вы еще не отметились сегодня. Подтвердите свое прибытие для начала рабочего дня!",
        'weekly_top': "\U0001F3C6 **Самые активные учителя недели:**\n\n{top_list}",
        'monthly_report': "\U0001F4CA **Отчет за {month}**\n\n{report}",
        'language_changed': "✅ Язык изменен: Русский язык",
        'language_prompt': "Пожалуйста, выберите язык:",
        'view_schedules': "\U0001F4CB **Ваши расписания уроков**",
        'no_schedules': "\U0001F4AD У вас еще нет расписаний уроков.\n\n\U00002795 Вы можете добавить новое расписание через кнопку 'Добавить расписание'.",
        'add_schedule_start': "\U0001F4C5 **Добавление нового расписания**\n\nВ каком филиале вы преподаете?",
        'select_weekdays': "\U0001F4C5 **В какие дни вы преподаете?**\n\nВыберите дни (можно выбрать несколько):",
        'next_button': "➡️ Далее",
        'done_button': "✅ Завершить",
        'enter_time': "⏰ **Во сколько начинается урок в {weekday}?**\n\nФормат: ЧЧ:ММ (например: 09:00)",
        'schedule_saved': "✅ **Расписание успешно сохранено!**\n\n\U0001F4C5 Филиал: {branch}\n\U0001F4C6 Дни: {days}\n⏰ Время: {times}",
        'schedule_detail': "\U0001F4C5 **{branch}**\n\n{days_times}",
        'schedule_deleted': "✅ **Расписание удалено!**\n\n\U0001F4C5 Расписание для филиала {branch} удалено.",
        'confirm_delete': "❓ **Вы действительно хотите удалить это расписание?**",
        'reminder': "⏰ **Напоминание!**\n\nСегодня в {time} у вас урок в филиале {branch}.\nНе забудьте отметиться!",
        'buttons': {
            'attendance': "\U0001F4CD Подтвердить прибытие",
            'my_stats': "\U0001F4CA Моя статистика",
            'branches': "\U0001F3E2 Филиалы",
            'top_week': "\U0001F3C6 Топ недели",
            'view_schedules': "\U0001F4CB Расписания",
            'add_schedule': "\u2795 Добавить",
            'help': "\u2753 Помощь",
            'language': "\U0001F310 Язык"
        }
    },
    'kr': {
        'welcome': "\U0001F31F **HANCOM ACADEMY 교사용 출석 체크 봇에 오신 것을 환영합니다, {name}!**\n\n아래 버튼을 통해:\n• 출석 체크하기\n• 내 통계 보기\n• 지점 목록 보기",
        'stats': "\U0001F4CA **내 통계:**",
        'no_stats': "\U0001F4AD 아직 출석 체크하지 않았습니다",
        'branches': "\U0001F3E2 **등록된 지점 (위치):**",
        'help': "\U0001F916 **사용 설명서:**\n\n\U0001F4CD **출석 체크 방법:**\n• 하단의 \"📍 출석 확인\" 버튼을 누르세요\n• 위치를 전송하세요\n\n\U0001F4CA **통계:**\n• \"📊 내 통계\" - 개인 출석 기록\n• \"🏢 지점\" - 모든 지점 목록\n\n⚠️ **참고사항:**\n• 각 지점에서 하루에 한 번만 출석 체크 가능\n• 출석은 타슈켄트 시간 기준으로 기록됨",
        'attendance_success': "✅ **출석이 확인되었습니다!**\n\n\U0001F3EB **지점:** {branch}\n\U0001F4C5 **날짜:** {date}\n⏰ **시간:** {time}\n\U0001F4CA **이번 달 출석:** {count}회\n\U0001F4CD **거리:** {distance:.1f}미터",
        'already_attended': "⚠️ 오늘 이미 **{branch}** 지점에서 출석 체크하셨습니다!",
        'not_in_area': "❌ 지정된 교육 기관 구역 내에 있지 않습니다!",
        'daily_reminder': "⏰ **알림!** 오늘 아직 출석 체크하지 않으셨습니다. 업무 시작을 위해 출석을 확인하세요!",
        'weekly_top': "\U0001F3C6 **이번 주 가장 활발한 교사:**\n\n{top_list}",
        'monthly_report': "\U0001F4CA **{month}월 보고서**\n\n{report}",
        'language_changed': "✅ 언어가 변경되었습니다: 한국어",
        'language_prompt': "언어를 선택하세요:",
        'view_schedules': "\U0001F4CB **내 수업 시간표**",
        'no_schedules': "\U0001F4AD 아직 수업 시간표가 없습니다.\n\n\U00002795 '시간표 추가' 버튼을 통해 새 시간표를 추가할 수 있습니다.",
        'add_schedule_start': "\U0001F4C5 **새 수업 시간표 추가**\n\n어느 지점에서 수업하시나요?",
        'select_weekdays': "\U0001F4C5 **어느 요일에 수업하시나요?**\n\n요일을 선택하세요 (여러 개 선택 가능):",
        'next_button': "➡️ 다음",
        'done_button': "✅ 완료",
        'enter_time': "⏰ **{weekday} 수업 시작 시간은 몇 시인가요?**\n\n형식: HH:MM (예: 09:00)",
        'schedule_saved': "✅ **시간표가 성공적으로 저장되었습니다!**\n\n\U0001F4C5 지점: {branch}\n\U0001F4C6 요일: {days}\n⏰ 시간: {times}",
        'schedule_detail': "\U0001F4C5 **{branch}**\n\n{days_times}",
        'schedule_deleted': "✅ **시간표가 삭제되었습니다!**\n\n\U0001F4C5 {branch} 지점의 시간표가 삭제되었습니다.",
        'confirm_delete': "❓ **이 시간표를 삭제하시겠습니까?**",
        'reminder': "⏰ **알림!**\n\n오늘 {time}에 {branch} 지점에서 수업이 있습니다.\n출석 체크를 잊지 마세요!",
        'buttons': {
            'attendance': "\U0001F4CD 출석 확인",
            'my_stats': "\U0001F4CA 내 통계",
            'branches': "\U0001F3E2 지점",
            'top_week': "\U0001F3C6 주간 TOP",
            'view_schedules': "\U0001F4CB 시간표",
            'add_schedule': "\u2795 추가",
            'help': "\u2753 도움말",
            'language': "\U0001F310 언어"
        }
    }
}

# Ma'lumotlarni saqlash
daily_attendance_log = set()  # {(user_id, branch_name, date, time)}
attendance_counter = {}       # {(user_id, branch_name, month): count}
user_languages = {}           # {user_id: 'uz' or 'ru' or 'kr'}
user_ids = set()              # Barcha foydalanuvchilar ID si

# Dars jadvallari uchun ma'lumotlar
schedules = {}  # {schedule_id: {'user_id': user_id, 'branch': branch, 'days': {weekday: time}}}
user_schedules = defaultdict(list)  # {user_id: [schedule_id1, schedule_id2, ...]}

# FSM holatlari
class AddSchedule(StatesGroup):
    selecting_branch = State()
    selecting_weekdays = State()
    entering_time = State()

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
    """Asosiy menyu tugmalarini yaratish - 8 ta tugma"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text=get_button_text(user_id, 'attendance'), request_location=True),
        KeyboardButton(text=get_button_text(user_id, 'my_stats')),
        KeyboardButton(text=get_button_text(user_id, 'branches')),
        KeyboardButton(text=get_button_text(user_id, 'top_week')),
        KeyboardButton(text=get_button_text(user_id, 'view_schedules')),
        KeyboardButton(text=get_button_text(user_id, 'add_schedule')),
        KeyboardButton(text=get_button_text(user_id, 'help')),
        KeyboardButton(text=get_button_text(user_id, 'language'))
    )
    builder.adjust(1, 2, 2, 3)  # 1,2,2,3 qilib joylashtirish
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

def get_yandex_maps_link(lat: float, lon: float) -> str:
    """Yandex Maps link yaratish"""
    return f"https://yandex.com/maps/?pt={lon},{lat}&z=17&l=map"

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

\U0001F4CD **Joy:** {city}
🌡️ **{temp_text}:** {temp:.1f}°C ({feels_text}: {feels_like:.1f}°C)
💧 **{humidity_text}:** {humidity}%
💨 **{wind_text}:** {wind_speed:.1f} m/s
📊 **{pressure_text}:** {pressure_mmhg:.1f} mmHg

💡 **{recommendation_title}:**
{recommendation}

⏰ **{time_text}:** {datetime.now(UZB_TZ).strftime('%H:%M')}
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

@dp.message(F.text.in_({'\U0001F310 Til', '\U0001F310 Язык', '\U0001F310 언어'}))
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

# --- DARS JADVALLARI HANDLERLARI ---
@dp.message(F.text.in_({'\U0001F4CB Dars jadvallari', '\U0001F4CB Расписания', '\U0001F4CB 시간표 목록'}))
async def view_schedules(message: types.Message):
    """Foydalanuvchining barcha dars jadvallarini ko'rish"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, 'uz')
    
    if user_id not in user_schedules or not user_schedules[user_id]:
        await message.answer(get_text(user_id, 'no_schedules'))
        return
    
    # Har bir jadval uchun alohida xabar va o'chirish tugmasi
    for schedule_id in user_schedules[user_id]:
        schedule = schedules.get(schedule_id)
        if schedule and schedule['user_id'] == user_id:
            branch = schedule['branch']
            days_times = ""
            for day, time in schedule['days'].items():
                days_times += f"• {day}: {time}\n"
            
            # O'chirish tugmasi bilan keyboard
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_schedule_{schedule_id}")
            )
            
            await message.answer(
                get_text(user_id, 'schedule_detail', branch=branch, days_times=days_times),
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )

@dp.callback_query(F.data.startswith("delete_schedule_"))
async def confirm_delete_schedule(callback: types.CallbackQuery):
    """Jadvalni o'chirishni tasdiqlash"""
    schedule_id = callback.data.replace("delete_schedule_", "")
    user_id = callback.from_user.id
    
    # Tasdiqlash tugmalari
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_delete_{schedule_id}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel_delete")
    )
    
    await callback.message.edit_text(
        get_text(user_id, 'confirm_delete'),
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def delete_schedule(callback: types.CallbackQuery):
    """Jadvalni o'chirish"""
    schedule_id = callback.data.replace("confirm_delete_", "")
    user_id = callback.from_user.id
    
    # Jadvalni o'chirish
    if schedule_id in schedules and schedules[schedule_id]['user_id'] == user_id:
        branch = schedules[schedule_id]['branch']
        del schedules[schedule_id]
        
        # Foydalanuvchi jadvallari ro'yxatidan o'chirish
        if user_id in user_schedules and schedule_id in user_schedules[user_id]:
            user_schedules[user_id].remove(schedule_id)
        
        await callback.message.edit_text(
            get_text(user_id, 'schedule_deleted', branch=branch)
        )
    else:
        await callback.message.edit_text("❌ Jadval topilmadi yoki sizga tegishli emas!")
    
    await callback.answer()

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery):
    """O'chirishni bekor qilish"""
    await callback.message.delete()
    await callback.answer("Bekor qilindi")

@dp.message(F.text.in_({'\u2795 Jadval qo\'shish', '\u2795 Добавить расписание', '\u2795 시간표 추가'}))
async def add_schedule_start(message: types.Message, state: FSMContext):
    """Yangi dars jadvali qo'shish - filial tanlash"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, 'uz')
    
    # Filiallar ro'yxatini tayyorlash
    builder = InlineKeyboardBuilder()
    for location in LOCATIONS:
        builder.row(
            InlineKeyboardButton(text=location['name'], callback_data=f"branch_{location['name']}")
        )
    
    await state.set_state(AddSchedule.selecting_branch)
    await message.answer(
        get_text(user_id, 'add_schedule_start'),
        reply_markup=builder.as_markup()
    )

@dp.callback_query(AddSchedule.selecting_branch, F.data.startswith("branch_"))
async def add_schedule_branch(callback: types.CallbackQuery, state: FSMContext):
    """Filial tanlangandan keyin"""
    branch = callback.data.replace("branch_", "")
    await state.update_data(branch=branch)
    
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, 'uz')
    weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
    
    # Hafta kunlarini tanlash uchun keyboard
    builder = InlineKeyboardBuilder()
    for i, day in enumerate(weekdays):
        builder.row(
            InlineKeyboardButton(text=f"⬜ {day}", callback_data=f"weekday_{i}")
        )
    builder.row(
        InlineKeyboardButton(text=get_text(user_id, 'next_button'), callback_data="weekdays_next")
    )
    
    await state.update_data(selected_days={})
    await state.set_state(AddSchedule.selecting_weekdays)
    await callback.message.edit_text(
        get_text(user_id, 'select_weekdays'),
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(AddSchedule.selecting_weekdays, F.data.startswith("weekday_"))
async def add_schedule_weekday_select(callback: types.CallbackQuery, state: FSMContext):
    """Hafta kunlarini tanlash"""
    data = await state.get_data()
    selected_days = data.get('selected_days', {})
    day_index = int(callback.data.replace("weekday_", ""))
    
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, 'uz')
    weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
    
    # Kunni tanlash/bekor qilish
    if day_index in selected_days:
        del selected_days[day_index]
    else:
        selected_days[day_index] = None
    
    await state.update_data(selected_days=selected_days)
    
    # Keyboardni yangilash
    builder = InlineKeyboardBuilder()
    for i, day in enumerate(weekdays):
        if i in selected_days:
            builder.row(
                InlineKeyboardButton(text=f"✅ {day}", callback_data=f"weekday_{i}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text=f"⬜ {day}", callback_data=f"weekday_{i}")
            )
    builder.row(
        InlineKeyboardButton(text=get_text(user_id, 'next_button'), callback_data="weekdays_next")
    )
    
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(AddSchedule.selecting_weekdays, F.data == "weekdays_next")
async def add_schedule_weekdays_next(callback: types.CallbackQuery, state: FSMContext):
    """Kunlar tanlangandan keyin vaqt kiritishga o'tish"""
    data = await state.get_data()
    selected_days = data.get('selected_days', {})
    
    if not selected_days:
        await callback.answer("Hech bo'lmaganda 1 kun tanlang!", show_alert=True)
        return
    
    days_without_time = [day for day in selected_days if selected_days[day] is None]
    
    if days_without_time:
        await state.update_data(current_day=days_without_time[0])
        await state.set_state(AddSchedule.entering_time)
        
        user_id = callback.from_user.id
        lang = user_languages.get(user_id, 'uz')
        weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
        day_name = weekdays[days_without_time[0]]
        
        await callback.message.edit_text(
            get_text(user_id, 'enter_time', weekday=day_name)
        )
    else:
        await save_schedule(callback.message, state, callback.from_user.id)
    
    await callback.answer()

@dp.message(AddSchedule.entering_time)
async def add_schedule_enter_time(message: types.Message, state: FSMContext):
    """Har bir kun uchun vaqt kiritish"""
    time_str = message.text.strip()
    
    try:
        hours, minutes = map(int, time_str.split(':'))
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            raise ValueError
        formatted_time = f"{hours:02d}:{minutes:02d}"
    except:
        user_id = message.from_user.id
        lang = user_languages.get(user_id, 'uz')
        await message.answer("❌ Noto'g'ri format! Iltimos, HH:MM formatida kiriting (masalan: 09:00)")
        return
    
    data = await state.get_data()
    selected_days = data.get('selected_days', {})
    current_day = data.get('current_day')
    
    selected_days[current_day] = formatted_time
    await state.update_data(selected_days=selected_days)
    
    days_without_time = [day for day in selected_days if selected_days[day] is None]
    
    if days_without_time:
        await state.update_data(current_day=days_without_time[0])
        user_id = message.from_user.id
        lang = user_languages.get(user_id, 'uz')
        weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
        day_name = weekdays[days_without_time[0]]
        
        await message.answer(
            get_text(user_id, 'enter_time', weekday=day_name)
        )
    else:
        await save_schedule(message, state, message.from_user.id)

async def save_schedule(message: types.Message, state: FSMContext, user_id: int):
    """Jadvalni saqlash"""
    data = await state.get_data()
    branch = data.get('branch')
    selected_days = data.get('selected_days', {})
    
    lang = user_languages.get(user_id, 'uz')
    weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
    
    schedule_id = f"schedule_{user_id}_{datetime.now().timestamp()}"
    
    days_with_names = {}
    for day_index, time in selected_days.items():
        day_name = weekdays[day_index]
        days_with_names[day_name] = time
    
    schedules[schedule_id] = {
        'user_id': user_id,
        'branch': branch,
        'days': days_with_names
    }
    user_schedules[user_id].append(schedule_id)
    
    days_list = ", ".join(days_with_names.keys())
    times_list = ", ".join(days_with_names.values())
    
    await message.answer(
        get_text(user_id, 'schedule_saved', branch=branch, days=days_list, times=times_list),
        parse_mode="Markdown"
    )
    
    await state.clear()
    
    keyboard = await main_keyboard(user_id)
    await message.answer("Asosiy menyu:", reply_markup=keyboard)

# --- BOSHQA HANDLERLAR ---
@dp.message(F.text.in_({'\U0001F4CA Mening statistikam', '\U0001F4CA Моя статистика', '\U0001F4CA 내 통계'}))
async def my_stats(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    current_month = now_uzb.strftime("%Y-%m")
    
    user_attendances = defaultdict(list)
    
    for (uid, branch, date, time) in daily_attendance_log:
        if uid == user_id:
            user_attendances[branch].append((date, time))
    
    if not user_attendances:
        await message.answer(get_text(user_id, 'no_stats'), parse_mode="Markdown")
        return
    
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
    else:
        month_names = month_names_kr
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        current_month_text = "(이번 달)"
    
    text = get_text(user_id, 'stats') + "\n\n"
    
    for branch, date_time_list in user_attendances.items():
        text += f"\U0001F3E2 **{branch}**\n"
        
        dates_by_month = defaultdict(list)
        for date_str, time_str in date_time_list:
            year_month = date_str[:7]
            dates_by_month[year_month].append((date_str, time_str))
        
        for year_month, month_data in sorted(dates_by_month.items(), reverse=True):
            year, month = year_month.split('-')
            month_name = month_names.get(month, month)
            
            month_display = f"{month_name} {year}"
            if year_month == current_month:
                month_display += f" {current_month_text}"
            
            text += f"   \U0001F4C5 **{month_display}**\n"
            
            for date_str, time_str in sorted(month_data, reverse=True):
                date_parts = date_str.split('-')
                year, month, day = date_parts
                
                date_obj = datetime(int(year), int(month), int(day), tzinfo=UZB_TZ)
                weekday = date_obj.weekday()
                weekday_name = weekdays[weekday]
                
                if lang == 'kr':
                    formatted_date = f"{year}년 {int(month):02d}월 {int(day):02d}일"
                else:
                    formatted_date = f"{int(day):02d}.{int(month):02d}.{year}"
                
                text += f"      • {formatted_date} ({weekday_name}) - ⏰ {time_str}\n"
            
            text += "\n"
        
        text += "\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({'\U0001F3E2 Filiallar', '\U0001F3E2 Филиалы', '\U0001F3E2 지점'}))
async def show_branches(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, 'uz')
    
    universities = []
    lyceums = []
    schools = []
    
    for branch in LOCATIONS:
        if "Universitet" in branch['name'] or "Kimyo" in branch['name']:
            universities.append(branch)
        elif "Litsey" in branch['name'] or "litseyi" in branch['name'].lower():
            lyceums.append(branch)
        elif "Maktab" in branch['name']:
            schools.append(branch)
    
    # Tilga mos sarlavhalar
    if lang == 'uz':
        uni_title = "\U0001F3DB **Universitetlar**"
        lyceum_title = "\U0001F4DA **Litseylar**"
        school_title = "\U0001F3EB **Maktablar**"
        header = f"{uni_title}\n{lyceum_title}\n{school_title}"
    elif lang == 'ru':
        uni_title = "\U0001F3DB **Университеты**"
        lyceum_title = "\U0001F4DA **Лицеи**"
        school_title = "\U0001F3EB **Школы**"
        header = f"{uni_title}\n{lyceum_title}\n{school_title}"
    else:
        uni_title = "\U0001F3DB **대학교**"
        lyceum_title = "\U0001F4DA **고등학교**"
        school_title = "\U0001F3EB **초중학교**"
        header = f"{uni_title}\n{lyceum_title}\n{school_title}"
    
    # Barcha tugmalarni bitta builderda yig'amiz
    builder = InlineKeyboardBuilder()
    
    # Universitetlar
    if universities:
        for uni in universities:
            maps_link = get_yandex_maps_link(uni['lat'], uni['lon'])
            builder.row(
                InlineKeyboardButton(text=f"\U0001F4CD {uni['name']}", url=maps_link)
            )
    
    # Litseylar
    if lyceums:
        for lyceum in lyceums:
            maps_link = get_yandex_maps_link(lyceum['lat'], lyceum['lon'])
            builder.row(
                InlineKeyboardButton(text=f"\U0001F4CD {lyceum['name']}", url=maps_link)
            )
    
    # Maktablar
    if schools:
        for school in schools:
            maps_link = get_yandex_maps_link(school['lat'], school['lon'])
            builder.row(
                InlineKeyboardButton(text=f"\U0001F4CD {school['name']}", url=maps_link)
            )
    
    # Bitta xabar - barcha tugmalar
    await message.answer(
        header,
        reply_markup=builder.as_markup()
    )

@dp.message(F.text.in_({'\u2753 Yordam', '\u2753 Помощь', '\u2753 도움말'}))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        get_text(user_id, 'help'),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'\U0001F3C6 Hafta topi', '\U0001F3C6 Топ недели', '\U0001F3C6 주간 TOP'}))
async def weekly_top(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    week_ago = now_uzb - timedelta(days=7)
    week_ago_str = week_ago.strftime("%Y-%m-%d")
    
    weekly_stats = defaultdict(int)
    
    for (uid, branch, date, time) in daily_attendance_log:
        if date >= week_ago_str:
            weekly_stats[uid] += 1
    
    if not weekly_stats:
        lang = user_languages.get(user_id, 'uz')
        if lang == 'uz':
            no_data_msg = "\U0001F4AD Bu hafta hali davomat yo'q"
        elif lang == 'ru':
            no_data_msg = "\U0001F4AD На этой неделе еще нет отметок"
        else:
            no_data_msg = "\U0001F4AD 이번 주에는 아직 출석 기록이 없습니다"
        
        await message.answer(no_data_msg)
        return
    
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

    if found_branch:
        already_attended = False
        for (uid, branch, date, time) in daily_attendance_log:
            if uid == user_id and branch == found_branch and date == today_date:
                already_attended = True
                break
        
        if already_attended:
            await message.answer(
                get_text(user_id, 'already_attended', branch=found_branch),
                parse_mode="Markdown"
            )
            return

        counter_key = (user_id, found_branch, current_month)
        attendance_counter[counter_key] = attendance_counter.get(counter_key, 0) + 1
        visit_number = attendance_counter[counter_key]
        
        daily_attendance_log.add((user_id, found_branch, today_date, now_time))
        full_name = message.from_user.full_name
        
        report = (
            f"✅ **Yangi Davomat**\n\n"
            f"👤 **O'qituvchi:** {full_name}\n"
            f"\U0001F4CD **Manzil:** {found_branch}\n"
            f"\U0001F4C5 **Sana:** {today_date}\n"
            f"⏰ **Vaqt:** {now_time}\n"
            f"\U0001F4CA **Shu oydagi tashrif:** {visit_number}-marta\n"
            f"\U0001F4CD **Masofa:** {min_distance:.1f} metr"
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
            
            success_text = get_text(
                user_id, 
                'attendance_success',
                branch=found_branch,
                date=today_date,
                time=now_time,
                count=visit_number,
                distance=min_distance
            )
            
            weather_data = await get_weather_by_coords(user_coords[0], user_coords[1])
            weather_message = format_weather_message(weather_data, user_languages.get(user_id, 'uz'))
            
            full_response = f"{success_text}\n\n{weather_message}"
            await message.answer(full_response, parse_mode="Markdown")
            
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
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
        
        monthly_stats = defaultdict(lambda: defaultdict(int))
        for (uid, branch, date, time) in daily_attendance_log:
            if date.startswith(current_month):
                monthly_stats[branch][uid] += 1
        
        report = f"📊 **{month_name} oyi uchun hisobot**\n\n"
        
        for branch, users in monthly_stats.items():
            total = sum(users.values())
            unique_users = len(users)
            report += f"\U0001F3E2 **{branch}**\n"
            report += f"   Jami: {total} ta davomat\n"
            report += f"   O'qituvchilar: {unique_users} ta\n\n"
        
        await callback.message.answer(report, parse_mode="Markdown")
    
    elif action == "excel":
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Davomat"
            
            headers = ["Sana", "Filial", "O'qituvchi ID", "O'qituvchi Ismi", "Vaqt"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            
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

# --- ESLATMA LOOPLARI ---
async def send_daily_reminders():
    """Har kuni soat 08:00 da eslatma yuborish"""
    now_uzb = datetime.now(UZB_TZ)
    today = now_uzb.strftime("%Y-%m-%d")
    
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

async def check_schedule_reminders():
    """Dars vaqtlarini tekshirib, eslatma yuborish"""
    while True:
        now_uzb = datetime.now(UZB_TZ)
        current_time = now_uzb.strftime("%H:%M")
        current_weekday = now_uzb.weekday()
        
        weekdays_uz = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        current_day_name = weekdays_uz[current_weekday]
        
        for schedule_id, schedule in schedules.items():
            user_id = schedule['user_id']
            branch = schedule['branch']
            days = schedule['days']
            
            if current_day_name in days:
                lesson_time = days[current_day_name]
                
                lesson_dt = datetime.strptime(lesson_time, "%H:%M")
                reminder_dt = lesson_dt - timedelta(minutes=15)
                reminder_time = reminder_dt.strftime("%H:%M")
                
                if current_time == reminder_time:
                    lang = user_languages.get(user_id, 'uz')
                    try:
                        await bot.send_message(
                            user_id,
                            get_text(user_id, 'reminder', time=lesson_time, branch=branch),
                            parse_mode="Markdown"
                        )
                        logging.info(f"Reminder sent to {user_id} for {branch} at {lesson_time}")
                    except Exception as e:
                        logging.error(f"Failed to send reminder to {user_id}: {e}")
        
        await asyncio.sleep(60)

async def reminder_loop():
    """Ertalabgi eslatmalar uchun doimiy loop"""
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
    asyncio.create_task(check_schedule_reminders())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
