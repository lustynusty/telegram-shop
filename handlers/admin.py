"""
handlers/admin.py – Админ-панель бота.
Содержит команды для управления товарами, категориями, просмотра статистики и перезапуска.
"""

from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3
import sys
import os
import signal
import asyncio
from config import ADMIN_CHAT_ID
from constants import EMOJI
from utils.image_processor import create_watermarked_preview
from database import (
    get_all_categories, add_category, get_all_products, get_product,
    add_product, add_product_image, get_products_by_category_and_type,
    delete_product, get_detailed_stats, get_top_buyers,
    get_visitors_stats, mark_product_sold_out
)

# ========== КЛАССЫ СОСТОЯНИЙ ==========

class AddProductStates(StatesGroup):
    """Состояния для добавления нового товара"""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price_stars = State()
    waiting_for_price_ton = State()
    waiting_for_type = State()
    waiting_for_category = State()
    waiting_for_file = State()                # для физических товаров – превью
    waiting_for_multiple_files = State()       # для цифровых – несколько фото
    waiting_for_preview_choice = State()       # выбор способа создания превью
    waiting_for_preview = State()               # ручная загрузка превью

class EditPriceStates(StatesGroup):
    waiting_for_product_id = State()
    waiting_for_price_type = State()
    waiting_for_new_price = State()

class RestartStates(StatesGroup):
    waiting_for_confirmation = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == ADMIN_CHAT_ID

# ========== ГЛАВНОЕ МЕНЮ АДМИНИСТРАТОРА ==========

async def cmd_admin(message: types.Message):
    """Главное меню админ-панели"""
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} У вас нет прав администратора.")
        return

    text = (
        f"{EMOJI['settings']} *Панель администратора*\n"
        f"{'─' * 30}\n"
        f"Выберите действие:\n\n"
        f"{EMOJI['forward']} /add\\_product – добавить товар\n"
        f"{EMOJI['edit']} /edit\\_price – изменить цену товара\n"
        f"{EMOJI['catalog']} /list\\_products – список товаров\n"
        f"{EMOJI['back']} /delete\\_product – удалить товар\n"
        f"{EMOJI['info']} /stats – статистика\n"
        f"{EMOJI['restart']} /restart – перезапустить бота\n"
        f"{EMOJI['catalog']} /categories – управление категориями\n"
        f"{EMOJI['forward']} /init\\_categories – создать стандартные категории (Лера, Катя, Настя, Лена, Оля)"
    )
    await message.answer(text, parse_mode="Markdown")

# ========== БЫСТРАЯ ИНИЦИАЛИЗАЦИЯ КАТЕГОРИЙ ==========

async def cmd_init_categories(message: types.Message):
    """Создание стандартных категорий (для быстрого старта)"""
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} У вас нет прав администратора.")
        return

    names = [
        {"name": "Лера", "icon": "👩", "desc": "Товары Леры"},
        {"name": "Катя", "icon": "👩", "desc": "Товары Кати"},
        {"name": "Настя", "icon": "👩", "desc": "Товары Насти"},
        {"name": "Лена", "icon": "👩", "desc": "Товары Лены"},
        {"name": "Оля", "icon": "👩", "desc": "Товары Оли"},
    ]

    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['check']} Да, создать", callback_data="confirm_init_categories")
    kb.button(text=f"{EMOJI['cancel']} Нет, отмена", callback_data="cancel_init_categories")
    kb.adjust(1)

    await message.answer(
        f"{EMOJI['warning']} *Инициализация категорий*\n\n"
        f"Будут созданы:\n" +
        "\n".join([f"{p['icon']} {p['name']}" for p in names]) +
        f"\n\n*Внимание!* Существующие категории будут удалены!\nПродолжить?",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

async def confirm_init_categories(callback: types.CallbackQuery):
    """Подтверждение создания стандартных категорий"""
    if not is_admin(callback.from_user.id):
        await callback.answer(f"{EMOJI['warning']} Нет прав")
        return

    names = [
        {"name": "Лера", "icon": "👩", "desc": "Товары Леры"},
        {"name": "Катя", "icon": "👩", "desc": "Товары Кати"},
        {"name": "Настя", "icon": "👩", "desc": "Товары Насти"},
        {"name": "Лена", "icon": "👩", "desc": "Товары Лены"},
        {"name": "Оля", "icon": "👩", "desc": "Товары Оли"},
    ]

    try:
        conn = sqlite3.connect("shop.db")
        cur = conn.cursor()
        cur.execute("DELETE FROM categories")
        deleted = cur.rowcount
        created = []
        for p in names:
            cur.execute("INSERT INTO categories (name, description, icon, is_hidden) VALUES (?, ?, ?, 0)",
                        (p["name"], p["desc"], p["icon"]))
            created.append(p["name"])
        conn.commit()
        conn.close()
        await callback.message.edit_text(
            f"{EMOJI['success']} *Категории созданы!*\n\n"
            f"Удалено старых: {deleted}\nСоздано новых: {len(created)}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.edit_text(f"{EMOJI['error']} Ошибка: {e}")
    await callback.answer()

async def cancel_init_categories(callback: types.CallbackQuery):
    await callback.message.edit_text(f"{EMOJI['cancel']} Отменено.")
    await callback.answer()

# ========== ДОБАВЛЕНИЕ ТОВАРА ==========

async def cmd_add_product(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} Нет прав")
        return
    await message.answer(
        f"{EMOJI['forward']} *Добавление товара*\n\n"
        f"{EMOJI['info']} Введите *название* товара:",
        parse_mode="Markdown"
    )
    await state.set_state(AddProductStates.waiting_for_name)

async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"{EMOJI['info']} Введите *описание* товара:",
        parse_mode="Markdown"
    )
    await state.set_state(AddProductStates.waiting_for_description)

async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        f"{EMOJI['stars']} Введите *цену в Stars* (только число, например 50):",
        parse_mode="Markdown"
    )
    await state.set_state(AddProductStates.waiting_for_price_stars)

async def process_price_stars(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price_stars=price)
        await message.answer(
            f"{EMOJI['ton']} Введите *цену в TON* (например 0.5):",
            parse_mode="Markdown"
        )
        await state.set_state(AddProductStates.waiting_for_price_ton)
    except ValueError:
        await message.answer(f"{EMOJI['error']} Введите целое положительное число.")

async def process_price_ton(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price_ton=price)
        kb = InlineKeyboardBuilder()
        kb.button(text=f"{EMOJI['physical']} Физический (бельё)", callback_data="type_physical")
        kb.button(text=f"{EMOJI['digital']} Цифровой (фото)", callback_data="type_digital")
        kb.adjust(1)
        await message.answer(
            f"{EMOJI['info']} Выберите *тип товара*:",
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )
        await state.set_state(AddProductStates.waiting_for_type)
    except ValueError:
        await message.answer(f"{EMOJI['error']} Введите число (например 0.5).")

async def process_type(callback: types.CallbackQuery, state: FSMContext):
    product_type = callback.data.split("_")[1]
    await state.update_data(type=product_type)
    # Показываем выбор категории
    categories = get_all_categories(show_hidden=False)
    if not categories:
        kb = InlineKeyboardBuilder()
        kb.button(text=f"{EMOJI['forward']} Создать категории", callback_data="go_to_init_categories")
        await callback.message.edit_text(
            f"{EMOJI['warning']} *Нет категорий*\nСначала создайте категории командой /init_categories",
            parse_mode="Markdown", reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for cat_id, name, desc, icon in categories:
        kb.button(text=f"{icon} {name}", callback_data=f"choose_cat_{cat_id}")
    kb.adjust(2)
    await callback.message.edit_text(
        f"{EMOJI['info']} Выберите *категорию*:",
        parse_mode="Markdown", reply_markup=kb.as_markup()
    )
    await state.set_state(AddProductStates.waiting_for_category)
    await callback.answer()

async def process_category_choice(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=cat_id)
    data = await state.get_data()
    if data['type'] == 'digital':
        await callback.message.edit_text(
            f"{EMOJI['digital']} *Загрузка фотографий*\n\n"
            f"Отправляйте фотографии по одной.\n"
            f"Когда закончите, отправьте /done.\n\n"
            f"Отправьте первое фото:",
            parse_mode="Markdown"
        )
        await state.set_state(AddProductStates.waiting_for_multiple_files)
        await state.update_data(images=[])
    else:
        await callback.message.edit_text(
            f"{EMOJI['physical']} Отправьте *фото товара* для превью.\n"
            f"Или /skip, если без фото:",
            parse_mode="Markdown"
        )
        await state.set_state(AddProductStates.waiting_for_file)
    await callback.answer()

async def process_multiple_files(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer(f"{EMOJI['error']} Отправьте фото.")
        return
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    images = data.get('images', [])
    images.append(file_id)
    await state.update_data(images=images)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['check']} Завершить загрузку", callback_data="done_uploading")
    await message.answer(
        f"{EMOJI['success']} Фото {len(images)} добавлено.\n"
        f"Всего фото: {len(images)}",
        reply_markup=kb.as_markup()
    )

async def done_uploading(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    images = data.get('images', [])
    await save_digital_product(callback.message, state, images)
    await callback.answer()

async def process_file(message: types.Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        await state.update_data(preview_image=file_id)
        await save_physical_product(message, state)
    elif message.text == "/skip":
        await state.update_data(preview_image=None)
        await save_physical_product(message, state)
    else:
        await message.answer(f"{EMOJI['error']} Отправьте фото или /skip")

async def save_physical_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (category_id, name, description, price_stars, price_ton, type, preview_image, in_stock)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (data['category_id'], data['name'], data['description'],
          data['price_stars'], data['price_ton'], data['type'],
          data.get('preview_image')))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    await message.answer(
        f"{EMOJI['success']} *Физический товар добавлен!*\n"
        f"ID: {pid}\nНазвание: {data['name']}\n"
        f"Цена: {data['price_stars']}{EMOJI['stars']} / {data['price_ton']}{EMOJI['ton']}",
        parse_mode="Markdown"
    )
    await state.clear()

async def save_digital_product(message: types.Message, state: FSMContext, images):
    data = await state.get_data()
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (category_id, name, description, price_stars, price_ton, type, in_stock)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (data['category_id'], data['name'], data['description'],
          data['price_stars'], data['price_ton'], data['type']))
    pid = cur.lastrowid
    for i, fid in enumerate(images):
        cur.execute("INSERT INTO product_images (product_id, file_id, sort_order) VALUES (?, ?, ?)",
                    (pid, fid, i))
    conn.commit()
    conn.close()
    await message.answer(
        f"{EMOJI['success']} *Цифровой товар добавлен!*\n"
        f"ID: {pid}\nНазвание: {data['name']}\n"
        f"Цена: {data['price_stars']}{EMOJI['stars']} / {data['price_ton']}{EMOJI['ton']}\n"
        f"📸 Фото: {len(images)}",
        parse_mode="Markdown"
    )
    await state.clear()

# ========== СПИСОК ТОВАРОВ ==========

async def cmd_list_products(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} Нет прав")
        return
    products = get_all_products()
    if not products:
        await message.answer(f"{EMOJI['info']} Товаров нет.")
        return
    text = f"{EMOJI['catalog']} *Список товаров*\n{'─'*30}\n"
    for p in products:
        pid, name, desc, p_stars, p_ton, ptype, preview, in_stock, sold, cat_id, cat_name = p
        icon = EMOJI['physical'] if ptype=='physical' else EMOJI['digital']
        status = f"{EMOJI['in_stock']} В наличии" if in_stock else f"{EMOJI['sold_out']} Закончился"
        text += f"{icon} *ID {pid}.* {name}\n"
        text += f"   Категория: {cat_name or 'Без кат.'}\n"
        text += f"   {p_stars}{EMOJI['stars']} / {p_ton}{EMOJI['ton']}\n"
        text += f"   Статус: {status} | Продано: {sold}\n\n"
        if len(text) > 3000:
            await message.answer(text, parse_mode="Markdown")
            text = f"{EMOJI['catalog']} *Список товаров (продолжение)*\n{'─'*30}\n"
    if text:
        await message.answer(text, parse_mode="Markdown")

# ========== УДАЛЕНИЕ ТОВАРА ==========

async def cmd_delete_product(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} Нет прав")
        return
    await message.answer(
        f"{EMOJI['warning']} *Удаление товара*\n\nВведите ID товара для удаления:",
        parse_mode="Markdown"
    )

async def process_delete(message: types.Message):
    try:
        pid = int(message.text)
        prod = get_product(pid)
        if not prod:
            await message.answer(f"{EMOJI['error']} Товар с ID {pid} не найден.")
            return
        delete_product(pid)
        await message.answer(f"{EMOJI['success']} Товар ID {pid} удалён.")
    except ValueError:
        await message.answer(f"{EMOJI['error']} Введите корректный ID.")

# ========== ИЗМЕНЕНИЕ ЦЕНЫ ==========

async def cmd_edit_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} Нет прав")
        return
    products = get_all_products()
    if not products:
        await message.answer(f"{EMOJI['info']} Товаров нет.")
        return
    text = f"{EMOJI['edit']} *Изменение цены*\n\nВведите ID товара:\n"
    for p in products[:10]:
        pid, name, *_ = p
        text += f"• ID {pid}: {name}\n"
    await message.answer(text, parse_mode="Markdown")
    await state.set_state(EditPriceStates.waiting_for_product_id)

async def process_edit_product_id(message: types.Message, state: FSMContext):
    try:
        pid = int(message.text)
        prod = get_product(pid)
        if not prod:
            await message.answer(f"{EMOJI['error']} Товар не найден.")
            return
        await state.update_data(product_id=pid, product_name=prod[1])
        kb = InlineKeyboardBuilder()
        kb.button(text=f"{EMOJI['stars']} Stars", callback_data="price_stars")
        kb.button(text=f"{EMOJI['ton']} TON", callback_data="price_ton")
        await message.answer("Что меняем?", reply_markup=kb.as_markup())
        await state.set_state(EditPriceStates.waiting_for_price_type)
    except ValueError:
        await message.answer(f"{EMOJI['error']} Введите число.")

async def process_price_type(callback: types.CallbackQuery, state: FSMContext):
    price_type = callback.data  # 'price_stars' или 'price_ton'
    await state.update_data(price_type=price_type)
    await callback.message.edit_text(
        f"{EMOJI['info']} Введите новую цену:",
        parse_mode="Markdown"
    )
    await state.set_state(EditPriceStates.waiting_for_new_price)
    await callback.answer()

async def process_new_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data['product_id']
    price_type = data['price_type']
    try:
        if price_type == 'price_stars':
            new_price = int(message.text)
            field = "price_stars"
        else:
            new_price = float(message.text)
            field = "price_ton"
        conn = sqlite3.connect("shop.db")
        cur = conn.cursor()
        cur.execute(f"UPDATE products SET {field}=? WHERE id=?", (new_price, pid))
        conn.commit()
        conn.close()
        await message.answer(f"{EMOJI['success']} Цена обновлена.")
    except ValueError:
        await message.answer(f"{EMOJI['error']} Неверное число.")
    await state.clear()

# ========== СТАТИСТИКА ==========

async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} Нет прав")
        return
    stats = get_detailed_stats()
    visitors = get_visitors_stats()
    top = get_top_buyers(5)
    text = (
        f"{EMOJI['stats']} *Статистика магазина*\n"
        f"{'─'*30}\n"
        f"*Товары:* {stats['total_products']}\n"
        f"  👙 Физических в наличии: {stats['physical_available']}\n"
        f"  📸 Цифровых: {stats['digital_total']}\n"
        f"*Заказы:* всего {stats['total_orders']}, оплачено {stats['paid_orders']}\n"
        f"  ⭐ Stars: {stats['stars_orders']}, 💎 TON: {stats['ton_orders']}\n"
        f"*Выручка:* ⭐ {stats['total_stars_earned']}, 💎 {stats['total_ton_earned']:.2f}\n"
        f"*Пользователи:* всего {visitors[0]}, сегодня {visitors[1]}\n"
    )
    if top:
        text += "*Топ покупателей:*\n"
        for i, (uname, full, cnt, spent) in enumerate(top, 1):
            name = full or f"@{uname}" if uname else "Аноним"
            text += f"  {i}. {name}: {cnt} зак., {spent:.2f}⭐\n"
    await message.answer(text, parse_mode="Markdown")

# ========== ПЕРЕЗАПУСК БОТА ==========

async def cmd_restart(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} Нет прав")
        return
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['check']} Да, перезапустить", callback_data="confirm_restart")
    kb.button(text=f"{EMOJI['cancel']} Нет, отмена", callback_data="cancel_restart")
    await message.answer(
        f"{EMOJI['restart']} *Перезапуск бота*\n\nВы уверены?",
        parse_mode="Markdown", reply_markup=kb.as_markup()
    )
    await state.set_state(RestartStates.waiting_for_confirmation)

async def confirm_restart(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"{EMOJI['restart']} Перезапуск...")
    await asyncio.sleep(2)
    await state.clear()
    # Завершаем процесс – на Railway он будет перезапущен автоматически
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit(0)

async def cancel_restart(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{EMOJI['cancel']} Отменено.")
    await callback.answer()

# ========== РЕГИСТРАЦИЯ ХЭНДЛЕРОВ ==========

def register_handlers(dp):
    # Команды админа
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_add_product, Command("add_product"))
    dp.message.register(cmd_edit_price, Command("edit_price"))
    dp.message.register(cmd_list_products, Command("list_products"))
    dp.message.register(cmd_delete_product, Command("delete_product"))
    dp.message.register(cmd_stats, Command("stats"))
    dp.message.register(cmd_restart, Command("restart"))
    dp.message.register(cmd_init_categories, Command("init_categories"))

    # Инициализация категорий
    dp.callback_query.register(confirm_init_categories, lambda c: c.data == "confirm_init_categories")
    dp.callback_query.register(cancel_init_categories, lambda c: c.data == "cancel_init_categories")
    dp.callback_query.register(lambda c: cmd_init_categories(c.message), lambda c: c.data == "go_to_init_categories")

    # Добавление товара
    dp.message.register(process_name, AddProductStates.waiting_for_name)
    dp.message.register(process_description, AddProductStates.waiting_for_description)
    dp.message.register(process_price_stars, AddProductStates.waiting_for_price_stars)
    dp.message.register(process_price_ton, AddProductStates.waiting_for_price_ton)
    dp.message.register(process_multiple_files, AddProductStates.waiting_for_multiple_files, F.photo)
    dp.message.register(process_file, AddProductStates.waiting_for_file, F.photo | F.text)
    dp.callback_query.register(process_type, AddProductStates.waiting_for_type,
                               lambda c: c.data in ["type_physical", "type_digital"])
    dp.callback_query.register(process_category_choice, AddProductStates.waiting_for_category,
                               lambda c: c.data.startswith("choose_cat_"))
    dp.callback_query.register(done_uploading, lambda c: c.data == "done_uploading")

    # Изменение цены
    dp.message.register(process_edit_product_id, EditPriceStates.waiting_for_product_id)
    dp.message.register(process_new_price, EditPriceStates.waiting_for_new_price)
    dp.callback_query.register(process_price_type, EditPriceStates.waiting_for_price_type,
                               lambda c: c.data in ["price_stars", "price_ton"])

    # Удаление товара
    dp.message.register(process_delete, Command("delete_product"))

    # Перезапуск
    dp.callback_query.register(confirm_restart, RestartStates.waiting_for_confirmation,
                               lambda c: c.data == "confirm_restart")
    dp.callback_query.register(cancel_restart, RestartStates.waiting_for_confirmation,
                               lambda c: c.data == "cancel_restart")