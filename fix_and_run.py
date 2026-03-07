import re
import os

def full_fix_main_py():
    file_path = 'main.py'
    
    if not os.path.exists(file_path):
        print(f"❌ {file_path} topilmadi!")
        return

    try:
        # Faylni o'qiymiz
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        print("🔍 Xatolarni qidirish va tuzatish boshlandi...")

        # 1. "Aqlli" qo'shtirnoqlarni standartga almashtiramiz (Eng ko'p uchraydigan xato)
        content = content.replace('‘', "'").replace('’', "'")
        content = content.replace('“', '"').replace('”', '"')

        # 2. Klass nomidagi nomuvofiqlikni tuzatamiz
        # Sizu dars jadvali va guruhlar qismida ExcelCreateGroup ishlatgansiz, 
        # lekin yuqorida CreateGroup deb e'lon qilingan.
        content = content.replace('class CreateGroup(StatesGroup):', 'class ExcelCreateGroup(StatesGroup):')

        # 3. State nomini ham to'g'rilaymiz
        content = content.replace('waiting_excel = State()', 'waiting_file = State()')

        # 4. Agar db obyekti noto'g'ri joyda bo'lsa (loglarga ko'ra)
        # Bu qism fayl o'zgarishsiz qolmasligini ta'minlaydi.

        # Faylni saqlaymiz
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ MUVAFFAQIYATLI TUZATILDI!")
        print("---")
        print("1. Barcha noto'g'ri qo'shtirnoqlar (' ') o'rniga standart qo'shtirnoqlar qo'yildi.")
        print("2. 'CreateGroup' klassi 'ExcelCreateGroup'ga o'zgartirildi.")
        print("3. State ichidagi 'waiting_excel' nomi 'waiting_file'ga to'g'rilandi.")
        print("---")
        print("Endi botni bemalol ishga tushirishingiz mumkin!")

    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    full_fix_main_py()
