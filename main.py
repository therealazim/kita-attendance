@dp.callback_query(F.data.startswith("admin_user_delete_"))
async def admin_user_delete(callback: types.CallbackQuery):
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    # Faqat "admin_user_delete_" bilan boshlangan va "confirm" bo'lmaganlarni qabul qilish
    if not callback.data.startswith("admin_user_delete_") or "_confirm_" in callback.data:
        return
    
    try:
        # "admin_user_delete_1965049633" dan "1965049633" ni ajratib olish
        uid_str = callback.data.replace("admin_user_delete_", "")
        uid = int(uid_str)
    except ValueError as e:
        logging.error(f"admin_user_delete parse error: {callback.data}, error: {e}")
        await callback.answer("Noto'g'ri format!")
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"admin_user_delete_confirm_{uid}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_user_info_{uid}")
    )
    
    ism_text = user_names.get(uid, "Noma'lum")
    await callback.message.edit_text(
        "⚠️ **Foydalanuvchini o'chirish**\n\n"
        f"ID: `{uid}`\n"
        f"Ism: {ism_text}\n\n"
        "Bu foydalanuvchini butunlay o'chirmoqchimisiz?\n"
        "Barcha ma'lumotlari (davomatlar, dars jadvallari) ham o'chib ketadi!",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_user_delete_confirm_"))
async def admin_user_delete_confirm(callback: types.CallbackQuery):
    if not check_admin(callback.message.chat.id):
        await callback.answer("Ruxsat yo'q!")
        return
    
    try:
        # "admin_user_delete_confirm_1965049633" dan "1965049633" ni ajratib olish
        uid_str = callback.data.replace("admin_user_delete_confirm_", "")
        uid = int(uid_str)
        logging.info(f"admin_user_delete_confirm called for uid: {uid}")
    except ValueError as e:
        logging.error(f"admin_user_delete_confirm parse error: {callback.data}, error: {e}")
        await callback.answer("Noto'g'ri format!")
        return
    
    try:
        # PostgreSQL dan o'chirish
        async with db.pool.acquire() as conn:
            await conn.execute("DELETE FROM attendance WHERE user_id = $1", uid)
            await conn.execute("DELETE FROM schedules WHERE user_id = $1", uid)
            await conn.execute("DELETE FROM users WHERE user_id = $1", uid)
        
        # RAM dan o'chirish
        if uid in user_ids:
            user_ids.remove(uid)
        
        ism_text = user_names.get(uid, "Noma'lum")
        
        user_names.pop(uid, None)
        user_specialty.pop(uid, None)
        user_status.pop(uid, None)
        user_languages.pop(uid, None)
        
        # daily_attendance_log dan o'chirish
        to_remove = [k for k in daily_attendance_log if k[0] == uid]
        for k in to_remove:
            daily_attendance_log.remove(k)
        
        # schedules dan o'chirish
        if uid in user_schedules:
            for schedule_id in user_schedules[uid]:
                schedules.pop(schedule_id, None)
            user_schedules.pop(uid, None)
        
        await callback.message.edit_text(
            f"✅ **Foydalanuvchi o'chirildi!**\n\n"
            f"ID: `{uid}`\n"
            f"Ism: {ism_text}\n\n"
            f"Barcha ma'lumotlari bazadan tozalandi.",
            parse_mode="Markdown"
        )
        
        await callback.answer("✅ Foydalanuvchi muvaffaqiyatli o'chirildi!")
        
        await asyncio.sleep(2)
        
        # Foydalanuvchilar ro'yxatini qayta ko'rsatish
        active = [uid for uid in user_ids if user_status.get(uid) != 'blocked']
        if active:
            builder = InlineKeyboardBuilder()
            for uid in sorted(active)[:20]:
                name = user_names.get(uid, f"ID: {uid}")
                specialty = user_specialty.get(uid, '')
                specialty_display = f" [{specialty}]" if specialty else ""
                builder.row(
                    InlineKeyboardButton(text=f"✅ {name}{specialty_display}", callback_data=f"admin_user_info_{uid}")
                )
            builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_users_main"))
            
            await callback.message.answer(
                "✅ Faol foydalanuvchilar ro'yxati:",
                reply_markup=builder.as_markup()
            )
        else:
            await callback.message.answer("📭 Faol foydalanuvchilar yo'q.")
        
    except Exception as e:
        logging.error(f"admin_user_delete_confirm error: {e}")
        await callback.message.edit_text(
            f"❌ Xatolik yuz berdi: {str(e)}"
        )
        await callback.answer("Xatolik yuz berdi!")