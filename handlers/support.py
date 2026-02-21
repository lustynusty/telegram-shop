# handlers/support.py
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_CHAT_ID
from constants import EMOJI
from database import add_message, get_user

class SupportStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_photo = State()

def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['catalog']} Каталог", callback_data="go_to_catalog")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

async def cmd_support(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(f"{EMOJI['warning']} Сначала /start")
        return
    await message.answer(
        f"{EMOJI['support']} *Связь с администратором*\n\nОпишите вашу проблему или вопрос. Можно отправить фото.\nНапишите сообщение (или /cancel):",
        parse_mode="Markdown")
    await state.set_state(SupportStates.waiting_for_message)

async def process_message(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{EMOJI['check']} Да, добавить фото", callback_data="support_add_photo")
    kb.button(text=f"{EMOJI['cancel']} Нет, отправить без фото", callback_data="support_no_photo")
    await message.answer(f"{EMOJI['info']} Хотите добавить фото?", reply_markup=kb.as_markup())
    await state.set_state(SupportStates.waiting_for_photo)

async def add_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(f"{EMOJI['info']} Отправьте фото (или /skip):", parse_mode="Markdown")
    await callback.answer()

async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await send_to_admin(callback.message, state, None)
    await callback.answer()

async def process_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else None
    await send_to_admin(message, state, file_id)

async def send_to_admin(message: types.Message, state: FSMContext, file_id):
    data = await state.get_data()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(f"{EMOJI['error']} Ошибка")
        await state.clear()
        return
    uid = user[0]
    msg_id = add_message(uid, data['text'], file_id)
    admin_text = f"{EMOJI['support']} *Новое сообщение*\nID: {msg_id}\nОт: @{message.from_user.username}\n{data['text']}"
    if file_id:
        await message.bot.send_photo(ADMIN_CHAT_ID, file_id, caption=admin_text, parse_mode="Markdown")
    else:
        await message.bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode="Markdown")
    await message.answer(f"{EMOJI['success']} Сообщение отправлено!", reply_markup=main_menu_keyboard())
    await state.clear()

async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(f"{EMOJI['cancel']} Отменено.", reply_markup=main_menu_keyboard())

def register_handlers(dp):
    dp.message.register(cmd_support, Command("support"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(process_message, SupportStates.waiting_for_message)
    dp.message.register(process_photo, SupportStates.waiting_for_photo, F.photo)
    dp.callback_query.register(add_photo, lambda c: c.data == "support_add_photo")
    dp.callback_query.register(skip_photo, lambda c: c.data == "support_no_photo")