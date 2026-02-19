import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from datetime import datetime
from aiohttp import web
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- LOGGING SOZLAMALARI ---
logging.basicConfig(level=logging.INFO)

# --- ASOSIY SOZLAMALAR ---
# Yangi API Tokeningiz
TOKEN = "8268187024:AAGVlMOzOUTXMyrB8ePj9vHcayshkZ4PGW4"
ADMIN_GROUP_ID = -1003885800610

# Manzillar ro'yxati
LOCATIONS = [
    {"name": "Kimyo Xalqaro Universiteti", "lat": 41.257490, "lon": 69.220109},
    {"name": "78-Maktab", "lat": 41.282791, "lon": 69.173290}
]
ALLOWED_DISTANCE = 150 # Metrda

# --- GOOGLE SHEETS ULANISH FUNKSIYASI ---
def connect_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # credentials.json fayli GitHub'da bo'lishi shart
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        # Jadval nomi Google Sheets'da aynan 'Davomat_Log' bo'lishi shart
        return client.open("Davomat_Log").sheet1
    except Exception as e:
        logging.error(f"Google Sheets ulanishda xatolik: {e}")
        return None

# Global sheet obyekti
sheet = connect_google_sheets()

# --- BOT VA XOTIRA ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
user_names = {}
attendance_log = set()
