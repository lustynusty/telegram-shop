# handlers/tracking.py
from aiogram import types
from aiogram.filters import Command
from database import get_order_by_tracking
from constants import EMOJI

async def cmd_track(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            f"{EMOJI['info']} *Отслеживание*\nВведите номер заказа после команды, например:\n`/track ORD-240201-ABC123`",
            parse_mode="Markdown")
        return
    track = args[1].strip().upper()
    order = get_order_by_tracking(track)
    if not order:
        await message.answer(f"{EMOJI['error']} Заказ `{track}` не найден.", parse_mode="Markdown")
        return
    # Распарсить order и показать статус
    status_emoji = {
        'pending': '⏳',
        'paid': '✅',
        'shipped': '📦',
        'delivered': '🏠'
    }.get(order[8], '❓')
    status_text = {
        'pending': 'Ожидает оплаты',
        'paid': 'Оплачен, ожидает отправки',
        'shipped': 'Отправлен',
        'delivered': 'Доставлен'
    }.get(order[8], 'Неизвестно')
    text = (
        f"{EMOJI['track']} *Статус заказа*\n"
        f"Номер: `{track}`\n"
        f"Товар: {order[-1]}\n"
        f"Статус: {status_emoji} {status_text}\n"
    )
    if order[11]:  # адрес
        text += f"Адрес: {order[11]}\n"
    await message.answer(text, parse_mode="Markdown")

def register_handlers(dp):
    dp.message.register(cmd_track, Command("track"))