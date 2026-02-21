# handlers/categories.py
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3
from config import ADMIN_CHAT_ID
from constants import EMOJI
from database import (
    get_all_categories, add_category, update_category, delete_category,
    get_category, get_products_by_category_and_type
)

class CategoryStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_icon = State()
    waiting_for_edit_name = State()
    waiting_for_edit_description = State()
    waiting_for_edit_icon = State()
    waiting_for_delete_confirm = State()
    waiting_for_hide_confirm = State()

def is_admin(user_id):
    return user_id == ADMIN_CHAT_ID

async def cmd_categories(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{EMOJI['warning']} У вас нет прав администратора.")
        return
    cats = get_all_categories(show_hidden=False)
    if not cats:
        await message.answer(
            f"{EMOJI['info']} *Категории*\n\nНет категорий.\n"
            f"/init_categories – создать стандартные\n/add_category – создать вручную",
            parse_mode="Markdown"
        )
        return
    text = f"{EMOJI['catalog']} *Активные категории*\n{'─'*30}\n"
    builder = InlineKeyboardBuilder()
    for cid, name, desc, icon in cats:
        phys = len(get_products_by_category_and_type(cid, 'physical', False))
        dig = len(get_products_by_category_and_type(cid, 'digital', False))
        text += f"{icon} *{name}*\n   👙 {phys} | 📸 {dig}\n"
        builder.button(text=f"{icon} {name}", callback_data=f"admin_cat_{cid}")
    builder.button(text=f"{EMOJI['forward']} Создать", callback_data="add_category")
    builder.button(text=f"{EMOJI['settings']} Скрытые", callback_data="show_hidden_categories")
    builder.button(text=f"{EMOJI['back']} Назад", callback_data="back_to_admin")
    builder.adjust(2)
    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

async def show_hidden_categories(callback: types.CallbackQuery):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, icon FROM categories WHERE is_hidden=1 ORDER BY name")
    cats = cur.fetchall()
    conn.close()
    if not cats:
        await callback.message.edit_text(
            f"{EMOJI['info']} *Скрытые категории*\n\nНет скрытых.",
            parse_mode="Markdown",
            reply_markup=back_to_categories_button()
        )
        await callback.answer()
        return
    text = f"{EMOJI['settings']} *Скрытые категории*\n{'─'*30}\n"
    builder = InlineKeyboardBuilder()
    for cid, name, desc, icon in cats:
        text += f"{icon} *{name}*\n"
        builder.button(text=f"{icon} {name}", callback_data=f"hidden_cat_{cid}")
    builder.button(text=f"{EMOJI['back']} Назад", callback_data="back_to_categories")
    builder.adjust(2)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

async def show_category_admin(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    cat = get_category(cid)
    if not cat:
        await callback.answer(f"{EMOJI['error']} Не найдена")
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT is_hidden FROM categories WHERE id=?", (cid,))
    hidden = cur.fetchone()[0]
    conn.close()
    phys = len(get_products_by_category_and_type(cid, 'physical', False))
    dig = len(get_products_by_category_and_type(cid, 'digital', False))
    text = (
        f"{cat[3]} *Управление категорией*{' (СКРЫТА)' if hidden else ''}\n"
        f"{'─'*30}\n"
        f"Название: *{cat[1]}*\nОписание: _{cat[2]}_\n"
        f"Товары: 👙 {phys} | 📸 {dig}\n\n"
        f"Действия:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['edit']} Редактировать", callback_data=f"edit_category_{cid}")
    if hidden:
        builder.button(text=f"{EMOJI['check']} Показать", callback_data=f"unhide_category_{cid}")
    else:
        builder.button(text=f"{EMOJI['settings']} Скрыть", callback_data=f"hide_category_{cid}")
    builder.button(text=f"{EMOJI['delete']} Удалить", callback_data=f"delete_category_{cid}")
    builder.button(text=f"{EMOJI['back']} Назад", callback_data="back_to_categories")
    builder.adjust(2)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

# ----- Создание категории -----

async def add_category_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"{EMOJI['forward']} *Создание категории*\n\nВведите название:",
        parse_mode="Markdown"
    )
    await state.set_state(CategoryStates.waiting_for_name)
    await callback.answer()

async def process_category_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"{EMOJI['info']} Введите описание (можно /skip):",
        parse_mode="Markdown"
    )
    await state.set_state(CategoryStates.waiting_for_description)

async def process_category_description(message: types.Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(description="")
    else:
        await state.update_data(description=message.text)
    await message.answer(
        f"{EMOJI['info']} Отправьте эмодзи для категории (например 👩) или /skip для 📁:",
        parse_mode="Markdown"
    )
    await state.set_state(CategoryStates.waiting_for_icon)

async def process_category_icon(message: types.Message, state: FSMContext):
    if message.text == "/skip":
        icon = "📁"
    else:
        icon = message.text.strip()[:2]
    data = await state.get_data()
    cat_id = add_category(data['name'], data.get('description', ''), icon)
    if cat_id:
        await message.answer(
            f"{EMOJI['success']} *Категория создана!*\n"
            f"{icon} {data['name']}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"{EMOJI['error']} Категория с таким именем уже существует.")
    await state.clear()

# ----- Редактирование категории -----

async def edit_category_start(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    cat = get_category(cid)
    if not cat:
        await callback.answer(f"{EMOJI['error']} Не найдена")
        return
    await state.update_data(category_id=cid, current_name=cat[1])
    await callback.message.edit_text(
        f"{EMOJI['edit']} *Редактирование*\n\nТекущее название: {cat[1]}\nВведите новое название (или /skip):",
        parse_mode="Markdown"
    )
    await state.set_state(CategoryStates.waiting_for_edit_name)
    await callback.answer()

async def process_edit_name(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(name=message.text)
    await message.answer("Введите новое описание (или /skip):")
    await state.set_state(CategoryStates.waiting_for_edit_description)

async def process_edit_description(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(description=message.text)
    await message.answer("Отправьте новый эмодзи (или /skip):")
    await state.set_state(CategoryStates.waiting_for_edit_icon)

async def process_edit_icon(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cid = data['category_id']
    old = get_category(cid)
    name = data.get('name', old[1])
    desc = data.get('description', old[2])
    if message.text != "/skip":
        icon = message.text.strip()[:2]
    else:
        icon = old[3]
    update_category(cid, name, desc, icon)
    await message.answer(f"{EMOJI['success']} Категория обновлена.")
    await state.clear()

# ----- Скрытие/показ категории -----

async def hide_category_start(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    cat = get_category(cid)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['check']} Да, скрыть", callback_data=f"confirm_hide_{cid}")
    kb.button(text=f"{EMOJI['cancel']} Нет", callback_data="cancel_hide")
    await callback.message.edit_text(
        f"{EMOJI['settings']} *Скрытие категории*\n\nСкрыть «{cat[1]}»? (будет не видна покупателям)",
        parse_mode="Markdown", reply_markup=kb.as_markup()
    )
    await state.set_state(CategoryStates.waiting_for_hide_confirm)
    await callback.answer()

async def confirm_hide(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE categories SET is_hidden=1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    await callback.message.edit_text(f"{EMOJI['success']} Категория скрыта.")
    await state.clear()
    await callback.answer()

async def unhide_category(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE categories SET is_hidden=0 WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    await callback.message.edit_text(f"{EMOJI['success']} Категория снова видна.")
    await callback.answer()

async def cancel_hide(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{EMOJI['cancel']} Отменено.")
    await callback.answer()

# ----- Удаление категории -----

async def delete_category_start(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    cat = get_category(cid)
    phys = len(get_products_by_category_and_type(cid, 'physical', False))
    dig = len(get_products_by_category_and_type(cid, 'digital', False))
    total = phys + dig
    warn = f"{EMOJI['warning']} В категории {total} товаров. " if total else ""
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['check']} Да, удалить", callback_data=f"confirm_delete_{cid}")
    kb.button(text=f"{EMOJI['cancel']} Нет", callback_data="cancel_delete")
    await callback.message.edit_text(
        f"{EMOJI['delete']} *Удаление категории*\n\n{warn}Удалить «{cat[1]}»? Товары останутся без категории.",
        parse_mode="Markdown", reply_markup=kb.as_markup()
    )
    await state.set_state(CategoryStates.waiting_for_delete_confirm)
    await callback.answer()

async def confirm_delete(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[-1])
    cat = get_category(cid)
    if cat:
        delete_category(cid)
        await callback.message.edit_text(f"{EMOJI['success']} Категория удалена.")
    else:
        await callback.message.edit_text(f"{EMOJI['error']} Категория не найдена.")
    await state.clear()
    await callback.answer()

async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{EMOJI['cancel']} Отменено.")
    await callback.answer()

def back_to_categories_button():
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['back']} Назад", callback_data="back_to_categories")
    return kb.as_markup()

def register_handlers(dp):
    dp.message.register(cmd_categories, Command("categories"))
    dp.callback_query.register(add_category_start, lambda c: c.data == "add_category")
    dp.callback_query.register(show_hidden_categories, lambda c: c.data == "show_hidden_categories")
    dp.callback_query.register(show_category_admin, lambda c: c.data.startswith("admin_cat_") or c.data.startswith("hidden_cat_"))
    dp.callback_query.register(edit_category_start, lambda c: c.data.startswith("edit_category_"))
    dp.callback_query.register(hide_category_start, lambda c: c.data.startswith("hide_category_"))
    dp.callback_query.register(unhide_category, lambda c: c.data.startswith("unhide_category_"))
    dp.callback_query.register(confirm_hide, lambda c: c.data.startswith("confirm_hide_"))
    dp.callback_query.register(cancel_hide, lambda c: c.data == "cancel_hide")
    dp.callback_query.register(delete_category_start, lambda c: c.data.startswith("delete_category_"))
    dp.callback_query.register(confirm_delete, lambda c: c.data.startswith("confirm_delete_"))
    dp.callback_query.register(cancel_delete, lambda c: c.data == "cancel_delete")
    dp.callback_query.register(lambda c: cmd_categories(c.message), lambda c: c.data == "back_to_categories")
    dp.message.register(process_category_name, CategoryStates.waiting_for_name)
    dp.message.register(process_category_description, CategoryStates.waiting_for_description)
    dp.message.register(process_category_icon, CategoryStates.waiting_for_icon)
    dp.message.register(process_edit_name, CategoryStates.waiting_for_edit_name)
    dp.message.register(process_edit_description, CategoryStates.waiting_for_edit_description)
    dp.message.register(process_edit_icon, CategoryStates.waiting_for_edit_icon)