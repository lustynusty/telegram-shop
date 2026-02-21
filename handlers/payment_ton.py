# handlers/payment_ton.py
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
from config import TON_WALLET, ADMIN_CHAT_ID, PLACEHOLDER_IMAGE_ID
from database import get_product, get_user, create_order, update_order_status, get_product_images, mark_product_sold_out, check_product_available
from utils.ton_api import check_transaction
from handlers.delivery import DeliveryStates
from constants import EMOJI

class TONPaymentStates(StatesGroup):
    waiting_for_payment = State()

def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['catalog']} Каталог", callback_data="go_to_catalog")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

async def buy_ton(callback: types.CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[1])
    if not check_product_available(pid):
        await callback.answer(f"{EMOJI['warning']} Товар закончился")
        return
    prod = get_product(pid)
    if not prod:
        await callback.answer(f"{EMOJI['error']} Товар не найден")
        return
    (prod_id, name, desc, price_stars, price_ton, ptype,
     preview_image, in_stock, sold_count, cat_id, cat_name) = prod
    if not price_ton:
        await callback.answer(f"{EMOJI['warning']} Нельзя купить за TON")
        return
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start")
        return
    uid = user[0]
    order_id, tracking = create_order(uid, prod_id, "ton", payment_details={})
    comment = f"order_{order_id}"
    images = get_product_images(prod_id) if ptype=="digital" else []
    await state.set_state(TONPaymentStates.waiting_for_payment)
    await state.update_data(product_id=prod_id, order_id=order_id, expected_amount=price_ton,
                            comment=comment, ptype=ptype, file_id=(images[0][1] if images else None),
                            product_name=name, cat_id=cat_id)
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['ton']} Я оплатил", callback_data="check_ton_payment")
    builder.button(text=f"{EMOJI['cancel']} Отмена", callback_data="cancel_ton_payment")
    builder.adjust(1)
    type_name = "Фотосет" if ptype=="digital" else "Бельё"
    type_icon = EMOJI['digital'] if ptype=="digital" else EMOJI['physical']
    if ptype=="digital" and images:
        await callback.message.delete()
        await callback.message.answer_photo(photo=images[0][1],
            caption=f"{type_icon} *{name}*\n{desc}\n📸 Всего фото: {len(images)}\nЦена: {price_ton}{EMOJI['ton']}",
            parse_mode="Markdown", reply_markup=builder.as_markup(), has_spoiler=True)
    elif ptype=="physical" and preview_image:
        await callback.message.delete()
        await callback.message.answer_photo(photo=preview_image,
            caption=f"{type_icon} *{name}*\n{desc}\nЦена: {price_ton}{EMOJI['ton']}",
            parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(
            f"{type_icon} *{name}*\n{desc}\nЦена: {price_ton}{EMOJI['ton']}",
            parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

async def check_ton_payment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await callback.answer("Сессия истекла")
        await state.clear()
        return
    order_id = data["order_id"]
    expected = data["expected_amount"]
    comment = data["comment"]
    ptype = data["ptype"]
    file_id = data.get("file_id")
    product_name = data["product_name"]
    cat_id = data["cat_id"]
    await callback.message.edit_text(f"{EMOJI['wait']} Проверяем...")
    found = await check_transaction(comment, expected)
    if found:
        update_order_status(order_id, "paid")
        await callback.bot.send_message(ADMIN_CHAT_ID,
            f"{EMOJI['success']} *Новый заказ (TON)*\nТовар: {product_name}\nЗаказ: {order_id}",
            parse_mode="Markdown")
        if ptype == "digital":
            images = get_product_images(data["product_id"])
            if images:
                await callback.message.answer(f"{EMOJI['success']} *Оплачено!* Ваш фотосет:")
                for img in images:
                    await callback.message.answer_photo(img[1])
                    await asyncio.sleep(0.5)
            else:
                await callback.message.answer(f"{EMOJI['success']} *Оплачено!* Ссылка на скачивание будет позже.")
            await state.clear()
        else:
            mark_product_sold_out(data["product_id"])
            await callback.message.answer(
                f"{EMOJI['success']} *Оплачено!* Номер заказа: {order_id}\nУкажите адрес доставки для белья:",
                parse_mode="Markdown")
            await state.set_state(DeliveryStates.waiting_for_address)
            await state.update_data(order_id=order_id)
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text=f"{EMOJI['wait']} Проверить ещё", callback_data="check_ton_payment")
        kb.button(text=f"{EMOJI['cancel']} Отмена", callback_data="cancel_ton_payment")
        await callback.message.edit_text(
            f"{EMOJI['warning']} Платёж не найден. Убедитесь, что вы отправили {expected} TON с комментарием `{comment}`.",
            parse_mode="Markdown", reply_markup=kb.as_markup())
    await callback.answer()

async def cancel_ton_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{EMOJI['cancel']} Оплата отменена.")
    await callback.answer()

def register_handlers(dp):
    dp.callback_query.register(buy_ton, lambda c: c.data.startswith("buyton_"))
    dp.callback_query.register(check_ton_payment, lambda c: c.data == "check_ton_payment")
    dp.callback_query.register(cancel_ton_payment, lambda c: c.data == "cancel_ton_payment")