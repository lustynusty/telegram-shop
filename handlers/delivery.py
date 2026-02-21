# handlers/delivery.py
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3
from config import ADMIN_CHAT_ID
from constants import EMOJI

class DeliveryStates(StatesGroup):
    waiting_for_address = State()

def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['catalog']} Каталог", callback_data="go_to_catalog")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

async def address_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer(f"{EMOJI['error']} Ошибка: заказ не найден")
        await state.clear()
        return
    address = message.text
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET delivery_address = ? WHERE id = ?", (address, order_id))
    conn.commit()
    conn.close()
    await message.answer(
        f"{EMOJI['success']} *Адрес сохранён!*\nЗаказ №{order_id}\nСкоро мы отправим ваше бельё.",
        parse_mode="Markdown", reply_markup=main_menu_keyboard())
    await message.bot.send_message(ADMIN_CHAT_ID,
        f"{EMOJI['delivery']} *Новый адрес доставки*\nЗаказ {order_id}\nАдрес: {address}",
        parse_mode="Markdown")
    await state.clear()

def register_handlers(dp):
    dp.message.register(address_received, DeliveryStates.waiting_for_address, F.text)