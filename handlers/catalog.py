# handlers/catalog.py
from aiogram import types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_all_categories, get_products_by_category_and_type, get_product, get_product_images
from constants import EMOJI

async def cmd_catalog(message: types.Message):
    categories = get_all_categories(show_hidden=False)
    if not categories:
        await message.answer(f"{EMOJI['warning']} Каталог пуст.")
        return
    text = f"{EMOJI['catalog']} *Категории*\n{'─'*20}\nВыберите девушку:"
    builder = InlineKeyboardBuilder()
    for cat_id, name, desc, icon in categories:
        builder.button(text=f"{icon} {name}", callback_data=f"category_{cat_id}")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

async def show_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    from database import get_category
    cat = get_category(cat_id)
    if not cat:
        await callback.answer(f"{EMOJI['error']} Категория не найдена")
        return
    # cat = (id, name, description, icon)
    text = (
        f"{cat[3]} *{cat[1]}*\n"
        f"_{cat[2]}_\n"  # описание категории
        f"{'─'*20}\n"
        f"Выберите тип:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['physical']} Бельё", callback_data=f"subcat_{cat_id}_physical")
    builder.button(text=f"{EMOJI['digital']} Фотосет", callback_data=f"subcat_{cat_id}_digital")
    builder.button(text=f"{EMOJI['back']} Назад", callback_data="back_to_categories")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

async def show_subcategory(callback: types.CallbackQuery):
    _, cat_id, ptype = callback.data.split("_")
    cat_id = int(cat_id)
    from database import get_category
    cat = get_category(cat_id)
    if not cat:
        await callback.answer(f"{EMOJI['error']} Категория не найдена")
        return
    products = get_products_by_category_and_type(cat_id, ptype, in_stock_only=True)
    if not products:
        await callback.answer(f"{EMOJI['info']} Нет товаров в наличии")
        return
    type_name = "Бельё" if ptype=="physical" else "Фотосет"
    type_icon = EMOJI['physical'] if ptype=="physical" else EMOJI['digital']
    text = f"{cat[3]} *{cat[1]}* | {type_icon} *{type_name}*\n{'─'*20}\nВыберите товар:"
    builder = InlineKeyboardBuilder()
    for prod in products:
        pid, name, desc, p_stars, p_ton, p_type, prev_img = prod
        btn = f"{name} | {p_stars}{EMOJI['stars']} / {p_ton}{EMOJI['ton']}"
        builder.button(text=btn, callback_data=f"product_{pid}")
    builder.button(text=f"{EMOJI['back']} Назад", callback_data=f"category_{cat_id}")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(1)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

async def product_callback(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    prod = get_product(pid)
    if not prod:
        await callback.answer(f"{EMOJI['error']} Товар не найден")
        return
    (prod_id, name, desc, price_stars, price_ton, ptype,
     preview_image, in_stock, sold_count, cat_id, cat_name) = prod
    if not in_stock:
        await callback.answer(f"{EMOJI['warning']} Товар закончился")
        return
    images = get_product_images(pid) if ptype=="digital" else []
    photo_info = f"\n📸 *Фото:* {len(images)} шт." if ptype=="digital" else ""
    type_icon = EMOJI['digital'] if ptype=="digital" else EMOJI['physical']
    type_name = "Фотосет" if ptype=="digital" else "Бельё"
    text = (
        f"{type_icon} *{name}*\n"
        f"{'─'*20}\n{desc}{photo_info}\n\n"
        f"{EMOJI['payment']} *Цена:*\n• {price_stars}{EMOJI['stars']}\n• {price_ton}{EMOJI['ton']}"
    )
    builder = InlineKeyboardBuilder()
    if price_stars:
        builder.button(text=f"{EMOJI['stars']} Купить за {price_stars} Stars", callback_data=f"buystars_{pid}")
    if price_ton:
        builder.button(text=f"{EMOJI['ton']} Купить за {price_ton} TON", callback_data=f"buyton_{pid}")
    builder.button(text=f"{EMOJI['back']} Назад", callback_data=f"subcat_{cat_id}_{ptype}")
    builder.button(text=f"{EMOJI['home']} Главное меню", callback_data="back_to_main")
    builder.adjust(1)
    if ptype=="physical" and preview_image:
        await callback.message.delete()
        await callback.message.answer_photo(photo=preview_image, caption=text,
                                            parse_mode="Markdown", reply_markup=builder.as_markup())
    elif ptype=="digital" and images:
        await callback.message.delete()
        await callback.message.answer_photo(photo=images[0][1], caption=text,
                                            parse_mode="Markdown", reply_markup=builder.as_markup(),
                                            has_spoiler=True)
    else:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

async def back_to_categories(callback: types.CallbackQuery):
    await cmd_catalog(callback.message)
    await callback.answer()

def register_handlers(dp):
    dp.message.register(cmd_catalog, Command("catalog"))
    dp.callback_query.register(show_category, lambda c: c.data.startswith("category_"))
    dp.callback_query.register(show_subcategory, lambda c: c.data.startswith("subcat_"))
    dp.callback_query.register(product_callback, lambda c: c.data.startswith("product_"))
    dp.callback_query.register(back_to_categories, lambda c: c.data == "back_to_categories")