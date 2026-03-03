import asyncpg
import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Set
from collections import defaultdict

# Xatoliklarni kuzatish uchun logging
logging.basicConfig(level=logging.INFO)

class Database:
    """PostgreSQL bilan ishlash uchun class"""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None
    
    async def create_pool(self):
    try:
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=1,
            max_size=5,
            command_timeout=30,
            ssl='require',
            max_queries=50000,
            max_inactive_connection_lifetime=300
        )
        print("✅ PostgreSQL pool yaratildi")
    except Exception as e:
        print(f"❌ PostgreSQL pool yaratishda xatolik: {e}")
        raise
    
    async def init_tables(self):
        """Jadvallarni yaratish"""
        async with self.pool.acquire() as conn:
            # Foydalanuvchilar jadvali
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    specialty TEXT,
                    status TEXT DEFAULT 'active',
                    language TEXT DEFAULT 'uz',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Davomatlar jadvali
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    branch TEXT NOT NULL,
                    date DATE NOT NULL,
                    time TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, branch, date)
                )
            ''')
            
            # Dars jadvallari jadvali - MUHIM: days_data ishlatilgan
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_id TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    branch TEXT NOT NULL,
                    lesson_type TEXT,
                    days_data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Indekslar
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_attendance_user ON attendance(user_id)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_schedules_user ON schedules(user_id)')
            
            print("✅ Jadvallar yaratildi")
    
    # --- FOYDALANUVCHILAR ---
    async def add_user(self, user_id: int, full_name: str, specialty: str = None, language: str = 'uz'):
        """Yangi foydalanuvchi qo'shish"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, full_name, specialty, language)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    specialty = COALESCE(EXCLUDED.specialty, users.specialty),
                    language = EXCLUDED.language
            ''', user_id, full_name, specialty, language)
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Foydalanuvchi ma'lumotlarini olish"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
            return dict(row) if row else None
    
    async def get_all_users(self) -> List[Dict]:
        """Barcha foydalanuvchilar"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM users ORDER BY user_id')
            return [dict(row) for row in rows]
    
    async def get_active_users(self) -> List[Dict]:
        """Faol foydalanuvchilar"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM users WHERE status = $1 ORDER BY user_id', 'active')
            return [dict(row) for row in rows]
    
    async def get_blocked_users(self) -> List[Dict]:
        """Bloklangan foydalanuvchilar"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM users WHERE status = $1 ORDER BY user_id', 'blocked')
            return [dict(row) for row in rows]
    
    async def update_user_status(self, user_id: int, status: str):
        """Foydalanuvchi holatini o'zgartirish"""
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET status = $1 WHERE user_id = $2', status, user_id)
    
    async def update_user_language(self, user_id: int, language: str):
        """Foydalanuvchi tilini o'zgartirish"""
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET language = $1 WHERE user_id = $2', language, user_id)
    
    async def update_user_specialty(self, user_id: int, specialty: str):
        """Foydalanuvchi mutaxassisligini o'zgartirish"""
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET specialty = $1 WHERE user_id = $2', specialty, user_id)
    
    # --- DAVOMATLAR ---
    async def add_attendance(self, user_id: int, branch: str, date: str, time: str):
        """Yangi davomat qo'shish"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO attendance (user_id, branch, date, time)
                VALUES ($1, $2, $3::date, $4)
                ON CONFLICT (user_id, branch, date) DO NOTHING
            ''', user_id, branch, date, time)
    
    # ✅ YANGI QO'SHILGAN METOD: check_attendance
    async def check_attendance(self, user_id: int, branch: str, date: str) -> bool:
        """Bugun shu filialda davomat qilinganmi?"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT 1 FROM attendance 
                WHERE user_id = $1 AND branch = $2 AND date = $3::date
            ''', user_id, branch, date)
            return row is not None
    
    async def get_user_attendances(self, user_id: int) -> List[Tuple]:
        """Foydalanuvchining barcha davomatlari"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT branch, date, time FROM attendance 
                WHERE user_id = $1 
                ORDER BY date DESC, time DESC
            ''', user_id)
            return [(row['branch'], row['date'].strftime('%Y-%m-%d'), row['time']) for row in rows]
    
    async def get_daily_attendances(self, date: str) -> List[Dict]:
        """Kunlik davomatlar (batafsil)"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT a.*, u.full_name, u.specialty, u.status
                FROM attendance a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.date = $1::date
                ORDER BY a.time
            ''', date)
            return [dict(row) for row in rows]
    
    async def get_attendance_stats(self, start_date: str, end_date: str) -> Dict:
        """Davomat statistikasi"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT 
                    branch,
                    COUNT(*) as total,
                    COUNT(DISTINCT user_id) as unique_teachers,
                    DATE(date) as day
                FROM attendance 
                WHERE date BETWEEN $1::date AND $2::date
                GROUP BY branch, DATE(date)
                ORDER BY day DESC
            ''', start_date, end_date)
            
            stats = defaultdict(lambda: {'total': 0, 'teachers': set(), 'daily': {}})
            for row in rows:
                branch = row['branch']
                stats[branch]['total'] += row['total']
                stats[branch]['teachers'].add(row['unique_teachers'])
                stats[branch]['daily'][row['day'].strftime('%Y-%m-%d')] = row['total']
            
            # Set obyektlarini JSON formatlash uchun listga aylantirish
            for b in stats:
                stats[b]['teachers'] = list(stats[b]['teachers'])
            
            return dict(stats)
    
    async def get_monthly_stats(self, year_month: str) -> Dict:
        """Oylik statistika"""
        start_date = f"{year_month}-01"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT branch, COUNT(*) as count, COUNT(DISTINCT user_id) as teachers
                FROM attendance 
                WHERE date >= $1::date AND date < ($1::date + INTERVAL '1 month')
                GROUP BY branch
                ORDER BY count DESC
            ''', start_date)
            return {row['branch']: {'count': row['count'], 'teachers': row['teachers']} for row in rows}
    
    # --- DARS JADVALLARI - MUHIM: days_data ishlatilgan ---
    async def add_schedule(self, schedule_id: str, user_id: int, branch: str, lesson_type: str, days: dict):
        """Dars jadvali qo'shish - days_data ustuniga saqlaydi"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO schedules (schedule_id, user_id, branch, lesson_type, days_data)
                VALUES ($1, $2, $3, $4, $5::jsonb)
            ''', schedule_id, user_id, branch, lesson_type, json.dumps(days))
    
    async def get_user_schedules(self, user_id: int) -> List[Dict]:
        """Foydalanuvchining dars jadvallari"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM schedules WHERE user_id = $1 ORDER BY created_at
            ''', user_id)
            result = []
            for row in rows:
                data = dict(row)
                data['days'] = json.loads(data['days_data'])  # days_data ni days ga o'giramiz
                result.append(data)
            return result
    
    async def get_all_schedules(self) -> List[Dict]:
        """Barcha dars jadvallari"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM schedules ORDER BY created_at')
            result = []
            for row in rows:
                data = dict(row)
                data['days'] = json.loads(data['days_data'])
                result.append(data)
            return result
    
    async def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Bitta dars jadvalini olish"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM schedules WHERE schedule_id = $1', schedule_id)
            if row:
                data = dict(row)
                data['days'] = json.loads(data['days_data'])
                return data
            return None
    
    async def update_schedule(self, schedule_id: str, branch: str, lesson_type: str, days: dict):
        """Dars jadvalini yangilash"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE schedules 
                SET branch = $1, lesson_type = $2, days_data = $3::jsonb
                WHERE schedule_id = $4
            ''', branch, lesson_type, json.dumps(days), schedule_id)
    
    async def delete_schedule(self, schedule_id: str):
        """Dars jadvalini o'chirish"""
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM schedules WHERE schedule_id = $1', schedule_id)
    
    # --- MA'LUMOTLARNI MIGRATSIYA QILISH ---
    async def migrate_from_ram(self, 
                               user_names: dict,
                               user_specialty: dict,
                               user_status: dict,
                               user_languages: dict,
                               daily_attendance_log: set,
                               schedules: dict,
                               user_schedules: dict):
        """RAMdagi ma'lumotlarni PostgreSQLga ko'chirish"""
        
        print("🔄 Ma'lumotlarni migratsiya qilish boshlandi...")
        
        async with self.pool.acquire() as conn:
            # Bitta connection ichida ishlash optimizatsiya uchun
            # Foydalanuvchilarni ko'chirish
            user_count = 0
            for user_id, name in user_names.items():
                specialty = user_specialty.get(user_id)
                status = user_status.get(user_id, 'active')
                lang = user_languages.get(user_id, 'uz')
                
                await conn.execute('''
                    INSERT INTO users (user_id, full_name, specialty, status, language)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        specialty = EXCLUDED.specialty,
                        status = EXCLUDED.status,
                        language = EXCLUDED.language
                ''', user_id, name, specialty, status, lang)
                user_count += 1
            
            # Davomatlarni ko'chirish
            attendance_count = 0
            for uid, branch, date, time in daily_attendance_log:
                await conn.execute('''
                    INSERT INTO attendance (user_id, branch, date, time)
                    VALUES ($1, $2, $3::date, $4)
                    ON CONFLICT DO NOTHING
                ''', uid, branch, date, time)
                attendance_count += 1
            
            # Dars jadvallarini ko'chirish
            schedule_count = 0
            for schedule_id, schedule in schedules.items():
                user_id = schedule['user_id']
                branch = schedule['branch']
                lesson_type = schedule.get('lesson_type', 'Dars')
                days = schedule['days']
                
                await conn.execute('''
                    INSERT INTO schedules (schedule_id, user_id, branch, lesson_type, days_data)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    ON CONFLICT (schedule_id) DO NOTHING
                ''', schedule_id, user_id, branch, lesson_type, json.dumps(days))
                schedule_count += 1
        
        print(f"✅ Migratsiya tugadi: {user_count} foydalanuvchi, {attendance_count} davomat, {schedule_count} jadval")
    
    # --- YORDAMCHI FUNKSIYALAR ---
    async def get_statistics(self) -> Dict:
        """Umumiy statistika"""
        async with self.pool.acquire() as conn:
            # Foydalanuvchilar soni
            total_users = await conn.fetchval('SELECT COUNT(*) FROM users')
            active_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE status = 'active'")
            blocked_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE status = 'blocked'")
            
            # IT va Koreys tili o'qituvchilari
            it_teachers = await conn.fetchval("SELECT COUNT(*) FROM users WHERE specialty = 'IT'")
            korean_teachers = await conn.fetchval("SELECT COUNT(*) FROM users WHERE specialty = 'Koreys tili'")
            
            # Davomatlar soni
            total_attendances = await conn.fetchval('SELECT COUNT(*) FROM attendance')
            today = datetime.now().strftime('%Y-%m-%d')
            today_attendances = await conn.fetchval('SELECT COUNT(*) FROM attendance WHERE date = $1::date', today)
            
            current_month = datetime.now().strftime('%Y-%m')
            monthly_attendances = await conn.fetchval('''
                SELECT COUNT(*) FROM attendance 
                WHERE date >= $1::date AND date < ($1::date + INTERVAL '1 month')
            ''', f"{current_month}-01")
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'blocked_users': blocked_users,
                'it_teachers': it_teachers,
                'korean_teachers': korean_teachers,
                'total_attendances': total_attendances,
                'today_attendances': today_attendances,
                'monthly_attendances': monthly_attendances
            }
    
    async def close(self):
        """Ulanishni yopish"""
        if self.pool:
            await self.pool.close()
            print("🔌 PostgreSQL ulanishi yopildi")

# TEST: database.py yuklanganligini tekshirish
print("✅ database.py yuklandi!")
print("📋 Mavjud metodlar:", [method for method in dir(Database) if not method.startswith('_')])
