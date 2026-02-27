import asyncio
import os
import logging
import pytz 
import csv
import io
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
ALLOWED_DISTANCE = 500  # 500 metrga o'zgartirildi

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
        text = text.format(**kwargs)
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
        KeyboardButton(text=get_button_text(user_id, 'help')),
        KeyboardButton(text=get_button_text(user_id, 'language'))
    )
    builder.adjust(1, 2, 2, 1)  # Tugmalarni joylashtirish
    return builder.as_markup(resize_keyboard=True)

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

@dp.message(F.text.in_({'📊 Mening statistikam', '📊 Моя статистика'}))
async def my_stats(message: types.Message):
    user_id = message.from_user.id
    now_uzb = datetime.now(UZB_TZ)
    current_month = now_uzb.strftime("%Y-%m")
    
    # Foydalanuvchining barcha davomatlarini topish
    user_attendances = defaultdict(lambda: defaultdict(int))
    for (uid, branch, date) in daily_attendance_log:
        if uid == user_id:
            month = date[:7]  # YYYY-MM
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
    user_names = {}
    
    for (uid, branch, date) in daily_attendance_log:
        if date >= week_ago_str:
            weekly_stats[uid] += 1
            if uid not in user_names:
                try:
                    user = await bot.get_chat(uid)
                    user_names[uid] = user.full_name
                except:
                    user_names[uid] = f"Foydalanuvchi {uid}"
    
    if not weekly_stats:
        await message.answer("📭 Bu hafta hali davomat yo'q")
        return
    
    # Top 10 foydalanuvchini saralash
    top_users = sorted(weekly_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    top_list = ""
    for i, (uid, count) in enumerate(top_users, 1):
        name = user_names.get(uid, f"Foydalanuvchi {uid}")
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
            
            await message.answer(
                get_text(
                    user_id, 
                    'attendance_success',
                    branch=found_branch,
                    date=today_date,
                    time=now_time,
                    count=visit_number,
                    distance=min_distance
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        await message.answer(get_text(user_id, 'not_in_area'), parse_mode="Markdown")

# --- ADMIN PANEL (faqat adminlar uchun) ---
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
            report += f"   Jami: {total} ta davomat\n"
            report += f"   O'qituvchilar: {unique_users} ta\n\n"
        
        await callback.message.answer(report, parse_mode="Markdown")
    
    elif action == "excel":
        # Excel fayl yaratish
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Davomat"
        
        # Sarlavhalar
        headers = ["Sana", "Filial", "O'qituvchi ID", "O'qituvchi Ismi", "Vaqt", "Masofa"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        
        # Ma'lumotlarni yozish
        row = 2
        for (uid, branch, date) in sorted(daily_attendance_log):
            try:
                user = await bot.get_chat(uid)
                user_name = user.full_name
            except:
                user_name = f"User_{uid}"
            
            ws.cell(row=row, column=1, value=date)
            ws.cell(row=row, column=2, value=branch)
            ws.cell(row=row, column=3, value=uid)
            ws.cell(row=row, column=4, value=user_name)
            ws.cell(row=row, column=5, value="09:00")  # Vaqt ma'lumoti saqlanmagan
            ws.cell(row=row, column=6, value="<500m")
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
    
    elif action == "users":
        user_count = len(user_ids)
        active_today = len([k for k in daily_attendance_log if k[2] == now_uzb.strftime("%Y-%m-%d")])
        
        await callback.message.answer(
            f"👥 **Foydalanuvchilar statistikasi**\n\n"
            f"Jami foydalanuvchilar: {user_count}\n"
            f"Bugun faol: {active_today}\n"
            f"Bugun davomat qilganlar: {active_today}",
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

# --- Eslatmalar (cron-job orqali) ---
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
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                logging.error(f"Reminder error for {user_id}: {e}")
    
    logging.info(f"Daily reminders sent: {sent_count} users")

async def reminder_loop():
    """Eslatmalar uchun doimiy loop"""
    while True:
        now_uzb = datetime.now(UZB_TZ)
        # Har kuni soat 08:00 da eslatma
        if now_uzb.hour == 8 and now_uzb.minute == 0:
            await send_daily_reminders()
            await asyncio.sleep(60)  # 1 daqiqa kutib, qayta yubormaslik
        await asyncio.sleep(30)  # Har 30 sekundda tekshirish

async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(reminder_loop())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
