# handlers/start.py
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import add_user, add_visit
from constants import EMOJI

async def cmd_start(message: types.Message, state: FSMContext = None):
    if state:
        await state.clear()
    add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    add_visit(message.from_user.id, "/start")

    text = (
        f"{EMOJI['start']} *Маркетплейс интимных сокровищ*\n\n"
        f"Здесь вы можете купить или продать уникальные экземпляры женского нижнего белья с историей — "
        f"чувственные, тёплые, пропитанные аурой своей владелицы. Каждая деталь хранит частичку настоящего "
        f"женского очарования, магии и тонкой загадки.\n\n"
        f"{EMOJI['physical']} *Бельё с доставкой*\n"
        f"{EMOJI['digital']} *Фотосеты девушек в белье*\n\n"
        f"{EMOJI['payment']} *Способы оплаты:*\n"
        f"• {EMOJI['stars']} Telegram Stars\n"
        f"• {EMOJI['ton']} Криптовалюта TON\n\n"
        f"{EMOJI['info']} Чтобы начать, выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['catalog']} Каталог", callback_data="go_to_catalog")
    builder.button(text=f"{EMOJI['support']} Связаться с админом", callback_data="go_to_support")
    builder.button(text=f"{EMOJI['track']} Отследить заказ", callback_data="go_to_track")
    builder.button(text=f"{EMOJI['help']} Помощь", callback_data="show_help")
    builder.button(text=f"{EMOJI['info']} О нас", callback_data="show_about")
    builder.adjust(1)

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

async def go_to_catalog(callback: types.CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    from handlers.catalog import cmd_catalog
    add_visit(callback.from_user.id, "catalog")
    await cmd_catalog(callback.message)
    await callback.answer()

async def go_to_support(callback: types.CallbackQuery, state: FSMContext):
    from handlers.support import cmd_support
    class FakeMessage:
        def __init__(self, chat, from_user, bot, message_id):
            self.chat = chat
            self.from_user = from_user
            self.bot = bot
            self.message_id = message_id
            self.text = "/support"
            self.answer = callback.message.answer
            self.reply = callback.message.reply
    fake = FakeMessage(callback.message.chat, callback.from_user, callback.bot, callback.message.message_id)
    await cmd_support(fake, state)
    await callback.answer()

async def go_to_track(callback: types.CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    await callback.message.edit_text(
        f"{EMOJI['track']} *Отслеживание заказа*\n\n"
        f"Чтобы отследить заказ, отправьте команду:\n"
        f"`/track НОМЕР_ЗАКАЗА`\n\n"
        f"Например: `/track ORD-240201-ABC123`\n\n"
        f"Номер заказа вы получили после оплаты.",
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    await callback.answer()

async def show_help(callback: types.CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    add_visit(callback.from_user.id, "help")
    help_text = (
        f"{EMOJI['help']} *Помощь*\n\n"
        f"*Доступные команды:*\n"
        f"{EMOJI['catalog']} /catalog - каталог\n"
        f"{EMOJI['support']} /support - поддержка\n"
        f"{EMOJI['track']} /track - отслеживание\n"
        f"{EMOJI['help']} /help - эта справка\n\n"
        f"*Как купить:*\n"
        f"1. Выберите категорию (девушку) в каталоге\n"
        f"2. Выберите тип товара: бельё или фотосет\n"
        f"3. Выберите товар и способ оплаты\n"
        f"4. Оплатите заказ\n"
        f"5. Получите товар\n\n"
        f"*Для белья:*\n"
        f"• После оплаты укажите адрес доставки\n"
        f"• Вы получите уникальный номер заказа\n"
        f"• Отслеживайте статус командой /track\n\n"
        f"*Для фотосетов:*\n"
        f"• После оплаты вы получите все фото\n"
        f"• Фото придут в личные сообщения"
    )
    await callback.message.edit_text(help_text, parse_mode="Markdown", reply_markup=back_button())
    await callback.answer()

async def show_about(callback: types.CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    add_visit(callback.from_user.id, "about")
    about_text = (
        f"{EMOJI['info']} *О нас*\n\n"
        f"Маркетплейс интимных сокровищ — уникальное место, где можно приобрести женское нижнее бельё с историей. "
        f"Каждое изделие хранит тепло и ауру своей владелицы, создавая особую связь.\n\n"
        f"{EMOJI['delivery']} *Доставка:* по всему миру, 1-3 дня.\n"
        f"{EMOJI['payment']} *Оплата:* Stars и TON.\n"
        f"{EMOJI['digital']} *Фотосеты:* мгновенная выдача.\n"
        f"{EMOJI['support']} *Поддержка:* всегда на связи, /support."
    )
    await callback.message.edit_text(about_text, parse_mode="Markdown", reply_markup=back_button())
    await callback.answer()

def back_button():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    return builder.as_markup()

async def back_to_main(callback: types.CallbackQuery, state: FSMContext = None):
    await cmd_start(callback.message, state)
    await callback.answer()

def register_handlers(dp):
    dp.message.register(cmd_start, Command("start"))
    dp.callback_query.register(go_to_catalog, lambda c: c.data == "go_to_catalog")
    dp.callback_query.register(go_to_support, lambda c: c.data == "go_to_support")
    dp.callback_query.register(go_to_track, lambda c: c.data == "go_to_track")
    dp.callback_query.register(show_help, lambda c: c.data == "show_help")
    dp.callback_query.register(show_about, lambda c: c.data == "show_about")
    dp.callback_query.register(back_to_main, lambda c: c.data == "back_to_main")