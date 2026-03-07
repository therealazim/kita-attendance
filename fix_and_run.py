import os
import re

def update_bot_logic():
    file_path = 'main.py'
    if not os.path.exists(file_path):
        print("❌ main.py topilmadi!")
        return

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    print("🛠 Logikani yangilash boshlandi...")

    # 1. Admin paneldagi '+ Dars jadvali qo'shish' tugmasini olib tashlaymiz
    # Odatda InlineKeyboardButton(text="➕ ...") ko'rinishida bo'ladi
    content = re.sub(r'InlineKeyboardButton\(text="➕ Dars jadvali qo\'shish",.*?\),?', '', content)
    
    # 2. load_to_ram funksiyasini yangilaymiz
    # Guruhlar yuklanayotganda ularni ham dars jadvali sifatida RAMga yozadigan qilamiz
    group_logic_patch = """
                students = await conn.fetch("SELECT * FROM group_students WHERE group_id = $1", g['id'])
                group_students[g['id']] = [{'name': s['student_name'], 'phone': s['student_phone']} for s in students]
                
                # --- YANGI: Guruhni dars jadvaliga qo'shish ---
                teacher_id = g['teacher_id']
                if teacher_id:
                    days_list = json.loads(g['days_data'])
                    time_val = g['time_text']
                    sched_id = f"group_as_sched_{g['id']}"
                    
                    # Jadval formatiga moslash (dict ko'rinishida)
                    days_dict = {day: time_val for day in days_list}
                    
                    schedules[sched_id] = {
                        'user_id': teacher_id,
                        'branch': g['branch'],
                        'lesson_type': g['lesson_type'],
                        'days': days_dict
                    }
                    if sched_id not in user_schedules[teacher_id]:
                        user_schedules[teacher_id].append(sched_id)
                # --------------------------------------------
    """
    
    # Guruhlar yuklanadigan qismni topib almashtiramiz
    old_group_load = r'group_students\[g\[\'id\'\]\] = \[\{\'name\': s\[\'student_name\'\], \'phone\': s\[\'student_phone\'\}\} for s in students\]'
    content = re.sub(old_group_load, group_logic_patch.strip(), content)

    # 3. Eski "Dars jadvali qo'shish" funksiyasiga kirish nuqtasini (callback) o'chirish
    content = content.replace('builder.row(InlineKeyboardButton(text="➕ Yangi jadval", callback_data="admin_add_schedule"))', '')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Muvaffaqiyatli yakunlandi!")
    print("1. Admin paneldagi ortiqcha tugmalar olib tashlandi.")
    print("2. Guruh vaqtlari avtomatik dars jadvaliga (PDF va Eslatmalar uchun) ulandi.")

if __name__ == "__main__":
    update_bot_logic()
