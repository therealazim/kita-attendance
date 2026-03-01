import asyncio
import os
import logging
import pytz 
import io
import aiohttp
import json
import csv
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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import pickle

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

# Foydalanuvchi ism-familiyalarini saqlash uchun
user_names = {}  # {user_id: full_name}

# Foydalanuvchi mutaxassisligi (IT yoki Koreys tili)
user_specialty = {}  # {user_id: 'IT' or 'Koreys tili'}

# Foydalanuvchi holati (bloklangan, aktiv, etc.)
user_status = {}  # {user_id: 'active' or 'blocked'}

# Adminlar ro'yxati
admins = {ADMIN_GROUP_ID: True}

# Broadcast xabarlar tarixi
broadcast_history = []  # [{text: '...', date: '...', sent_count: 0, specialty: '...'}]

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
    {"name": "294-Maktab", "lat": 41.281633, "lon": 69.289237},
    {"name": "Umnie Deti School", "lat": 41.315790, "lon": 69.209515},
    {"name": "Cambridge School", "lat": 41.342296, "lon": 69.167571}
]
ALLOWED_DISTANCE = 500

# FSM holatlari
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_specialty = State()

class AdminAddSchedule(StatesGroup):
    selecting_teacher = State()
    selecting_branch = State()
    selecting_lesson_type = State()
    selecting_weekdays = State()
    entering_time = State()

class AdminEditSchedule(StatesGroup):
    selecting_schedule = State()
    selecting_branch = State()
    selecting_lesson_type = State()
    selecting_weekdays = State()
    entering_time = State()

class Broadcast(StatesGroup):
    selecting_specialty = State()
    waiting_for_message = State()
    waiting_for_confirm = State()

class AddLocation(StatesGroup):
    waiting_for_name = State()
    waiting_for_coords = State()

class PDFReport(StatesGroup):
    waiting_for_date = State()

# Hafta kunlari
WEEKDAYS = {
    'uz': ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'],
    'ru': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
    'kr': ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
}

# Dars turlari
LESSON_TYPES = {
    'uz': ['IT', 'Koreys tili'],
    'ru': ['IT', 'Корейский язык'],
    'kr': ['IT', '한국어']
}

# Hafta kunlari nomlari (eslatma uchun)
WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

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
        'welcome': "\U0001F31F HANCOM ACADEMYning o'qituvchilar uchun davomat botiga hush kelibsiz, {name}!",
        'ask_name': "👤 Iltimos, ism va familiyangizni kiriting:\n\nMasalan: Ali Karimov",
        'ask_specialty': "📚 Qaysi fan o'qituvchisisiz?",
        'specialty_it': "💻 IT",
        'specialty_korean': "🇰🇷 Koreys tili",
        'stats': "\U0001F4CA Sizning statistikangiz:",
        'no_stats': "\U0001F4AD Hali davomat qilmagansiz",
        'branches': "\U0001F3E2 Mavjud filiallar (lokatsiya):",
        'help': "\U0001F916 Botdan foydalanish qo'llanmasi:\n\n\U0001F4CD Davomat qilish uchun:\n• Pastdagi \"📍 Kelganimni tasdiqlash\" tugmasini bosing\n• Joylashuvingizni yuboring\n\n\U0001F4CA Statistika:\n• \"📊 Mening statistikam\" - shaxsiy davomat tarixingiz\n• \"🏢 Filiallar\" - barcha mavjud filiallar ro'yxati\n\n⚠️ Eslatmalar:\n• Har bir filialda kuniga faqat 1 marta davomat qilish mumkin\n• Davomat faqat Toshkent vaqti bilan hisoblanadi",
        'attendance_success': "✅ Davomat tasdiqlandi!\n\n\U0001F3EB Filial: {branch}\n\U0001F4C5 Sana: {date}\n⏰ Vaqt: {time}\n\U0001F4CA Bu oydagi tashriflar: {count} marta\n\U0001F4CD Masofa: {distance:.1f} metr",
        'already_attended': "⚠️ Siz bugun {branch} hududida allaqachon davomatdan o'tgansiz!",
        'not_in_area': "❌ Siz belgilangan ta'lim muassasalari hududida emassiz!",
        'daily_reminder': "⏰ Eslatma! Bugun hali davomat qilmagansiz. Ish kuningizni boshlash uchun davomatni tasdiqlang!",
        'weekly_top': "\U0001F3C6 Haftaning eng faol o'qituvchilari:\n\n{top_list}",
        'monthly_report': "\U0001F4CA {month} oyi uchun hisobot\n\n{report}",
        'language_changed': "✅ Til o'zgartirildi: O'zbek tili",
        'language_prompt': "Iltimos, tilni tanlang:",
        'view_schedules': "\U0001F4CB Mening dars jadvalim",
        'my_schedule': "📅 Sizning dars jadvalingiz:\n\n{schedule}",
        'no_schedules': "📭 Sizga hali dars jadvali biriktirilmagan.",
        'schedule_updated': "📢 Sizning dars jadvalingiz yangilandi!\n\n{schedule}",
        'schedule_deleted_notify': "📢 Sizning dars jadvalingiz o'chirildi.",
        'select_teacher': "👤 O'qituvchini tanlang:",
        'select_lesson_type': "📚 Dars turini tanlang:",
        'active_schedules': "📋 Faol dars jadvallari",
        'no_active_schedules': "📭 Hali dars jadvallari mavjud emas.",
        'schedule_info': "👤 {teacher} [{specialty}]\n🏢 {branch}\n📚 {lesson_type}\n📆 {days_times}",
        'enter_date': "📅 Hisobot olish uchun sanani kiriting (format: YYYY-MM-DD)\nMasalan: 2026-03-01",
        'invalid_date': "❌ Noto'g'ri sana formati. Qaytadan urinib ko'ring:",
        'select_broadcast_specialty': "📢 Qaysi fan o'qituvchilariga xabar yubormoqchisiz?",
        'all_teachers': "👥 Hammasi",
        'buttons': {
            'attendance': "\U0001F4CD Kelganimni tasdiqlash",
            'my_stats': "\U0001F4CA Mening statistikam",
            'branches': "\U0001F3E2 Filiallar",
            'top_week': "\U0001F3C6 Hafta topi",
            'view_schedules': "\U0001F4CB Dars jadvalim",
            'help': "\u2753 Yordam",
            'language': "\U0001F310 Til"
        }
    },
    'ru': {
        'welcome': "\U0001F31F Добро пожаловать в бот для отметок HANCOM ACADEMY для учителей, {name}!",
        'ask_name': "👤 Пожалуйста, введите ваше имя и фамилию:\n\nНапример: Ali Karimov",
        'ask_specialty': "📚 Какой предмет вы преподаете?",
        'specialty_it': "💻 IT",
        'specialty_korean': "🇰🇷 Корейский язык",
        'stats': "\U0001F4CA Ваша статистика:",
        'no_stats': "\U0001F4AD Вы еще не отмечались",
        'branches': "\U0001F3E2 Доступные филиалы (локация):",
        'help': "\U0001F916 Руководство по использованию:\n\n\U0001F4CD Для отметки:\n• Нажмите кнопку \"📍 Подтвердить прибытие\"\n• Отправьте свою геолокацию\n\n\U0001F4CA Статистика:\n• \"📊 Моя статистика\" - история отметок\n• \"🏢 Филиалы\" - список всех филиалов\n\n⚠️ Примечания:\n• В каждом филиале можно отмечаться только 1 раз в день\n• Отметки записываются по ташкентскому времени",
        'attendance_success': "✅ Отметка подтверждена!\n\n\U0001F3EB Филиал: {branch}\n\U0001F4C5 Дата: {date}\n⏰ Время: {time}\n\U0001F4CA Посещений в этом месяце: {count}\n\U0001F4CD Расстояние: {distance:.1f} м",
        'already_attended': "⚠️ Вы уже отмечались сегодня в филиале {branch}!",
        'not_in_area': "❌ Вы не находитесь в зоне учебных заведений!",
        'daily_reminder': "⏰ Напоминание! Вы еще не отметились сегодня. Подтвердите свое прибытие для начала рабочего дня!",
        'weekly_top': "\U0001F3C6 Самые активные учителя недели:\n\n{top_list}",
        'monthly_report': "\U0001F4CA Отчет за {month}\n\n{report}",
        'language_changed': "✅ Язык изменен: Русский язык",
        'language_prompt': "Пожалуйста, выберите язык:",
        'view_schedules': "\U0001F4CB Мое расписание",
        'my_schedule': "📅 Ваше расписание уроков:\n\n{schedule}",
        'no_schedules': "📭 Вам еще не назначено расписание.",
        'schedule_updated': "📢 Ваше расписание обновлено!\n\n{schedule}",
        'schedule_deleted_notify': "📢 Ваше расписание удалено.",
        'select_teacher': "👤 Выберите учителя:",
        'select_lesson_type': "📚 Выберите тип урока:",
        'active_schedules': "📋 Активные расписания",
        'no_active_schedules': "📭 Нет активных расписаний.",
        'schedule_info': "👤 {teacher} [{specialty}]\n🏢 {branch}\n📚 {lesson_type}\n📆 {days_times}",
        'enter_date': "📅 Введите дату для отчета (формат: YYYY-MM-DD)\nНапример: 2026-03-01",
        'invalid_date': "❌ Неверный формат даты. Попробуйте снова:",
        'select_broadcast_specialty': "📢 Каким учителям отправить сообщение?",
        'all_teachers': "👥 Всем",
        'buttons': {
            'attendance': "\U0001F4CD Подтвердить прибытие",
            'my_stats': "\U0001F4CA Моя статистика",
            'branches': "\U0001F3E2 Филиалы",
            'top_week': "\U0001F3C6 Топ недели",
            'view_schedules': "\U0001F4CB Мое расписание",
            'help': "\u2753 Помощь",
            'language': "\U0001F310 Язык"
        }
    },
    'kr': {
        'welcome': "\U0001F31F HANCOM ACADEMY 교사용 출석 체크 봇에 오신 것을 환영합니다, {name}!",
        'ask_name': "👤 이름과 성을 입력하세요:\n\n예: Ali Karimov",
        'ask_specialty': "📚 어떤 과목을 가르치시나요?",
        'specialty_it': "💻 IT",
        'specialty_korean': "🇰🇷 한국어",
        'stats': "\U0001F4CA 내 통계:",
        'no_stats': "\U0001F4AD 아직 출석 체크하지 않았습니다",
        'branches': "\U0001F3E2 등록된 지점 (위치):",
        'help': "\U0001F916 사용 설명서:\n\n\U0001F4CD 출석 체크 방법:\n• 하단의 \"📍 출석 확인\" 버튼을 누르세요\n• 위치를 전송하세요\n\n\U0001F4CA 통계:\n• \"📊 내 통계\" - 개인 출석 기록\n• \"🏢 지점\" - 모든 지점 목록\n\n⚠️ 참고사항:\n• 각 지점에서 하루에 한 번만 출석 체크 가능\n• 출석은 타슈켄트 시간 기준으로 기록됨",
        'attendance_success': "✅ 출석이 확인되었습니다!\n\n\U0001F3EB 지점: {branch}\n\U0001F4C5 날짜: {date}\n⏰ 시간: {time}\n\U0001F4CA 이번 달 출석: {count}회\n\U0001F4CD 거리: {distance:.1f}미터",
        'already_attended': "⚠️ 오늘 이미 {branch} 지점에서 출석 체크하셨습니다!",
        'not_in_area': "❌ 지정된 교육 기관 구역 내에 있지 않습니다!",
        'daily_reminder': "⏰ 알림! 오늘 아직 출석 체크하지 않으셨습니다. 업무 시작을 위해 출석을 확인하세요!",
        'weekly_top': "\U0001F3C6 이번 주 가장 활발한 교사:\n\n{top_list}",
        'monthly_report': "\U0001F4CA {month}월 보고서\n\n{report}",
        'language_changed': "✅ 언어가 변경되었습니다: 한국어",
        'language_prompt': "언어를 선택하세요:",
        'view_schedules': "\U0001F4CB 내 시간표",
        'my_schedule': "📅 내 수업 시간표:\n\n{schedule}",
        'no_schedules': "📭 아직 시간표가 배정되지 않았습니다.",
        'schedule_updated': "📢 시간표가 업데이트되었습니다!\n\n{schedule}",
        'schedule_deleted_notify': "📢 시간표가 삭제되었습니다.",
        'select_teacher': "👤 교사를 선택하세요:",
        'select_lesson_type': "📚 수업 유형을 선택하세요:",
        'active_schedules': "📋 활성 시간표",
        'no_active_schedules': "📭 활성 시간표가 없습니다.",
        'schedule_info': "👤 {teacher} [{specialty}]\n🏢 {branch}\n📚 {lesson_type}\n📆 {days_times}",
        'enter_date': "📅 보고서 날짜를 입력하세요 (형식: YYYY-MM-DD)\n예: 2026-03-01",
        'invalid_date': "❌ 잘못된 날짜 형식입니다. 다시 시도하세요:",
        'select_broadcast_specialty': "📢 어떤 선생님들에게 메시지를 보낼까요?",
        'all_teachers': "👥 모두",
        'buttons': {
            'attendance': "\U0001F4CD 출석 확인",
            'my_stats': "\U0001F4CA 내 통계",
            'branches': "\U0001F3E2 지점",
            'top_week': "\U0001F3C6 주간 TOP",
            'view_schedules': "\U0001F4CB 내 시간표",
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
schedules = {}  # {schedule_id: {'user_id': user_id, 'branch': branch, 'lesson_type': lesson_type, 'days': {weekday: time}}}
user_schedules = defaultdict(list)  # {user_id: [schedule_id1, schedule_id2, ...]}

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

def check_admin(chat_id):
    """Foydalanuvchi admin ekanligini tekshirish"""
    return chat_id == ADMIN_GROUP_ID

def get_specialty_display(specialty: str, lang: str = 'uz') -> str:
    """Mutaxassislikni formatlash"""
    if specialty == 'IT':
        return "💻 IT"
    else:
        return "🇰🇷 Koreys tili"

async def main_keyboard(user_id: int):
    """Asosiy menyu tugmalarini yaratish"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text=get_button_text(user_id, 'attendance'), request_location=True),
        KeyboardButton(text=get_button_text(user_id, 'my_stats')),
        KeyboardButton(text=get_button_text(user_id, 'branches')),
        KeyboardButton(text=get_button_text(user_id, 'top_week')),
        KeyboardButton(text=get_button_text(user_id, 'view_schedules')),
        KeyboardButton(text=get_button_text(user_id, 'help')),
        KeyboardButton(text=get_button_text(user_id, 'language'))
    )
    builder.adjust(1, 2, 2, 2)  # 1,2,2,2 qilib joylashtirish
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

async def specialty_keyboard(user_id: int):
    """Mutaxassislik tanlash uchun keyboard"""
    lang = user_languages.get(user_id, 'uz')
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text=TRANSLATIONS[lang]['specialty_it']),
        KeyboardButton(text=TRANSLATIONS[lang]['specialty_korean'])
    )
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

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
{emoji} Ob-havo ma'lumoti

\U0001F4CD Joy: {city}
🌡️ {temp_text}: {temp:.1f}°C ({feels_text}: {feels_like:.1f}°C)
💧 {humidity_text}: {humidity}%
💨 {wind_text}: {wind_speed:.1f} m/s
📊 {pressure_text}: {pressure_mmhg:.1f} mmHg

💡 {recommendation_title}:
{recommendation}

⏰ {time_text}: {datetime.now(UZB_TZ).strftime('%H:%M')}
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
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Bloklangan foydalanuvchini tekshirish
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
    # Agar foydalanuvchi ismini kiritmagan bo'lsa
    if user_id not in user_names:
        # Til tanlashni so'raymiz
        if user_id not in user_languages:
            keyboard = await language_selection_keyboard()
            await message.answer(
                "Iltimos, tilni tanlang:\nПожалуйста, выберите язык:\n언어를 선택하세요:",
                reply_markup=keyboard
            )
            return
        
        # Ism so'rash
        await state.set_state(Registration.waiting_for_name)
        await message.answer(get_text(user_id, 'ask_name'))
        return
    
    # Eski foydalanuvchi bo'lsa, to'g'ridan-to'g'ri menyuga o'tamiz
    user_ids.add(user_id)
    keyboard = await main_keyboard(user_id)
    name = user_names.get(user_id, message.from_user.full_name)
    specialty = user_specialty.get(user_id, '')
    
    welcome_text = get_text(user_id, 'welcome', name=name)
    if specialty:
        specialty_display = get_specialty_display(specialty, user_languages.get(user_id, 'uz'))
        welcome_text += f"\n\n{specialty_display}"
    
    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    """Foydalanuvchi ismini qabul qilish"""
    user_id = message.from_user.id
    full_name = message.text.strip()
    
    # Ismni saqlash
    user_names[user_id] = full_name
    user_ids.add(user_id)
    
    await state.update_data(name=full_name)
    
    # Mutaxassislik so'rash
    keyboard = await specialty_keyboard(user_id)
    await state.set_state(Registration.waiting_for_specialty)
    await message.answer(
        get_text(user_id, 'ask_specialty'),
        reply_markup=keyboard
    )

@dp.message(Registration.waiting_for_specialty)
async def process_specialty(message: types.Message, state: FSMContext):
    """Foydalanuvchi mutaxassisligini qabul qilish"""
    user_id = message.from_user.id
    text = message.text
    
    lang = user_languages.get(user_id, 'uz')
    
    if text == TRANSLATIONS[lang]['specialty_it']:
        specialty = 'IT'
    elif text == TRANSLATIONS[lang]['specialty_korean']:
        specialty = 'Koreys tili'
    else:
        await message.answer("❌ Noto'g'ri tanlov. Qaytadan urinib ko'ring.")
        return
    
    # Mutaxassislikni saqlash
    user_specialty[user_id] = specialty
    user_status[user_id] = 'active'
    
    await state.clear()
    
    # Asosiy menyuni ko'rsatish
    keyboard = await main_keyboard(user_id)
    name = user_names.get(user_id)
    specialty_display = get_specialty_display(specialty, lang)
    
    welcome_text = get_text(user_id, 'welcome', name=name) + f"\n\n{specialty_display}"
    
    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("lang_"))
async def set_initial_language(callback: types.CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        lang = callback.data.split("_")[1]
        
        # Tilni saqlash
        user_languages[user_id] = lang
        
        await callback.answer()
        await callback.message.delete()
        
        # Ism so'rash
        await state.set_state(Registration.waiting_for_name)
        await callback.message.answer(get_text(user_id, 'ask_name'))
    except Exception as e:
        logging.error(f"set_initial_language error: {e}")
        await callback.answer("Xatolik yuz berdi")

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
    try:
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
    except Exception as e:
        logging.error(f"set_changed_language error: {e}")
        await callback.answer("Xatolik yuz berdi")

# --- FOYDALANUVCHI UCHUN DARS JADVALINI KO'RISH ---
@dp.message(F.text.in_({'\U0001F4CB Dars jadvalim', '\U0001F4CB Мое расписание', '\U0001F4CB 내 시간표'}))
async def view_my_schedule(message: types.Message):
    """Foydalanuvchi o'zining dars jadvalini ko'rish"""
    user_id = message.from_user.id
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
    if user_id not in user_schedules or not user_schedules[user_id]:
        await message.answer(get_text(user_id, 'no_schedules'))
        return
    
    # Foydalanuvchining barcha jadvallarini yig'ish
    schedule_text = ""
    for schedule_id in user_schedules[user_id]:
        schedule = schedules.get(schedule_id)
        if schedule and schedule['user_id'] == user_id:
            branch = schedule['branch']
            lesson_type = schedule.get('lesson_type', 'Dars')
            days_times = ""
            for day, time in sorted(schedule['days'].items(), key=lambda x: WEEKDAYS_UZ.index(x[0])):
                days_times += f"• {day}: {time}\n"
            
            schedule_text += f"🏢 {branch} - {lesson_type}\n{days_times}\n"
    
    await message.answer(
        get_text(user_id, 'my_schedule', schedule=schedule_text),
        parse_mode="Markdown"
    )

# --- BOSHQA FOYDALANUVCHI HANDLERLARI ---
@dp.message(F.text.in_({'\U0001F4CA Mening statistikam', '\U0001F4CA Моя статистика', '\U0001F4CA 내 통계'}))
async def my_stats(message: types.Message):
    user_id = message.from_user.id
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
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
        text += f"\U0001F3E2 {branch}\n"
        
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
            
            text += f"   \U0001F4C5 {month_display}\n"
            
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
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
    # Barcha tugmalarni bitta builderda yig'amiz
    builder = InlineKeyboardBuilder()
    
    for loc in LOCATIONS:
        maps_link = get_yandex_maps_link(loc['lat'], loc['lon'])
        builder.row(
            InlineKeyboardButton(text=f"\U0001F4CD {loc['name']}", url=maps_link)
        )
    
    await message.answer(
        "\U0001F3E2 Mavjud filiallar (lokatsiya uchun bosing):",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text.in_({'\u2753 Yordam', '\u2753 Помощь', '\u2753 도움말'}))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
    await message.answer(
        get_text(user_id, 'help'),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'\U0001F3C6 Hafta topi', '\U0001F3C6 Топ недели', '\U0001F3C6 주간 TOP'}))
async def weekly_top(message: types.Message):
    user_id = message.from_user.id
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
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
            name = user_names.get(uid, f"ID: {uid}")
            specialty = user_specialty.get(uid, '')
            specialty_display = f" [{specialty}]" if specialty else ""
        except:
            name = f"Foydalanuvchi {uid}"
            specialty_display = ""
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        top_list += f"{medal} {name}{specialty_display}: **{count}** marta\n"
    
    await message.answer(
        get_text(user_id, 'weekly_top', top_list=top_list),
        parse_mode="Markdown"
    )

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    user_ids.add(user_id)
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
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
        full_name = user_names.get(user_id, message.from_user.full_name)
        specialty = user_specialty.get(user_id, '')
        specialty_display = f" [{specialty}]" if specialty else ""
        
        # Admin guruhiga hisobot
        report = (
            f"✅ Yangi Davomat\n\n"
            f"👤 O'qituvchi: {full_name}{specialty_display}\n"
            f"\U0001F4CD Manzil: {found_branch}\n"
            f"\U0001F4C5 Sana: {today_date}\n"
            f"⏰ Vaqt: {now_time}\n"
            f"\U0001F4CA Shu oydagi tashrif: {visit_number}-marta\n"
            f"\U0001F4CD Masofa: {min_distance:.1f} metr"
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

# --- ADMIN PANEL - YANGILANGAN ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Admin panel asosiy menyusi"""
    if not check_admin(message.chat.id):
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats_main"),
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users_main")
        )
        builder.row(
            InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="📅 Dars jadvallari", callback_data="admin_schedules_main")
        )
        builder.row(
            InlineKeyboardButton(text="🏢 Filiallar", callback_data="admin_locations_main"),
            InlineKeyboardButton(text="📊 PDF Hisobot", callback_data="admin_pdf_report")
        )
        
        await message.answer(
            "👨‍💼 Admin Panel\n\nKerakli bo'limni tanlang:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"admin_panel error: {e}")
        await message.answer("❌ Admin panelni ochishda xatolik yuz berdi")

# --- 1. STATISTIKA BO'LIMI ---
@dp.callback_query(F.data == "admin_stats_main")
async def admin_stats_main(callback: types.CallbackQuery):
    """Statistika asosiy menyusi"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Umumiy statistika", callback_data="admin_stats_general"),
            InlineKeyboardButton(text="🏆 Filiallar reytingi", callback_data="admin_stats_branches")
        )
        builder.row(
            InlineKeyboardButton(text="👥 O'qituvchilar reytingi", callback_data="admin_stats_teachers"),
            InlineKeyboardButton(text="📅 Oylik hisobot", callback_data="admin_monthly")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_back")
        )
        
        await callback.message.edit_text(
            "📊 Statistika bo'limi\n\nKerakli statistikani tanlang:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_stats_main error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data == "admin_stats_general")
async def admin_stats_general(callback: types.CallbackQuery):
    """Umumiy statistika"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        now_uzb = datetime.now(UZB_TZ)
        today = now_uzb.strftime("%Y-%m-%d")
        current_month = now_uzb.strftime("%Y-%m")
        
        total_users = len(user_ids)
        active_users = len([uid for uid in user_ids if user_status.get(uid) == 'active'])
        blocked_users = len([uid for uid in user_ids if user_status.get(uid) == 'blocked'])
        total_attendances = len(daily_attendance_log)
        today_attendances = len([k for k in daily_attendance_log if k[2] == today])
        monthly_attendances = len([k for k in daily_attendance_log if k[2].startswith(current_month)])
        
        # IT va Koreys tili o'qituvchilari soni
        it_teachers = len([uid for uid in user_ids if user_specialty.get(uid) == 'IT'])
        korean_teachers = len([uid for uid in user_ids if user_specialty.get(uid) == 'Koreys tili'])
        
        # Eng faol filial
        branch_stats = defaultdict(int)
        for (uid, branch, date, time) in daily_attendance_log:
            branch_stats[branch] += 1
        top_branch = max(branch_stats.items(), key=lambda x: x[1]) if branch_stats else ("Yo'q", 0)
        
        # Eng faol o'qituvchi
        teacher_stats = defaultdict(int)
        for (uid, branch, date, time) in daily_attendance_log:
            teacher_stats[uid] += 1
        top_teacher_id = max(teacher_stats.items(), key=lambda x: x[1]) if teacher_stats else (None, 0)
        top_teacher_name = user_names.get(top_teacher_id[0], "Noma'lum") if top_teacher_id[0] else "Yo'q"
        top_teacher_specialty = user_specialty.get(top_teacher_id[0], '')
        top_teacher_display = f"{top_teacher_name} [{top_teacher_specialty}]" if top_teacher_specialty else top_teacher_name
        
        text = f"""
📊 Umumiy statistika

👥 Foydalanuvchilar:
• Jami: {total_users}
• Faol: {active_users}
• Bloklangan: {blocked_users}
• 💻 IT: {it_teachers}
• 🇰🇷 Koreys tili: {korean_teachers}

📋 Davomatlar:
• Jami: {total_attendances}
• Bugun: {today_attendances}
• Shu oyda: {monthly_attendances}

🏆 Eng faol filial: {top_branch[0]} ({top_branch[1]} ta)

👑 Eng faol o'qituvchi: {top_teacher_display} ({top_teacher_id[1]} ta)

📅 Oxirgi yangilanish: {now_uzb.strftime('%Y-%m-%d %H:%M')}
"""
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_stats_main"))
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_stats_general error: {e}")
        await callback.message.edit_text("❌ Statistikani olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data == "admin_stats_branches")
async def admin_stats_branches(callback: types.CallbackQuery):
    """Filiallar reytingi"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        branch_stats = defaultdict(int)
        for (uid, branch, date, time) in daily_attendance_log:
            branch_stats[branch] += 1
        
        if not branch_stats:
            await callback.message.edit_text("📭 Hali davomat ma'lumotlari yo'q.")
            await callback.answer()
            return
        
        sorted_branches = sorted(branch_stats.items(), key=lambda x: x[1], reverse=True)
        
        text = "🏆 Filiallar reytingi\n\n"
        for i, (branch, count) in enumerate(sorted_branches, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {branch}: {count} ta davomat\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_stats_main"))
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_stats_branches error: {e}")
        await callback.message.edit_text("❌ Filiallar reytingini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data == "admin_stats_teachers")
async def admin_stats_teachers(callback: types.CallbackQuery):
    """O'qituvchilar reytingi"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        teacher_stats = defaultdict(int)
        for (uid, branch, date, time) in daily_attendance_log:
            teacher_stats[uid] += 1
        
        if not teacher_stats:
            await callback.message.edit_text("📭 Hali davomat ma'lumotlari yo'q.")
            await callback.answer()
            return
        
        sorted_teachers = sorted(teacher_stats.items(), key=lambda x: x[1], reverse=True)[:20]
        
        text = "👥 Eng faol o'qituvchilar\n\n"
        for i, (uid, count) in enumerate(sorted_teachers, 1):
            name = user_names.get(uid, f"ID: {uid}")
            specialty = user_specialty.get(uid, '')
            specialty_display = f" [{specialty}]" if specialty else ""
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {name}{specialty_display}: {count} ta davomat\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_stats_main"))
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_stats_teachers error: {e}")
        await callback.message.edit_text("❌ O'qituvchilar reytingini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data == "admin_monthly")
async def admin_monthly(callback: types.CallbackQuery):
    """Oylik hisobot"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        now_uzb = datetime.now(UZB_TZ)
        current_month = now_uzb.strftime("%Y-%m")
        month_name = now_uzb.strftime("%B %Y")
        
        monthly_stats = defaultdict(lambda: defaultdict(int))
        for (uid, branch, date, time) in daily_attendance_log:
            if date.startswith(current_month):
                monthly_stats[branch][uid] += 1
        
        if not monthly_stats:
            await callback.message.edit_text("📭 Shu oy uchun davomat ma'lumotlari yo'q.")
            await callback.answer()
            return
        
        report = f"📊 {month_name} oyi uchun hisobot\n\n"
        
        for branch, users in monthly_stats.items():
            total = sum(users.values())
            unique_users = len(users)
            report += f"\U0001F3E2 {branch}\n"
            report += f"   Jami: {total} ta davomat\n"
            report += f"   O'qituvchilar: {unique_users} ta\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_stats_main"))
        
        await callback.message.edit_text(
            report,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_monthly error: {e}")
        await callback.message.edit_text("❌ Oylik hisobotni olishda xatolik yuz berdi")
        await callback.answer()

# --- 2. FOYDALANUVCHILARNI BOSHQARISH (FAQAT FAOLLAR VA BLOKLANGANLAR) ---
@dp.callback_query(F.data == "admin_users_main")
async def admin_users_main(callback: types.CallbackQuery):
    """Foydalanuvchilarni boshqarish menyusi"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Foydalanuvchilar ro'yxati", callback_data="admin_users_active")
        )
        builder.row(
            InlineKeyboardButton(text="⛔ Bloklanganlar", callback_data="admin_users_blocked")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_back")
        )
        
        await callback.message.edit_text(
            "👥 Foydalanuvchilarni boshqarish\n\nKerakli amalni tanlang:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_users_main error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data.startswith("admin_user_info_"))
async def admin_user_info(callback: types.CallbackQuery):
    """Foydalanuvchi haqida ma'lumot"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        uid = int(callback.data.replace("admin_user_info_", ""))
        name = user_names.get(uid, "Noma'lum")
        status = user_status.get(uid, 'active')
        lang = user_languages.get(uid, 'uz')
        specialty = user_specialty.get(uid, '')
        specialty_display = f" [{specialty}]" if specialty else ""
        
        # Foydalanuvchi statistikasi
        user_attendances = len([k for k in daily_attendance_log if k[0] == uid])
        user_schedules_count = len(user_schedules.get(uid, []))
        
        # Oxirgi davomat
        last_attendance = "Yo'q"
        user_logs = [k for k in daily_attendance_log if k[0] == uid]
        if user_logs:
            last = max(user_logs, key=lambda x: x[2])
            last_attendance = f"{last[2]} {last[3]} ({last[1]})"
        
        text = f"""
👤 Foydalanuvchi ma'lumoti

ID: `{uid}`
Ism: {name}{specialty_display}
Holat: {"✅ Faol" if status == 'active' else "⛔ Bloklangan"}
Til: {lang}

📊 Statistika:
• Jami davomatlar: {user_attendances}
• Dars jadvallari: {user_schedules_count}
• Oxirgi davomat: {last_attendance}
"""
        
        builder = InlineKeyboardBuilder()
        if status == 'active':
            builder.row(InlineKeyboardButton(text="⛔ Bloklash", callback_data=f"admin_user_block_{uid}"))
        else:
            builder.row(InlineKeyboardButton(text="✅ Faollashtirish", callback_data=f"admin_user_unblock_{uid}"))
        builder.row(
            InlineKeyboardButton(text="📊 Statistika", callback_data=f"admin_user_stats_{uid}"),
        )
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_users_main"))
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_user_info error: {e}")
        await callback.message.edit_text("❌ Foydalanuvchi ma'lumotlarini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data.startswith("admin_user_block_"))
async def admin_user_block(callback: types.CallbackQuery):
    """Foydalanuvchini bloklash"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        uid = int(callback.data.replace("admin_user_block_", ""))
        user_status[uid] = 'blocked'
        
        await callback.answer("✅ Foydalanuvchi bloklandi!")
        await admin_user_info(callback)
    except Exception as e:
        logging.error(f"admin_user_block error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data.startswith("admin_user_unblock_"))
async def admin_user_unblock(callback: types.CallbackQuery):
    """Foydalanuvchini faollashtirish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        uid = int(callback.data.replace("admin_user_unblock_", ""))
        user_status[uid] = 'active'
        
        await callback.answer("✅ Foydalanuvchi faollashtirildi!")
        await admin_user_info(callback)
    except Exception as e:
        logging.error(f"admin_user_unblock error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data.startswith("admin_user_stats_"))
async def admin_user_stats(callback: types.CallbackQuery):
    """Foydalanuvchi statistikasi"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        uid = int(callback.data.replace("admin_user_stats_", ""))
        name = user_names.get(uid, "Noma'lum")
        
        # Filiallar bo'yicha davomatlar
        branch_stats = defaultdict(int)
        month_stats = defaultdict(int)
        
        for (user_id, branch, date, time) in daily_attendance_log:
            if user_id == uid:
                branch_stats[branch] += 1
                month = date[:7]
                month_stats[month] += 1
        
        text = f"📊 {name} statistikasi\n\n"
        
        if branch_stats:
            text += "🏢 Filiallar bo'yicha:\n"
            for branch, count in sorted(branch_stats.items(), key=lambda x: x[1], reverse=True):
                text += f"• {branch}: {count} ta\n"
            text += "\n"
        
        if month_stats:
            text += "📅 Oylar bo'yicha:\n"
            for month, count in sorted(month_stats.items(), reverse=True):
                text += f"• {month}: {count} ta\n"
        else:
            text += "📭 Hali davomat yo'q"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data=f"admin_user_info_{uid}"))
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_user_stats error: {e}")
        await callback.message.edit_text("❌ Foydalanuvchi statistikasini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data == "admin_users_active")
async def admin_users_active(callback: types.CallbackQuery):
    """Faol foydalanuvchilar ro'yxati"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        active = [uid for uid in user_ids if user_status.get(uid) != 'blocked']
        
        if not active:
            await callback.message.edit_text("📭 Faol foydalanuvchilar yo'q.")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for uid in sorted(active)[:20]:  # Eng ko'pi 20 ta
            name = user_names.get(uid, f"ID: {uid}")
            specialty = user_specialty.get(uid, '')
            specialty_display = f" [{specialty}]" if specialty else ""
            builder.row(
                InlineKeyboardButton(text=f"✅ {name}{specialty_display}", callback_data=f"admin_user_info_{uid}")
            )
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_users_main"))
        
        await callback.message.edit_text(
            "✅ Faol foydalanuvchilar ro'yxati:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_users_active error: {e}")
        await callback.message.edit_text("❌ Faol foydalanuvchilar ro'yxatini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data == "admin_users_blocked")
async def admin_users_blocked(callback: types.CallbackQuery):
    """Bloklangan foydalanuvchilar"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        blocked = [uid for uid in user_ids if user_status.get(uid) == 'blocked']
        
        if not blocked:
            await callback.message.edit_text("📭 Bloklangan foydalanuvchilar yo'q.")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for uid in blocked[:20]:
            name = user_names.get(uid, f"ID: {uid}")
            specialty = user_specialty.get(uid, '')
            specialty_display = f" [{specialty}]" if specialty else ""
            builder.row(
                InlineKeyboardButton(text=f"⛔ {name}{specialty_display}", callback_data=f"admin_user_info_{uid}")
            )
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_users_main"))
        
        await callback.message.edit_text(
            "⛔ Bloklangan foydalanuvchilar:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_users_blocked error: {e}")
        await callback.message.edit_text("❌ Bloklangan foydalanuvchilar ro'yxatini olishda xatolik yuz berdi")
        await callback.answer()

# --- 3. XABAR YUBORISH (BROADCAST) - MUTAXASSISLIK BO'YICHA ---
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    """Broadcast xabar yuborish - mutaxassislik tanlash"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        user_id = callback.from_user.id
        lang = user_languages.get(user_id, 'uz')
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=TRANSLATIONS[lang]['specialty_it'], callback_data="broadcast_spec_IT"),
            InlineKeyboardButton(text=TRANSLATIONS[lang]['specialty_korean'], callback_data="broadcast_spec_Koreys tili")
        )
        builder.row(
            InlineKeyboardButton(text=TRANSLATIONS[lang]['all_teachers'], callback_data="broadcast_spec_all")
        )
        
        await state.set_state(Broadcast.selecting_specialty)
        await callback.message.edit_text(
            get_text(user_id, 'select_broadcast_specialty'),
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_broadcast_start error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(Broadcast.selecting_specialty, F.data.startswith("broadcast_spec_"))
async def admin_broadcast_specialty(callback: types.CallbackQuery, state: FSMContext):
    """Mutaxassislik tanlangandan keyin"""
    try:
        specialty = callback.data.replace("broadcast_spec_", "")
        if specialty == "all":
            specialty = None
        
        await state.update_data(specialty=specialty)
        await state.set_state(Broadcast.waiting_for_message)
        
        await callback.message.edit_text(
            "📢 Xabar yuborish\n\nYubormoqchi bo'lgan xabaringizni kiriting (matn, rasm, hujjat):"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_broadcast_specialty error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.message(Broadcast.waiting_for_message)
async def admin_broadcast_message(message: types.Message, state: FSMContext):
    """Broadcast xabar matnini qabul qilish"""
    if not check_admin(message.chat.id):
        await state.clear()
        return
    
    try:
        # Xabarni saqlash
        await state.update_data(
            message_text=message.text or message.caption,
            message_type=message.content_type,
            message_data=message
        )
        
        # Tasdiqlash
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Ha", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="broadcast_cancel")
        )
        
        data = await state.get_data()
        specialty = data.get('specialty')
        
        if specialty:
            target_users = [uid for uid in user_ids if user_status.get(uid) != 'blocked' and user_specialty.get(uid) == specialty]
            specialty_text = f" ({specialty})"
        else:
            target_users = [uid for uid in user_ids if user_status.get(uid) != 'blocked']
            specialty_text = " (barcha)"
        
        total_users = len(target_users)
        
        await state.set_state(Broadcast.waiting_for_confirm)
        await message.answer(
            f"📢 Xabar yuborishni tasdiqlang{specialty_text}\n\n"
            f"Xabar: {message.text or 'Rasm/hujjat'}\n"
            f"Qabul qiluvchilar: {total_users} ta foydalanuvchi\n\n"
            f"Yuborishni boshlaymizmi?",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"admin_broadcast_message error: {e}")
        await message.answer("❌ Xatolik yuz berdi")
        await state.clear()

@dp.callback_query(Broadcast.waiting_for_confirm, F.data == "broadcast_confirm")
async def admin_broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Broadcast xabarni yuborish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        data = await state.get_data()
        specialty = data.get('specialty')
        
        if specialty:
            target_users = [uid for uid in user_ids if user_status.get(uid) != 'blocked' and user_specialty.get(uid) == specialty]
        else:
            target_users = [uid for uid in user_ids if user_status.get(uid) != 'blocked']
        
        await callback.message.edit_text("⏳ Xabarlar yuborilmoqda...")
        
        sent_count = 0
        failed_count = 0
        
        for user_id in target_users:
            try:
                msg_data = data['message_data']
                if data['message_type'] == 'text':
                    await bot.send_message(user_id, msg_data.text)
                elif data['message_type'] == 'photo':
                    await bot.send_photo(user_id, msg_data.photo[-1].file_id, caption=msg_data.caption)
                elif data['message_type'] == 'document':
                    await bot.send_document(user_id, msg_data.document.file_id, caption=msg_data.caption)
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                failed_count += 1
                logging.error(f"Broadcast error for user {user_id}: {e}")
        
        broadcast_history.append({
            'text': data.get('message_text', ''),
            'date': datetime.now(UZB_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            'sent_count': sent_count,
            'failed_count': failed_count,
            'specialty': specialty
        })
        
        specialty_text = f" ({specialty})" if specialty else " (barcha)"
        
        await callback.message.edit_text(
            f"✅ Xabar yuborildi{specialty_text}!\n\n"
            f"✓ Yuborildi: {sent_count}\n"
            f"✗ Xatolik: {failed_count}"
        )
        
        await state.clear()
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_broadcast_confirm error: {e}")
        await callback.message.edit_text("❌ Xabar yuborishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(Broadcast.waiting_for_confirm, F.data == "broadcast_cancel")
async def admin_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Broadcast xabarni bekor qilish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        await state.clear()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back"))
        
        await callback.message.edit_text(
            "❌ Xabar yuborish bekor qilindi.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_broadcast_cancel error: {e}")
        await callback.answer("Xatolik yuz berdi")

# --- 4. DARS JADVALLARI (ADMIN UCHUN) - O'ZGARTIRISH VA O'CHIRISH TUGMALARI BILAN ---
@dp.callback_query(F.data == "admin_schedules_main")
async def admin_schedules_main(callback: types.CallbackQuery):
    """Dars jadvallarini boshqarish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="➕ O'qituvchiga jadval qo'shish", callback_data="admin_add_schedule")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Faol dars jadvallari", callback_data="admin_active_schedules")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_back")
        )
        
        await callback.message.edit_text(
            "📅 Dars jadvallarini boshqarish",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_schedules_main error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data == "admin_active_schedules")
async def admin_active_schedules(callback: types.CallbackQuery):
    """Barcha faol dars jadvallarini ko'rish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        if not schedules:
            await callback.message.edit_text("📭 Hali dars jadvallari mavjud emas.")
            await callback.answer()
            return
        
        # Har bir jadval uchun alohida xabar
        for schedule_id, schedule in schedules.items():
            teacher_name = user_names.get(schedule['user_id'], f"ID: {schedule['user_id']}")
            teacher_specialty = user_specialty.get(schedule['user_id'], '')
            specialty_display = f" [{teacher_specialty}]" if teacher_specialty else ""
            branch = schedule['branch']
            lesson_type = schedule.get('lesson_type', 'Dars')
            days_times = ""
            for day, time in sorted(schedule['days'].items(), key=lambda x: WEEKDAYS_UZ.index(x[0])):
                days_times += f"• {day}: {time}\n"
            
            text = get_text(callback.from_user.id, 'schedule_info', 
                           teacher=f"{teacher_name}{specialty_display}", 
                           branch=branch, 
                           lesson_type=lesson_type, 
                           days_times=days_times)
            
            # O'zgartirish va o'chirish tugmalari
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="✏️ O'zgartirish", callback_data=f"admin_edit_schedule_{schedule_id}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_delete_schedule_{schedule_id}")
            )
            
            await callback.message.answer(
                text,
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_active_schedules error: {e}")
        await callback.message.edit_text("❌ Dars jadvallarini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data.startswith("admin_delete_schedule_"))
async def admin_delete_schedule(callback: types.CallbackQuery):
    """Dars jadvalini o'chirish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        schedule_id = callback.data.replace("admin_delete_schedule_", "")
        
        if schedule_id in schedules:
            schedule = schedules[schedule_id]
            teacher_id = schedule['user_id']
            
            # O'qituvchiga xabar yuborish
            try:
                lang = user_languages.get(teacher_id, 'uz')
                await bot.send_message(
                    teacher_id,
                    get_text(teacher_id, 'schedule_deleted_notify'),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Failed to notify teacher {teacher_id}: {e}")
            
            # Jadvalni o'chirish
            del schedules[schedule_id]
            if teacher_id in user_schedules and schedule_id in user_schedules[teacher_id]:
                user_schedules[teacher_id].remove(schedule_id)
            
            await callback.message.edit_text("✅ Dars jadvali o'chirildi!")
        else:
            await callback.message.edit_text("❌ Jadval topilmadi!")
        
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_delete_schedule error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data == "admin_add_schedule")
async def admin_add_schedule_start(callback: types.CallbackQuery, state: FSMContext):
    """Admin o'qituvchiga jadval qo'shish - o'qituvchini tanlash"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        # Faol o'qituvchilar ro'yxati
        builder = InlineKeyboardBuilder()
        for uid in user_ids:
            if user_status.get(uid) != 'blocked':
                name = user_names.get(uid, f"ID: {uid}")
                specialty = user_specialty.get(uid, '')
                specialty_display = f" [{specialty}]" if specialty else ""
                builder.row(
                    InlineKeyboardButton(text=f"👤 {name}{specialty_display}", callback_data=f"admin_teacher_{uid}")
                )
        
        if not builder.buttons:
            await callback.message.edit_text("📭 Faol o'qituvchilar yo'q.")
            await callback.answer()
            return
        
        await state.set_state(AdminAddSchedule.selecting_teacher)
        await callback.message.edit_text(
            "👤 O'qituvchini tanlang:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_add_schedule_start error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(AdminAddSchedule.selecting_teacher, F.data.startswith("admin_teacher_"))
async def admin_add_schedule_teacher(callback: types.CallbackQuery, state: FSMContext):
    """O'qituvchi tanlangandan keyin"""
    try:
        teacher_id = int(callback.data.replace("admin_teacher_", ""))
        await state.update_data(teacher_id=teacher_id)
        
        # Filiallar ro'yxati
        builder = InlineKeyboardBuilder()
        for location in LOCATIONS:
            builder.row(
                InlineKeyboardButton(text=location['name'], callback_data=f"admin_branch_{location['name']}")
            )
        
        await state.set_state(AdminAddSchedule.selecting_branch)
        await callback.message.edit_text(
            "🏢 Filialni tanlang:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_add_schedule_teacher error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(AdminAddSchedule.selecting_branch, F.data.startswith("admin_branch_"))
async def admin_add_schedule_branch(callback: types.CallbackQuery, state: FSMContext):
    """Filial tanlangandan keyin"""
    try:
        branch = callback.data.replace("admin_branch_", "")
        await state.update_data(branch=branch)
        
        user_id = callback.from_user.id
        lang = user_languages.get(user_id, 'uz')
        lesson_types = LESSON_TYPES.get(lang, LESSON_TYPES['uz'])
        
        # Dars turini tanlash
        builder = InlineKeyboardBuilder()
        for lesson in lesson_types:
            builder.row(
                InlineKeyboardButton(text=lesson, callback_data=f"admin_lesson_{lesson}")
            )
        
        await state.set_state(AdminAddSchedule.selecting_lesson_type)
        await callback.message.edit_text(
            "📚 Dars turini tanlang:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_add_schedule_branch error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(AdminAddSchedule.selecting_lesson_type, F.data.startswith("admin_lesson_"))
async def admin_add_schedule_lesson(callback: types.CallbackQuery, state: FSMContext):
    """Dars turi tanlangandan keyin"""
    try:
        lesson_type = callback.data.replace("admin_lesson_", "")
        await state.update_data(lesson_type=lesson_type)
        
        user_id = callback.from_user.id
        lang = user_languages.get(user_id, 'uz')
        weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
        
        # Hafta kunlarini tanlash
        builder = InlineKeyboardBuilder()
        for i, day in enumerate(weekdays):
            builder.row(
                InlineKeyboardButton(text=f"⬜ {day}", callback_data=f"admin_weekday_{i}")
            )
        builder.row(
            InlineKeyboardButton(text="➡️ Keyingisi", callback_data="admin_weekdays_next")
        )
        
        await state.update_data(selected_days={})
        await state.set_state(AdminAddSchedule.selecting_weekdays)
        await callback.message.edit_text(
            "📅 Qaysi kunlarda dars bor?",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_add_schedule_lesson error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(AdminAddSchedule.selecting_weekdays, F.data.startswith("admin_weekday_"))
async def admin_add_schedule_weekday_select(callback: types.CallbackQuery, state: FSMContext):
    """Kunlarni tanlash"""
    try:
        data = await state.get_data()
        selected_days = data.get('selected_days', {})
        day_index = int(callback.data.replace("admin_weekday_", ""))
        
        user_id = callback.from_user.id
        lang = user_languages.get(user_id, 'uz')
        weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
        
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
                    InlineKeyboardButton(text=f"✅ {day}", callback_data=f"admin_weekday_{i}")
                )
            else:
                builder.row(
                    InlineKeyboardButton(text=f"⬜ {day}", callback_data=f"admin_weekday_{i}")
                )
        builder.row(
            InlineKeyboardButton(text="➡️ Keyingisi", callback_data="admin_weekdays_next")
        )
        
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_add_schedule_weekday_select error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(AdminAddSchedule.selecting_weekdays, F.data == "admin_weekdays_next")
async def admin_add_schedule_weekdays_next(callback: types.CallbackQuery, state: FSMContext):
    """Kunlar tanlangandan keyin vaqt kiritish"""
    try:
        data = await state.get_data()
        selected_days = data.get('selected_days', {})
        
        if not selected_days:
            await callback.answer("Hech bo'lmaganda 1 kun tanlang!", show_alert=True)
            return
        
        days_without_time = [day for day in selected_days if selected_days[day] is None]
        
        if days_without_time:
            await state.update_data(current_day=days_without_time[0])
            await state.set_state(AdminAddSchedule.entering_time)
            
            user_id = callback.from_user.id
            lang = user_languages.get(user_id, 'uz')
            weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
            day_name = weekdays[days_without_time[0]]
            
            await callback.message.edit_text(
                f"⏰ {day_name} kuni soat nechida?\n\nFormat: HH:MM (masalan: 09:00)"
            )
        else:
            await admin_save_schedule(callback.message, state, is_new=True)
        
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_add_schedule_weekdays_next error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.message(AdminAddSchedule.entering_time)
async def admin_add_schedule_enter_time(message: types.Message, state: FSMContext):
    """Vaqt kiritish"""
    try:
        time_str = message.text.strip()
        hours, minutes = map(int, time_str.split(':'))
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            raise ValueError
        formatted_time = f"{hours:02d}:{minutes:02d}"
    except:
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
            f"⏰ {day_name} kuni soat nechida?\n\nFormat: HH:MM (masalan: 09:00)"
        )
    else:
        await admin_save_schedule(message, state, is_new=True)

async def admin_save_schedule(message: types.Message, state: FSMContext, is_new: bool = True):
    """Admin tomonidan kiritilgan jadvalni saqlash"""
    try:
        data = await state.get_data()
        teacher_id = data.get('teacher_id')
        branch = data.get('branch')
        lesson_type = data.get('lesson_type')
        selected_days = data.get('selected_days', {})
        
        user_id = message.from_user.id
        lang = user_languages.get(user_id, 'uz')
        weekdays = WEEKDAYS.get(lang, WEEKDAYS['uz'])
        
        schedule_id = f"schedule_{teacher_id}_{datetime.now().timestamp()}"
        
        days_with_names = {}
        for day_index, time in selected_days.items():
            day_name = weekdays[day_index]
            days_with_names[day_name] = time
        
        schedules[schedule_id] = {
            'user_id': teacher_id,
            'branch': branch,
            'lesson_type': lesson_type,
            'days': days_with_names
        }
        user_schedules[teacher_id].append(schedule_id)
        
        teacher_name = user_names.get(teacher_id, f"ID: {teacher_id}")
        days_list = ", ".join(days_with_names.keys())
        times_list = ", ".join(days_with_names.values())
        
        # O'qituvchiga xabar yuborish
        try:
            schedule_text = ""
            for day, time in sorted(days_with_names.items(), key=lambda x: WEEKDAYS_UZ.index(x[0])):
                schedule_text += f"• {day}: {time}\n"
            
            await bot.send_message(
                teacher_id,
                get_text(teacher_id, 'schedule_updated', schedule=f"🏢 {branch} - {lesson_type}\n{schedule_text}"),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to notify teacher {teacher_id}: {e}")
        
        await message.answer(
            f"✅ Dars jadvali muvaffaqiyatli qo'shildi!\n\n"
            f"👤 O'qituvchi: {teacher_name}\n"
            f"🏢 Filial: {branch}\n"
            f"📚 Dars turi: {lesson_type}\n"
            f"📆 Kunlar: {days_list}\n"
            f"⏰ Vaqtlar: {times_list}"
        )
        
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back"))
        await message.answer("Admin panelga qaytish:", reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"admin_save_schedule error: {e}")
        await message.answer("❌ Jadvalni saqlashda xatolik yuz berdi")
        await state.clear()

# --- 5. FILIALLAR (ADMIN UCHUN) ---
@dp.callback_query(F.data == "admin_locations_main")
async def admin_locations_main(callback: types.CallbackQuery):
    """Filiallarni boshqarish menyusi"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="➕ Yangi filial qo'shish", callback_data="admin_location_add"),
            InlineKeyboardButton(text="📋 Barcha filiallar", callback_data="admin_location_list")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_back")
        )
        
        await callback.message.edit_text(
            "🏢 Filiallarni boshqarish",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_locations_main error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.callback_query(F.data == "admin_location_list")
async def admin_location_list(callback: types.CallbackQuery):
    """Barcha filiallar ro'yxati - LINK SHAKLIDA"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        builder = InlineKeyboardBuilder()
        
        for loc in LOCATIONS:
            maps_link = get_yandex_maps_link(loc['lat'], loc['lon'])
            builder.row(
                InlineKeyboardButton(text=f"\U0001F4CD {loc['name']}", url=maps_link)
            )
        
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_locations_main"))
        
        await callback.message.edit_text(
            "📋 Barcha filiallar (lokatsiya uchun bosing):",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_location_list error: {e}")
        await callback.message.edit_text("❌ Filiallar ro'yxatini olishda xatolik yuz berdi")
        await callback.answer()

@dp.callback_query(F.data == "admin_location_add")
async def admin_location_add_start(callback: types.CallbackQuery, state: FSMContext):
    """Yangi filial qo'shish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        await state.set_state(AddLocation.waiting_for_name)
        await callback.message.edit_text(
            "🏢 Yangi filial nomini kiriting:"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_location_add_start error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.message(AddLocation.waiting_for_name)
async def admin_location_add_name(message: types.Message, state: FSMContext):
    """Filial nomini qabul qilish"""
    if not check_admin(message.chat.id):
        await state.clear()
        return
    
    try:
        await state.update_data(name=message.text.strip())
        await state.set_state(AddLocation.waiting_for_coords)
        await message.answer(
            "📍 Filial koordinatalarini kiriting (format: lat,lon)\n"
            "Masalan: 41.315790,69.209515"
        )
    except Exception as e:
        logging.error(f"admin_location_add_name error: {e}")
        await message.answer("❌ Xatolik yuz berdi")
        await state.clear()

@dp.message(AddLocation.waiting_for_coords)
async def admin_location_add_coords(message: types.Message, state: FSMContext):
    """Filial koordinatalarini qabul qilish"""
    if not check_admin(message.chat.id):
        await state.clear()
        return
    
    try:
        lat, lon = map(float, message.text.strip().split(','))
        data = await state.get_data()
        name = data['name']
        
        # Yangi filialni qo'shish
        LOCATIONS.append({"name": name, "lat": lat, "lon": lon})
        
        await message.answer(f"✅ Filial muvaffaqiyatli qo'shildi!\n\n{name}\n📍 {lat}, {lon}")
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back"))
        await message.answer("Admin panelga qaytish:", reply_markup=builder.as_markup())
        
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}\nQaytadan urinib ko'ring.")
        return
    
    await state.clear()

# --- 6. PDF HISOBOT (ORTGA QAYTISH TUGMASISIZ) ---
@dp.callback_query(F.data == "admin_pdf_report")
async def admin_pdf_report_start(callback: types.CallbackQuery, state: FSMContext):
    """PDF hisobot - sanani kiritish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        await state.set_state(PDFReport.waiting_for_date)
        await callback.message.edit_text(
            "📅 Hisobot olish uchun sanani kiriting (format: YYYY-MM-DD)\n"
            "Masalan: 2026-03-01"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_pdf_report_start error: {e}")
        await callback.answer("Xatolik yuz berdi")

@dp.message(PDFReport.waiting_for_date)
async def admin_pdf_report_date(message: types.Message, state: FSMContext):
    """Sanani qabul qilish va PDF yaratish"""
    if not check_admin(message.chat.id):
        await state.clear()
        return
    
    try:
        date_str = message.text.strip()
        # Sanani tekshirish
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        report_date_str = report_date.strftime("%Y-%m-%d")
        
        await message.answer("⏳ PDF hisobot yaratilmoqda...")
        
        # Shu kungi davomatlar
        day_attendances = []
        for att in daily_attendance_log:
            if att[2] == report_date_str:
                day_attendances.append(att)
        
        # PDF yaratish
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()
        
        # Sarlavha
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            alignment=1,
            spaceAfter=30
        )
        elements.append(Paragraph(f"Davomat Hisoboti - {report_date.strftime('%d.%m.%Y')}", title_style))
        
        elements.append(Paragraph(f"Hisobot yaratilgan vaqt: {datetime.now(UZB_TZ).strftime('%H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Umumiy statistika
        total_attendances = len(day_attendances)
        unique_teachers = len(set(att[0] for att in day_attendances))
        unique_branches = len(set(att[1] for att in day_attendances))
        
        stats_data = [
            ['Ko\'rsatkich', 'Qiymat'],
            ['Jami davomatlar', str(total_attendances)],
            ['O\'qituvchilar soni', str(unique_teachers)],
            ['Filiallar soni', str(unique_branches)],
            ['Sana', report_date.strftime('%d.%m.%Y')]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
        
        # Batafsil davomatlar jadvali
        if day_attendances:
            elements.append(Paragraph(f"{report_date.strftime('%d.%m.%Y')} dagi davomatlar", styles['Heading2']))
            
            data = [['№', 'Vaqt', 'O\'qituvchi', 'Mutaxassislik', 'Filial']]
            for i, (uid, branch, date, time) in enumerate(sorted(day_attendances, key=lambda x: x[3]), 1):
                teacher_name = user_names.get(uid, f"ID: {uid}")
                specialty = user_specialty.get(uid, '')
                data.append([str(i), time, teacher_name, specialty, branch])
            
            table = Table(data, colWidths=[0.5*inch, 1*inch, 2*inch, 1.5*inch, 2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 10)
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("Bu kunda davomat yo'q", styles['Normal']))
        
        # PDF ni saqlash
        doc.build(elements)
        pdf_buffer.seek(0)
        
        await message.answer_document(
            types.BufferedInputFile(pdf_buffer.getvalue(), 
                                    filename=f"davomat_{report_date_str}.pdf"),
            caption=f"📊 {report_date.strftime('%d.%m.%Y')} kunlik davomat hisoboti"
        )
        
        await state.clear()
        
        # Ortga qaytish tugmasisiz, admin panelga qaytish uchun alohida xabar
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back"))
        await message.answer("Admin panelga qaytish:", reply_markup=builder.as_markup())
        
    except ValueError:
        await message.answer("❌ Noto'g'ri sana formati. Qaytadan urinib ko'ring:\nFormat: YYYY-MM-DD")
    except Exception as e:
        logging.error(f"admin_pdf_report_date error: {e}")
        await message.answer(f"❌ PDF yaratishda xatolik: {e}")
        await state.clear()

# --- 7. ORTGA QAYTISH ---
@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    """Admin panelga qaytish"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats_main"),
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users_main")
        )
        builder.row(
            InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="📅 Dars jadvallari", callback_data="admin_schedules_main")
        )
        builder.row(
            InlineKeyboardButton(text="🏢 Filiallar", callback_data="admin_locations_main"),
            InlineKeyboardButton(text="📊 PDF Hisobot", callback_data="admin_pdf_report")
        )
        
        await callback.message.edit_text(
            "👨‍💼 Admin Panel\n\nKerakli bo'limni tanlang:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_back error: {e}")
        await callback.message.edit_text("❌ Admin panelga qaytishda xatolik yuz berdi")
        await callback.answer()

# --- ESLATMA LOOPLARI ---
async def send_daily_reminders():
    """Har kuni soat 08:00 da eslatma yuborish"""
    now_uzb = datetime.now(UZB_TZ)
    today = now_uzb.strftime("%Y-%m-%d")
    
    sent_count = 0
    for user_id in user_ids:
        if user_status.get(user_id) == 'blocked':
            continue
        
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
        
        current_day_name = WEEKDAYS_UZ[current_weekday]
        
        for schedule_id, schedule in schedules.items():
            user_id = schedule['user_id']
            
            if user_status.get(user_id) == 'blocked':
                continue
            
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
