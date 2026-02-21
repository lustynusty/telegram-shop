# config.py
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Путь к базе данных (для Railway volume)
if os.environ.get('RAILWAY_VOLUME_PATH'):
    DB_PATH = os.path.join(os.environ.get('RAILWAY_VOLUME_PATH'), 'shop.db')
else:
    DB_PATH = 'shop.db'

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN_STARS = os.getenv("PROVIDER_TOKEN_STARS")  # пустая строка для Stars
TON_WALLET = os.getenv("TON_WALLET")
TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY")

# ID администратора – приводим к int
admin_id_str = os.getenv("ADMIN_CHAT_ID")
if admin_id_str:
    ADMIN_CHAT_ID = int(admin_id_str)
else:
    ADMIN_CHAT_ID = None
    print("⚠️ ВНИМАНИЕ: ADMIN_CHAT_ID не задан!")

PLACEHOLDER_IMAGE_ID = os.getenv("PLACEHOLDER_IMAGE_ID")