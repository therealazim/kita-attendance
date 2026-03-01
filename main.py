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
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import pickle
import asyncpg
from database import Database

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
TOKEN = "8268187024:AAGVlMOzOUTXMyrB8ePj9vHcayshkZ4PGW4"
ADMIN_GROUP_ID = -1003885800610 
UZB_TZ = pytz.timezone('Asia/Tashkent') 

# --- OB-HAVO SOZLAMALARI ---
WEATHER_API_KEY = "2b7818365e4ac19cebd34c34a135a669"
WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/weather"

# --- DATABASE SOZLAMALARI ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("⚠️ DATABASE_URL environment variable is not set! Bot RAM bilan ishlaydi.")
    db = None
else:
    db = Database(DATABASE_URL)

# Bot va Dispatcher obyektlarini yaratish
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Foydalanuvchi ism-familiyalarini saqlash uchun (RAM kesh)
user_names = {}  # {user_id: full_name}

# Foydalanuvchi mutaxassisligi (IT yoki Koreys tili)
user_specialty = {}  # {user_id: 'IT' or 'Koreys tili'}

# Foydalanuvchi holati (bloklangan, aktiv, etc.)
user_status = {}  # {user_id: 'active' or 'blocked'}

# Foydalanuvchi tili
user_languages = {}  # {user_id: 'uz' or 'ru' or 'kr'}

# Foydalanuvchi IDlari
user_ids = set()  # Barcha foydalanuvchilar ID si

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

# Davomatlar
daily_attendance_log = set()  # {(user_id, branch_name, date, time)}
attendance_counter = {}       # {(user_id, branch_name, month): count}

# Dars jadvallari uchun ma'lumotlar
schedules = {}  # {schedule_id: {'user_id': user_id, 'branch': branch, 'lesson_type': lesson_type, 'days': {weekday: time}}}
user_schedules = defaultdict(list)  # {user_id: [schedule_id1, schedule_id2, ...]}

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
    editing_branch = State()
    editing_lesson_type = State()
    editing_weekdays = State()
    editing_time = State()

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

# Hafta kunlari tartibi (saralash uchun)
WEEKDAY_ORDER = {
    'Dushanba': 0, 'Seshanba': 1, 'Chorshanba': 2, 'Payshanba': 3, 'Juma': 4, 'Shanba': 5, 'Yakshanba': 6
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
        'welcome': "🌟 HANCOM ACADEMYning o'qituvchilar uchun davomat botiga hush kelibsiz, {name}!",
        'ask_name': "👤 Iltimos, ism va familiyangizni kiriting:\n\nMasalan: Ali Karimov",
        'ask_specialty': "📚 Qaysi fan o'qituvchisisiz?",
        'specialty_it': "💻 IT",
        'specialty_korean': "🇰🇷 Koreys tili",
        'stats': "📊 Sizning statistikangiz:",
        'no_stats': "📭 Hali davomat qilmagansiz",
        'branches': "🏢 Mavjud filiallar (lokatsiya):",
        'help': "🤖 Botdan foydalanish qo'llanmasi:\n\n📍 Davomat qilish uchun:\n• Pastdagi \"📍 Kelganimni tasdiqlash\" tugmasini bosing\n• Joylashuvingizni yuboring\n\n📊 Statistika:\n• \"📊 Mening statistikam\" - shaxsiy davomat tarixingiz\n• \"🏢 Filiallar\" - barcha mavjud filiallar ro'yxati\n\n⚠️ Eslatmalar:\n• Har bir filialda kuniga faqat 1 marta davomat qilish mumkin\n• Davomat faqat Toshkent vaqti bilan hisoblanadi",
        'attendance_success': "✅ Davomat tasdiqlandi!\n\n🏫 Filial: {branch}\n📅 Sana: {date}\n⏰ Vaqt: {time}\n📊 Bu oydagi tashriflar: {count} marta\n📍 Masofa: {distance:.1f} metr",
        'already_attended': "⚠️ Siz bugun {branch} hududida allaqachon davomatdan o'tgansiz!",
        'not_in_area': "❌ Siz belgilangan ta'lim muassasalari hududida emassiz!",
        'daily_reminder': "⏰ Eslatma! Bugun hali davomat qilmagansiz. Ish kuningizni boshlash uchun davomatni tasdiqlang!",
        'weekly_top': "🏆 Haftaning eng faol o'qituvchilari:\n\n{top_list}",
        'monthly_report': "📊 {month} oyi uchun hisobot\n\n{report}",
        'language_changed': "✅ Til o'zgartirildi: O'zbek tili",
        'language_prompt': "Iltimos, tilni tanlang:",
        'view_schedules': "📋 Dars jadvalim (PDF)",
        'my_schedule': "📅 Sizning dars jadvalingiz PDF formatida tayyorlandi!",
        'no_schedules': "📭 Sizga hali dars jadvali biriktirilmagan.",
        'schedule_updated': "📢 Sizning dars jadvalingiz yangilandi!",
        'schedule_deleted_notify': "📢 Sizning dars jadvalingiz o'chirildi.",
        'reminder': "⏰ Eslatma!\n\nBugun soat {time} da {branch} filialida darsingiz bor.\nDavomat qilishni unutmang!",
        'lesson_started_attended': "✅ Dars boshlandi va siz muvaffaqiyatli davomatni amalga oshirdingiz!\n\nE'tiboringizni darsga qaratishingiz mumkin.\nDarsga kelgan o'quvchilarni davomat qilishni yodingizdan chiqarmang.\n\nHayrli kun!",
        'lesson_started_not_attended': "⚠️ Sizning darsingiz boshlandi, lekin hali davomat qilmadingiz!\n\n📌 {branch} filialida soat {time} da darsingiz boshlangan.\n📍 Iltimos, darhol davomat qiling yoki sababini admin xabardor qiling.\n\nDavomat qilish uchun 📍 Kelganimni tasdiqlash tugmasini bosing.",
        'select_teacher': "👤 O'qituvchini tanlang:",
        'select_lesson_type': "📚 Dars turini tanlang:",
        'active_schedules': "📋 Faol dars jadvallari",
        'no_active_schedules': "📭 Hali dars jadvallari mavjud emas.",
        'schedule_info': "{teacher} [{specialty}]\n🏢 {branch}\n📚 {lesson_type}\n{days_times}",
        'enter_date': "📅 Hisobot olish uchun sanani kiriting (format: YYYY-MM-DD)\nMasalan: 2026-03-01",
        'invalid_date': "❌ Noto'g'ri sana formati. Qaytadan urinib ko'ring:",
        'select_broadcast_specialty': "📢 Qaysi fan o'qituvchilariga xabar yubormoqchisiz?",
        'all_teachers': "👥 Hammasi",
        'edit_schedule': "✏️ Dars jadvalini tahrirlash",
        'select_new_branch': "🏢 Yangi filialni tanlang:",
        'select_new_lesson_type': "📚 Yangi dars turini tanlang:",
        'select_new_weekdays': "📅 Yangi kunlarni tanlang:",
        'enter_new_time': "⏰ {weekday} kuni uchun yangi vaqtni kiriting:\n\nFormat: HH:MM (masalan: 09:00)",
        'ontime': "Vaqtida",
        'late': "Kechikkan",
        'buttons': {
            'attendance': "📍 Kelganimni tasdiqlash",
            'my_stats': "📊 Mening statistikam",
            'branches': "🏢 Filiallar",
            'top_week': "🏆 Hafta topi",
            'view_schedules': "📋 Dars jadvalim (PDF)",
            'help': "❓ Yordam",
            'language': "🌐 Til"
        }
    },
    'ru': {
        'welcome': "🌟 Добро пожаловать в бот для отметок HANCOM ACADEMY для учителей, {name}!",
        'ask_name': "👤 Пожалуйста, введите ваше имя и фамилию:\n\nНапример: Ali Karimov",
        'ask_specialty': "📚 Какой предмет вы преподаете?",
        'specialty_it': "💻 IT",
        'specialty_korean': "🇰🇷 Корейский язык",
        'stats': "📊 Ваша статистика:",
        'no_stats': "📭 Вы еще не отмечались",
        'branches': "🏢 Доступные филиалы (локация):",
        'help': "🤖 Руководство по использованию:\n\n📍 Для отметки:\n• Нажмите кнопку \"📍 Подтвердить прибытие\"\n• Отправьте свою геолокацию\n\n📊 Статистика:\n• \"📊 Моя статистика\" - история отметок\n• \"🏢 Филиалы\" - список всех филиалов\n\n⚠️ Примечания:\n• В каждом филиале можно отмечаться только 1 раз в день\n• Отметки записываются по ташкентскому времени",
        'attendance_success': "✅ Отметка подтверждена!\n\n🏫 Филиал: {branch}\n📅 Дата: {date}\n⏰ Время: {time}\n📊 Посещений в этом месяце: {count}\n📍 Расстояние: {distance:.1f} м",
        'already_attended': "⚠️ Вы уже отмечались сегодня в филиале {branch}!",
        'not_in_area': "❌ Вы не находитесь в зоне учебных заведений!",
        'daily_reminder': "⏰ Напоминание! Вы еще не отметились сегодня. Подтвердите свое прибытие для начала рабочего дня!",
        'weekly_top': "🏆 Самые активные учителя недели:\n\n{top_list}",
        'monthly_report': "📊 Отчет за {month}\n\n{report}",
        'language_changed': "✅ Язык изменен: Русский язык",
        'language_prompt': "Пожалуйста, выберите язык:",
        'view_schedules': "📋 Мое расписание (PDF)",
        'my_schedule': "📅 Ваше расписание уроков готово в формате PDF!",
        'no_schedules': "📭 Вам еще не назначено расписание.",
        'schedule_updated': "📢 Ваше расписание обновлено!",
        'schedule_deleted_notify': "📢 Ваше расписание удалено.",
        'reminder': "⏰ Напоминание!\n\nСегодня в {time} у вас урок в филиале {branch}.\nНе забудьте отметиться!",
        'lesson_started_attended': "✅ Урок начался и вы успешно отметились!\n\nМожете сосредоточиться на уроке.\nНе забудьте отметить присутствующих учеников.\n\nХорошего дня!",
        'lesson_started_not_attended': "⚠️ Ваш урок начался, но вы еще не отметились!\n\n📌 В филиале {branch} в {time} начался ваш урок.\n📍 Пожалуйста, немедленно отметьтесь или сообщите причину администратору.\n\nДля отметки нажмите кнопку 📍 Подтвердить прибытие.",
        'select_teacher': "👤 Выберите учителя:",
        'select_lesson_type': "📚 Выберите тип урока:",
        'active_schedules': "📋 Активные расписания",
        'no_active_schedules': "📭 Нет активных расписаний.",
        'schedule_info': "{teacher} [{specialty}]\n🏢 {branch}\n📚 {lesson_type}\n{days_times}",
        'enter_date': "📅 Введите дату для отчета (формат: YYYY-MM-DD)\nНапример: 2026-03-01",
        'invalid_date': "❌ Неверный формат даты. Попробуйте снова:",
        'select_broadcast_specialty': "📢 Каким учителям отправить сообщение?",
        'all_teachers': "👥 Всем",
        'edit_schedule': "✏️ Редактирование расписания",
        'select_new_branch': "🏢 Выберите новый филиал:",
        'select_new_lesson_type': "📚 Выберите новый тип урока:",
        'select_new_weekdays': "📅 Выберите новые дни:",
        'enter_new_time': "⏰ Введите новое время для {weekday}:\n\nФормат: HH:MM (например: 09:00)",
        'ontime': "Вовремя",
        'late': "Опоздал",
        'buttons': {
            'attendance': "📍 Подтвердить прибытие",
            'my_stats': "📊 Моя статистика",
            'branches': "🏢 Филиалы",
            'top_week': "🏆 Топ недели",
            'view_schedules': "📋 Мое расписание (PDF)",
            'help': "❓ Помощь",
            'language': "🌐 Язык"
        }
    },
    'kr': {
        'welcome': "🌟 HANCOM ACADEMY 교사용 출석 체크 봇에 오신 것을 환영합니다, {name}!",
        'ask_name': "👤 이름과 성을 입력하세요:\n\n예: Ali Karimov",
        'ask_specialty': "📚 어떤 과목을 가르치시나요?",
        'specialty_it': "💻 IT",
        'specialty_korean': "🇰🇷 한국어",
        'stats': "📊 내 통계:",
        'no_stats': "📭 아직 출석 체크하지 않았습니다",
        'branches': "🏢 등록된 지점 (위치):",
        'help': "🤖 사용 설명서:\n\n📍 출석 체크 방법:\n• 하단의 \"📍 출석 확인\" 버튼을 누르세요\n• 위치를 전송하세요\n\n📊 통계:\n• \"📊 내 통계\" - 개인 출석 기록\n• \"🏢 지점\" - 모든 지점 목록\n\n⚠️ 참고사항:\n• 각 지점에서 하루에 한 번만 출석 체크 가능\n• 출석은 타슈켄트 시간 기준으로 기록됨",
        'attendance_success': "✅ 출석이 확인되었습니다!\n\n🏫 지점: {branch}\n📅 날짜: {date}\n⏰ 시간: {time}\n📊 이번 달 출석: {count}회\n📍 거리: {distance:.1f}미터",
        'already_attended': "⚠️ 오늘 이미 {branch} 지점에서 출석 체크하셨습니다!",
        'not_in_area': "❌ 지정된 교육 기관 구역 내에 있지 않습니다!",
        'daily_reminder': "⏰ 알림! 오늘 아직 출석 체크하지 않으셨습니다. 업무 시작을 위해 출석을 확인하세요!",
        'weekly_top': "🏆 이번 주 가장 활발한 교사:\n\n{top_list}",
        'monthly_report': "📊 {month}월 보고서\n\n{report}",
        'language_changed': "✅ 언어가 변경되었습니다: 한국어",
        'language_prompt': "언어를 선택하세요:",
        'view_schedules': "📋 내 시간표 (PDF)",
        'my_schedule': "📅 내 수업 시간표가 PDF 형식으로 준비되었습니다!",
        'no_schedules': "📭 아직 시간표가 배정되지 않았습니다.",
        'schedule_updated': "📢 시간표가 업데이트되었습니다!",
        'schedule_deleted_notify': "📢 시간표가 삭제되었습니다.",
        'reminder': "⏰ 알림!\n\n오늘 {time}에 {branch} 지점에서 수업이 있습니다.\n출석 체크를 잊지 마세요!",
        'lesson_started_attended': "✅ 수업이 시작되었고 출석이 확인되었습니다!\n\n수업에 집중하세요.\n학생들 출석 체크하는 것을 잊지 마세요.\n\n좋은 하루 되세요!",
        'lesson_started_not_attended': "⚠️ 수업이 시작되었지만 아직 출석 체크하지 않으셨습니다!\n\n📌 {branch} 지점에서 {time}에 수업이 시작되었습니다.\n📍 즉시 출석 체크하거나 관리자에게 사유를 알려주세요.\n\n출석 체크를 위해 📍 출석 확인 버튼을 누르세요.",
        'select_teacher': "👤 교사를 선택하세요:",
        'select_lesson_type': "📚 수업 유형을 선택하세요:",
        'active_schedules': "📋 활성 시간표",
        'no_active_schedules': "📭 활성 시간표가 없습니다.",
        'schedule_info': "{teacher} [{specialty}]\n🏢 {branch}\n📚 {lesson_type}\n{days_times}",
        'enter_date': "📅 보고서 날짜를 입력하세요 (형식: YYYY-MM-DD)\n예: 2026-03-01",
        'invalid_date': "❌ 잘못된 날짜 형식입니다. 다시 시도하세요:",
        'select_broadcast_specialty': "📢 어떤 선생님들에게 메시지를 보낼까요?",
        'all_teachers': "👥 모두",
        'edit_schedule': "✏️ 시간표 편집",
        'select_new_branch': "🏢 새 지점을 선택하세요:",
        'select_new_lesson_type': "📚 새 수업 유형을 선택하세요:",
        'select_new_weekdays': "📅 새 요일을 선택하세요:",
        'enter_new_time': "⏰ {weekday} 요일의 새 시간을 입력하세요:\n\n형식: HH:MM (예: 09:00)",
        'ontime': "정시",
        'late': "지각",
        'buttons': {
            'attendance': "📍 출석 확인",
            'my_stats': "📊 내 통계",
            'branches': "🏢 지점",
            'top_week': "🏆 주간 TOP",
            'view_schedules': "📋 내 시간표 (PDF)",
            'help': "❓ 도움말",
            'language': "🌐 언어"
        }
    }
}

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

def sort_weekdays(days_dict):
    """Hafta kunlarini tartiblash"""
    return dict(sorted(days_dict.items(), key=lambda x: WEEKDAY_ORDER.get(x[0], 0)))

def calculate_lateness(attendance_time: str, lesson_time: str) -> tuple:
    """Kechikishni hisoblash"""
    try:
        att_dt = datetime.strptime(attendance_time, "%H:%M")
        les_dt = datetime.strptime(lesson_time, "%H:%M")
        
        if att_dt <= les_dt:
            return True, 0  # Vaqtida
        else:
            diff = att_dt - les_dt
            minutes_late = int(diff.total_seconds() / 60)
            return False, minutes_late  # Kechikkan
    except:
        return True, 0

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

async def create_schedule_pdf(user_id: int) -> io.BytesIO:
    """Foydalanuvchi uchun dars jadvali PDF yaratish"""
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Sarlavha
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,
        spaceAfter=20
    )
    
    name = user_names.get(user_id, "Foydalanuvchi")
    specialty = user_specialty.get(user_id, '')
    specialty_display = f" [{specialty}]" if specialty else ""
    
    elements.append(Paragraph(f"{name}{specialty_display} - Dars Jadvali", title_style))
    elements.append(Spacer(1, 10))
    
    if user_id not in user_schedules or not user_schedules[user_id]:
        elements.append(Paragraph("Sizga hali dars jadvali biriktirilmagan.", styles['Normal']))
    else:
        for schedule_id in user_schedules[user_id]:
            schedule = schedules.get(schedule_id)
            if schedule and schedule['user_id'] == user_id:
                branch = schedule['branch']
                lesson_type = schedule.get('lesson_type', 'Dars')
                
                # Filial sarlavhasi
                branch_style = ParagraphStyle(
                    'BranchStyle',
                    parent=styles['Heading2'],
                    fontSize=14,
                    textColor=colors.blue,
                    spaceAfter=10
                )
                elements.append(Paragraph(f"🏢 {branch} - {lesson_type}", branch_style))
                
                # Jadval ma'lumotlari
                days = sort_weekdays(schedule['days'])
                data = [['Kun', 'Vaqt']]
                for day, time in days.items():
                    data.append([day, time])
                
                table = Table(data, colWidths=[2.5*inch, 2.5*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 0), (-1, -1), 12)
                ]))
                elements.append(table)
                elements.append(Spacer(1, 15))
    
    # Sana
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=2,
        spaceBefore=20
    )
    elements.append(Paragraph(f"Yaratilgan sana: {datetime.now(UZB_TZ).strftime('%d.%m.%Y %H:%M')}", date_style))
    
    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer

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
    
    # PostgreSQL dan foydalanuvchini tekshirish
    if db:
        try:
            user = await db.get_user(user_id)
            if user and user['status'] == 'blocked':
                await message.answer(get_text(user_id, 'blocked_user'))
                return
            if user:
                # RAMni yangilash
                user_names[user_id] = user['full_name']
                user_specialty[user_id] = user['specialty']
                user_status[user_id] = user['status']
                user_languages[user_id] = user['language']
                user_ids.add(user_id)
        except Exception as e:
            logging.error(f"PostgreSQL dan foydalanuvchi olishda xatolik: {e}")
    
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
    
    # PostgreSQL ga saqlash
    if db:
        try:
            await db.add_user(user_id, user_names[user_id], specialty, lang)
        except Exception as e:
            logging.error(f"PostgreSQL ga saqlashda xatolik: {e}")
    
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
    try:
        user_id = callback.from_user.id
        lang = callback.data.split("_")[2]
        user_languages[user_id] = lang
        
        if db:
            try:
                await db.update_user_language(user_id, lang)
            except Exception as e:
                logging.error(f"PostgreSQL da tilni yangilashda xatolik: {e}")
        
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

# --- FOYDALANUVCHI UCHUN DARS JADVALINI PDF KO'RISH ---
@dp.message(F.text.in_({'📋 Dars jadvalim (PDF)', '📋 Мое расписание (PDF)', '📋 내 시간표 (PDF)'}))
async def view_my_schedule_pdf(message: types.Message):
    """Foydalanuvchi o'zining dars jadvalini PDF formatida ko'rish"""
    user_id = message.from_user.id
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
    if user_id not in user_schedules or not user_schedules[user_id]:
        await message.answer(get_text(user_id, 'no_schedules'))
        return
    
    try:
        # PDF yaratish
        pdf_buffer = await create_schedule_pdf(user_id)
        
        await message.answer_document(
            types.BufferedInputFile(pdf_buffer.getvalue(), 
                                    filename=f"dars_jadvali_{user_names.get(user_id, 'user')}.pdf"),
            caption=get_text(user_id, 'my_schedule')
        )
    except Exception as e:
        logging.error(f"view_my_schedule_pdf error: {e}")
        await message.answer("❌ PDF yaratishda xatolik yuz berdi")

# --- BOSHQA FOYDALANUVCHI HANDLERLARI ---
@dp.message(F.text.in_({'📊 Mening statistikam', '📊 Моя статистика', '📊 내 통계'}))
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
        text += f"📍 {branch}\n"
        
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
            
            text += f"   📅 {month_display}\n"
            
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

@dp.message(F.text.in_({'🏢 Filiallar', '🏢 Филиалы', '🏢 지점'}))
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
            InlineKeyboardButton(text=f"📍 {loc['name']}", url=maps_link)
        )
    
    await message.answer(
        "🏢 Mavjud filiallar (lokatsiya uchun bosing):",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text.in_({'❓ Yordam', '❓ Помощь', '❓ 도움말'}))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_status.get(user_id) == 'blocked':
        await message.answer(get_text(user_id, 'blocked_user'))
        return
    
    await message.answer(
        get_text(user_id, 'help'),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_({'🏆 Hafta topi', '🏆 Топ недели', '🏆 주간 TOP'}))
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
            no_data_msg = "📭 Bu hafta hali davomat yo'q"
        elif lang == 'ru':
            no_data_msg = "📭 На этой неделе еще нет отметок"
        else:
            no_data_msg = "📭 이번 주에는 아직 출석 기록이 없습니다"
        
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
        # PostgreSQL dan tekshirish
        already_attended = False
        if db:
            try:
                already_attended = await db.check_attendance(user_id, found_branch, today_date)
            except Exception as e:
                logging.error(f"PostgreSQL dan davomat tekshirishda xatolik: {e}")
        
        # Agar PostgreSQL ishlamasa, RAMdan tekshirish
        if not already_attended:
            already_attended = any(k[0] == user_id and k[1] == found_branch and k[2] == today_date for k in daily_attendance_log)
        
        if already_attended:
            await message.answer(
                get_text(user_id, 'already_attended', branch=found_branch),
                parse_mode="Markdown"
            )
            return

        counter_key = (user_id, found_branch, current_month)
        attendance_counter[counter_key] = attendance_counter.get(counter_key, 0) + 1
        visit_number = attendance_counter[counter_key]
        
        # RAMga saqlash
        daily_attendance_log.add((user_id, found_branch, today_date, now_time))
        
        # PostgreSQL ga saqlash
        if db:
            try:
                await db.add_attendance(user_id, found_branch, today_date, now_time)
            except Exception as e:
                logging.error(f"PostgreSQL ga davomat saqlashda xatolik: {e}")
        
        full_name = user_names.get(user_id, message.from_user.full_name)
        specialty = user_specialty.get(user_id, '')
        specialty_display = f" [{specialty}]" if specialty else ""
        
        # Admin guruhiga hisobot
        report = (
            f"✅ Yangi Davomat\n\n"
            f"👤 O'qituvchi: {full_name}{specialty_display}\n"
            f"📍 Manzil: {found_branch}\n"
            f"📅 Sana: {today_date}\n"
            f"⏰ Vaqt: {now_time}\n"
            f"📊 Shu oydagi tashrif: {visit_number}-marta\n"
            f"📍 Masofa: {min_distance:.1f} metr"
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
            
            # Ob-havo ma'lumotini olish
            weather_data = await get_weather_by_coords(user_coords[0], user_coords[1])
            if weather_data:
                weather_message = format_weather_message(weather_data, user_languages.get(user_id, 'uz'))
                full_response = f"{success_text}\n\n{weather_message}"
            else:
                full_response = success_text
            
            await message.answer(full_response, parse_mode="Markdown")
            
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        await message.answer(
            get_text(user_id, 'not_in_area'),
            parse_mode="Markdown"
        )

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

📍 Joy: {city}
🌡️ {temp_text}: {temp:.1f}°C ({feels_text}: {feels_like:.1f}°C)
💧 {humidity_text}: {humidity}%
💨 {wind_text}: {wind_speed:.1f} m/s
📊 {pressure_text}: {pressure_mmhg:.1f} mmHg

💡 {recommendation_title}:
{recommendation}

⏰ {time_text}: {datetime.now(UZB_TZ).strftime('%H:%M')}
"""
    return message

# --- ADMIN PANEL - TO'LIQ FUNKSIYALAR BILAN ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Admin panel asosiy menyusi"""
    chat_id = message.chat.id
    
    # Debug uchun
    logging.info(f"Admin komandasi keldi. Chat ID: {chat_id}, Admin ID: {ADMIN_GROUP_ID}")
    
    if not check_admin(chat_id):
        await message.answer(f"⛔ Ruxsat yo'q!\nSizning ID: {chat_id}\nAdmin ID: {ADMIN_GROUP_ID}")
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
        builder.row(
            InlineKeyboardButton(text="📥 Backup", callback_data="admin_backup"),
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")
        )
        
        await message.answer(
            "👨‍💼 Admin Panel\n\nKerakli bo'limni tanlang:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"admin_panel error: {e}")
        await message.answer(f"❌ Admin panelni ochishda xatolik: {e}")

# --- STATISTIKA BO'LIMI ---
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
            InlineKeyboardButton(text="📈 Grafiklar", callback_data="admin_stats_charts")
        )
        builder.row(
            InlineKeyboardButton(text="🏆 Filiallar reytingi", callback_data="admin_stats_branches"),
            InlineKeyboardButton(text="👥 O'qituvchilar reytingi", callback_data="admin_stats_teachers")
        )
        builder.row(
            InlineKeyboardButton(text="📅 Oylik hisobot", callback_data="admin_monthly"),
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

@dp.callback_query(F.data == "admin_stats_charts")
async def admin_stats_charts(callback: types.CallbackQuery):
    """Grafikli statistika"""
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        # So'nggi 7 kunlik davomatlar
        now_uzb = datetime.now(UZB_TZ)
        dates = []
        counts = []
        
        for i in range(6, -1, -1):
            date = (now_uzb - timedelta(days=i)).strftime("%Y-%m-%d")
            dates.append((now_uzb - timedelta(days=i)).strftime("%d.%m"))
            count = len([k for k in daily_attendance_log if k[2] == date])
            counts.append(count)
        
        # Grafik yaratish
        plt.figure(figsize=(10, 6))
        plt.bar(dates, counts, color='skyblue')
        plt.title(f"So'nggi 7 kunlik davomatlar", fontsize=16)
        plt.xlabel("Sanalar", fontsize=12)
        plt.ylabel("Davomatlar soni", fontsize=12)
        plt.grid(axis='y', alpha=0.3)
        
        for i, v in enumerate(counts):
            plt.text(i, v + 0.1, str(v), ha='center', va='bottom')
        
        # Grafikni saqlash
        img_bytes = io.BytesIO()
        plt.savefig(img_bytes, format='png', dpi=100, bbox_inches='tight')
        img_bytes.seek(0)
        plt.close()
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_stats_main"))
        
        await callback.message.answer_photo(
            photo=types.BufferedInputFile(img_bytes.getvalue(), filename="chart.png"),
            caption="📊 So'nggi 7 kunlik davomatlar statistikasi",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_stats_charts error: {e}")
        await callback.message.answer("❌ Grafik yaratishda xatolik yuz berdi")
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
            report += f"📍 {branch}\n"
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

# --- FOYDALANUVCHILARNI BOSHQARISH ---
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
            InlineKeyboardButton(text="🔍 Qidirish", callback_data="admin_users_search"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_users_stats")
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
        
        text = "✅ Faol foydalanuvchilar:\n\n"
        for uid in sorted(active)[:20]:
            name = user_names.get(uid, f"ID: {uid}")
            specialty = user_specialty.get(uid, '')
            spec_display = f" [{specialty}]" if specialty else ""
            text += f"• {name}{spec_display}\n"
        
        if len(active) > 20:
            text += f"\n... va yana {len(active) - 20} ta"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_users_main"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_users_active error: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi")
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
        
        text = "⛔ Bloklangan foydalanuvchilar:\n\n"
        for uid in blocked[:20]:
            name = user_names.get(uid, f"ID: {uid}")
            specialty = user_specialty.get(uid, '')
            spec_display = f" [{specialty}]" if specialty else ""
            text += f"• {name}{spec_display}\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_users_main"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logging.error(f"admin_users_blocked error: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi")
        await callback.answer()

# --- ORTGA QAYTISH ---
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
        builder.row(
            InlineKeyboardButton(text="📥 Backup", callback_data="admin_backup"),
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")
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
        today_date = now_uzb.strftime("%Y-%m-%d")
        
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
                
                # Dars boshlanishidan 15 daqiqa oldin eslatma
                reminder_dt = lesson_dt - timedelta(minutes=15)
                reminder_time = reminder_dt.strftime("%H:%M")
                
                # Dars boshlangan vaqt
                lesson_start_time = lesson_dt.strftime("%H:%M")
                
                # Dars boshlanganidan 5 daqiqa o'tgach eslatma
                lesson_passed_dt = lesson_dt + timedelta(minutes=5)
                lesson_passed_time = lesson_passed_dt.strftime("%H:%M")
                
                lang = user_languages.get(user_id, 'uz')
                
                # 1. Dars boshlanishidan 15 daqiqa oldin eslatma
                if current_time == reminder_time:
                    try:
                        await bot.send_message(
                            user_id,
                            get_text(user_id, 'reminder', time=lesson_time, branch=branch),
                            parse_mode="Markdown"
                        )
                        logging.info(f"Reminder sent to {user_id} for {branch} at {lesson_time}")
                    except Exception as e:
                        logging.error(f"Failed to send reminder to {user_id}: {e}")
                
                # 2. Dars boshlanganida (davomat qilgan bo'lsa) xabar
                elif current_time == lesson_start_time:
                    # Bugun shu filialda davomat qilganmi?
                    attended_today = any(k[0] == user_id and k[1] == branch and k[2] == today_date for k in daily_attendance_log)
                    
                    if attended_today:
                        try:
                            await bot.send_message(
                                user_id,
                                get_text(user_id, 'lesson_started_attended'),
                                parse_mode="Markdown"
                            )
                            logging.info(f"Lesson started message sent to {user_id} for {branch}")
                        except Exception as e:
                            logging.error(f"Failed to send lesson started message to {user_id}: {e}")
                
                # 3. Dars boshlanganidan 5 daqiqa o'tgach (hali davomat qilmagan bo'lsa)
                elif current_time == lesson_passed_time:
                    # Bugun shu filialda davomat qilmagan bo'lsa
                    attended_today = any(k[0] == user_id and k[1] == branch and k[2] == today_date for k in daily_attendance_log)
                    
                    if not attended_today:
                        try:
                            await bot.send_message(
                                user_id,
                                get_text(user_id, 'lesson_started_not_attended', time=lesson_time, branch=branch),
                                parse_mode="Markdown"
                            )
                            logging.info(f"Late reminder sent to {user_id} for {branch}")
                        except Exception as e:
                            logging.error(f"Failed to send late reminder to {user_id}: {e}")
        
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
    
    # PostgreSQL ulanishini sozlash
    if db:
        try:
            await db.create_pool()
            await db.init_tables()
            print("✅ PostgreSQL muvaffaqiyatli ulandi")
            
            # RAMdagi ma'lumotlarni DB ga ko'chirish (faqat birinchi marta)
            if user_ids:
                print("🔄 RAMdagi ma'lumotlar PostgreSQLga ko'chirilmoqda...")
                await db.migrate_from_ram(
                    user_names=user_names,
                    user_specialty=user_specialty,
                    user_status=user_status,
                    user_languages=user_languages,
                    daily_attendance_log=daily_attendance_log,
                    schedules=schedules,
                    user_schedules=user_schedules
                )
                print("✅ Ma'lumotlar muvaffaqiyatli ko'chirildi")
        except Exception as e:
            print(f"❌ PostgreSQL ulanishida xatolik: {e}")
            print("⚠️ Bot RAM bilan ishlashda davom etadi...")
    else:
        print("⚠️ DATABASE_URL sozlanmagan. Bot RAM bilan ishlaydi.")
    
    asyncio.create_task(reminder_loop())
    asyncio.create_task(check_schedule_reminders())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
