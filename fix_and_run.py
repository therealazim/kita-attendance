import os
import re

def update_main_py():
    file_path = 'main.py'
    if not os.path.exists(file_path):
        print("❌ main.py topilmadi!")
        return

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    print("🛠 Kodni yangilash boshlandi...")

    # 1. Admin panelidagi "+ O'qituvchiga jadval qo'shish" tugmasini olib tashlash
    # Exact match: InlineKeyboardButton(text="➕ O'qituvchiga jadval qo'shish", callback_data="admin_add_schedule")
    pattern = r'InlineKeyboardButton\(text="➕ O\'qituvchiga jadval qo\'shish", callback_data="admin_add_schedule"\)'
    content = re.sub(pattern, '', content)
    
    # Ortiqcha bo'sh qatorlar va vergullarni tozalash (agar builder ichida qolib ketgan bo'lsa)
    content = content.replace('builder.row(\n            \n        )', '')

    # 2. Database.load_to_ram funksiyasini yangilaymiz (Guruhlarni dars jadvaliga bog'lash uchun)
    group_ram_logic = """
                students = await conn.fetch("SELECT * FROM group_students WHERE group_id = $1", g['id'])
                group_students[g['id']] = [{'name': s['student_name'], 'phone': s['student_phone']} for s in students]
                
                # --- YANGI: Guruhni avtomatik dars jadvaliga qo'shish ---
                t_id = g['teacher_id']
                if t_id:
                    g_days = json.loads(g['days_data'])
                    g_time = g['time_text']
                    s_id = f"grp_{g['id']}"
                    schedules[s_id] = {
                        'user_id': t_id,
                        'branch': g['branch'],
                        'lesson_type': g['lesson_type'],
                        'days': {d: g_time for d in g_days}
                    }
                    if s_id not in user_schedules[t_id]:
                        user_schedules[t_id].append(s_id)
    """
    
    old_ram_part = r'group_students\[g\[\'id\'\]\] = \[\{\'name\': s\[\'student_name\'\], \'phone\': s\[\'student_phone\'\}\} for s in students\]'
    content = re.sub(old_ram_part, group_ram_logic.strip(), content)

    # 3. Guruh yaratish handleridagi RAM yangilanishini to'g'rilash
    new_group_handler_logic = """
        groups[group_id] = {
            'group_name': data['group_name'],
            'branch': data['branch'],
            'lesson_type': data['type'],
            'teacher_id': data['teacher_id'],
            'days': data['selected_days'],
            'time': data['time']
        }
        # RAM dars jadvaliga qo'shish
        s_id = f"grp_{group_id}"
        schedules[s_id] = {
            'user_id': data['teacher_id'],
            'branch': data['branch'],
            'lesson_type': data['type'],
            'days': {d: data['time'] for d in data['selected_days']}
        }
        if s_id not in user_schedules[data['teacher_id']]:
            user_schedules[data['teacher_id']].append(s_id)
        
        group_students[group_id] = students
    """
    
    # Eskisini qidirish (taxminiy qism)
    old_handler_part = r"groups\[group_id\] = \{.*?\}\s+group_students\[group_id\] = students"
    content = re.sub(old_handler_part, new_group_handler_logic.strip(), content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Muvaffaqiyatli yakunlandi!")
    print("1. '+ O\'qituvchiga jadval qo\'shish' tugmasi o'chirildi.")
    print("2. Guruhlar endi avtomatik ravishda o'qituvchi dars jadvaliga (PDF/Eslatma uchun) ulanadi.")

if __name__ == "__main__":
    update_main_py()
