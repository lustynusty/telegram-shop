# bot.py
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from config import BOT_TOKEN, DB_PATH
from database import init_db, get_all_categories, add_category, get_all_products
from handlers import start, catalog, payment_stars, payment_ton, delivery, admin, categories, support, tracking

logging.basicConfig(level=logging.INFO)

session = AiohttpSession(timeout=60)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

def migrate_db():
    """Обновление структуры БД (добавление новых колонок)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Добавляем колонку is_hidden в categories
        cur.execute("PRAGMA table_info(categories)")
        cols = [c[1] for c in cur.fetchall()]
        if 'is_hidden' not in cols:
            cur.execute("ALTER TABLE categories ADD COLUMN is_hidden INTEGER DEFAULT 0")
            logging.info("Добавлена колонка is_hidden в categories")
        # Аналогично можно добавить другие колонки, если нужно
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка миграции: {e}")

def setup_database():
    """Инициализация БД и создание тестовых категорий при необходимости"""
    logging.info("Инициализация базы данных...")
    init_db()
    migrate_db()

    # Если нет категорий, создаём стандартные
    if not get_all_categories(show_hidden=True):
        logging.info("Добавляем категории по именам...")
        names = [
            {"name": "Лера", "icon": "👩", "desc": "Товары Леры"},
            {"name": "Катя", "icon": "👩", "desc": "Товары Кати"},
            {"name": "Настя", "icon": "👩", "desc": "Товары Насти"},
            {"name": "Лена", "icon": "👩", "desc": "Товары Лены"},
            {"name": "Оля", "icon": "👩", "desc": "Товары Оли"},
        ]
        for p in names:
            add_category(p["name"], p["desc"], p["icon"])
            logging.info(f"  ✓ Добавлена категория {p['icon']} {p['name']}")

    # Можно также добавить тестовые товары, если нужно
    # ...

# Регистрация всех обработчиков
start.register_handlers(dp)
catalog.register_handlers(dp)
payment_stars.register_handlers(dp)
payment_ton.register_handlers(dp)
delivery.register_handlers(dp)
admin.register_handlers(dp)
categories.register_handlers(dp)
support.register_handlers(dp)
tracking.register_handlers(dp)

async def main():
    setup_database()
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")