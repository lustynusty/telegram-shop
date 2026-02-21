# handlers/payment_stars.py
from aiogram import types, F
from aiogram.types import LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
from config import PROVIDER_TOKEN_STARS, ADMIN_CHAT_ID, PLACEHOLDER_IMAGE_ID
from database import get_product, get_user, create_order, update_order_status, get_product_images, mark_product_sold_out, check_product_available
from handlers.delivery import DeliveryStates
from constants import EMOJI

class StarsPaymentStates(StatesGroup):
    waiting_for_payment = State()

def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['catalog']} Каталог", callback_data="go_to_catalog")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

async def buy_stars(callback: types.CallbackQuery, state: FSMContext):
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
    if not price_stars:
        await callback.answer(f"{EMOJI['warning']} Нельзя купить за Stars")
        return
    images = get_product_images(prod_id) if ptype=="digital" else []
    await state.set_state(StarsPaymentStates.waiting_for_payment)
    await state.update_data(product_id=prod_id, product_name=name, product_type=ptype,
                            images=images, price_stars=price_stars, cat_id=cat_id)
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['stars']} Оплатить {price_stars} Stars", callback_data=f"send_invoice_{prod_id}")
    builder.button(text=f"{EMOJI['cancel']} Отмена", callback_data="cancel_stars_payment")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(1)
    type_name = "Фотосет" if ptype=="digital" else "Бельё"
    type_icon = EMOJI['digital'] if ptype=="digital" else EMOJI['physical']
    if ptype=="digital" and images:
        await callback.message.delete()
        await callback.message.answer_photo(photo=images[0][1],
            caption=f"{type_icon} *{name}*\n{desc}\n📸 Всего фото: {len(images)}\nЦена: {price_stars}{EMOJI['stars']}",
            parse_mode="Markdown", reply_markup=builder.as_markup(), has_spoiler=True)
    elif ptype=="physical" and preview_image:
        await callback.message.delete()
        await callback.message.answer_photo(photo=preview_image,
            caption=f"{type_icon} *{name}*\n{desc}\nЦена: {price_stars}{EMOJI['stars']}",
            parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(
            f"{type_icon} *{name}*\n{desc}\nЦена: {price_stars}{EMOJI['stars']}",
            parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

async def send_invoice(callback: types.CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[-1])
    if not check_product_available(pid):
        await callback.message.answer(f"{EMOJI['warning']} Товар закончился")
        await state.clear()
        return
    prod = get_product(pid)
    if not prod:
        await callback.answer(f"{EMOJI['error']} Товар не найден")
        return
    (prod_id, name, desc, price_stars, price_ton, ptype,
     preview_image, in_stock, sold_count, cat_id, cat_name) = prod
    try:
        await callback.message.delete()
        if PLACEHOLDER_IMAGE_ID:
            await callback.message.answer_photo(PLACEHOLDER_IMAGE_ID,
                caption=f"{EMOJI['info']} *Сейчас откроется окно оплаты*\nТовар: {name}\nЦена: {price_stars}{EMOJI['stars']}",
                parse_mode="Markdown")
            await asyncio.sleep(1)
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=name,
            description=f"{desc[:150]}...\n\n{'Бельё' if ptype=='physical' else 'Фотосет'}",
            payload=str(pid),
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=name, amount=price_stars)],
            start_parameter="create_invoice_stars"
        )
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"{EMOJI['error']} Ошибка: {e}")
        await callback.answer()

async def cancel_stars_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(f"{EMOJI['cancel']} Оплата отменена.", reply_markup=main_menu_keyboard())
    await callback.answer()

async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

async def successful_payment_handler(message: types.Message, state: FSMContext):
    payload = message.successful_payment.invoice_payload
    pid = int(payload)
    user = get_user(message.from_user.id)
    prod = get_product(pid)
    if not user or not prod:
        await message.answer(f"{EMOJI['error']} Ошибка")
        return
    uid = user[0]
    (prod_id, name, desc, price_stars, price_ton, ptype,
     preview_image, in_stock, sold_count, cat_id, cat_name) = prod
    if not check_product_available(prod_id):
        await message.answer(f"{EMOJI['warning']} Товар закончился во время оплаты, средства вернутся.")
        return
    order_id, tracking = create_order(uid, prod_id, "stars",
                                      payment_details={"telegram_payment_id": message.successful_payment.telegram_payment_charge_id})
    update_order_status(order_id, "paid")
    if ptype == "physical":
        mark_product_sold_out(prod_id)
    await message.bot.send_message(ADMIN_CHAT_ID,
        f"{EMOJI['success']} *Новый заказ (Stars)*\nТрек: `{tracking}`\nТовар: {name}\nПокупатель: @{message.from_user.username}",
        parse_mode="Markdown")
    if ptype == "digital":
        images = get_product_images(prod_id)
        if images:
            await message.answer(f"{EMOJI['success']} *Оплачено!* Ваш фотосет:")
            for img in images:
                await message.answer_photo(img[1])
                await asyncio.sleep(0.5)
        else:
            await message.answer(f"{EMOJI['success']} *Оплачено!* Ссылка на скачивание будет позже.")
    else:
        await message.answer(
            f"{EMOJI['success']} *Оплачено!* Номер заказа: `{tracking}`\nУкажите адрес доставки для белья:",
            parse_mode="Markdown")
        await state.set_state(DeliveryStates.waiting_for_address)
        await state.update_data(order_id=order_id, tracking=tracking)
    await state.clear()

def register_handlers(dp):
    dp.callback_query.register(buy_stars, lambda c: c.data.startswith("buystars_"))
    dp.callback_query.register(send_invoice, lambda c: c.data.startswith("send_invoice_"))
    dp.callback_query.register(cancel_stars_payment, lambda c: c.data == "cancel_stars_payment")
    dp.pre_checkout_query.register(pre_checkout_query_handler)
    dp.message.register(successful_payment_handler, F.content_type == ContentType.SUCCESSFUL_PAYMENT)