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
    # Foydalanuvchi holatini saqlash - ob-havo kutyapti
    user_states[user_id] = "waiting_weather"
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
    user_states[user_id] = "waiting_weather"
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

# ASOSIY LOKATSIYA HANDLERI (davomat uchun)
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

    # Ob-havo ma'lumotini olish
    weather_data = await get_weather_by_coords(user_coords[0], user_coords[1])
    weather_message = format_weather_message(weather_data, user_languages.get(user_id, 'uz'))

    # DAVOMAT QISMI
    if found_branch:
        attendance_key = (user_id, found_branch, today_date)
        if attendance_key in daily_attendance_log:
            # Bugun allaqachon davomat qilgan
            response = f"{get_text(user_id, 'already_attended', branch=found_branch)}\n\n{weather_message}"
            await message.answer(response, parse_mode="Markdown")
            return

        # Yangi davomat
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
            # Adminga yuborish
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID, 
                text=report, 
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            
            # Foydalanuvchiga davomat + ob-havo
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
        # Filial topilmadi - faqat ob-havo
        await message.answer(
            f"{get_text(user_id, 'not_in_area')}\n\n{weather_message}",
            parse_mode="Markdown"
        )
    
    # Asosiy menyuga qaytish
    keyboard = await main_keyboard(user_id)
    await message.answer("Asosiy menyu:", reply_markup=keyboard)

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
            headers = ["Sana", "Filial", "O'qituvchi ID", "O'qituvchi Ismi"]
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
