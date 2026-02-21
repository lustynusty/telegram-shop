# utils/image_processor.py
from PIL import Image, ImageDraw, ImageFont
import os
import tempfile
from aiogram.types import FSInputFile
import logging
from config import ADMIN_CHAT_ID

async def create_watermarked_preview(image_file_id, bot, text="ТОВАР БУДЕТ ДОСТУПЕН ПОСЛЕ ОПЛАТЫ"):
    """
    Создаёт превью с водяным знаком из полного изображения.
    Возвращает file_id нового изображения или None.
    """
    try:
        file = await bot.get_file(image_file_id)
        file_path = file.file_path
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_in:
            await bot.download_file(file_path, tmp_in.name)
            input_path = tmp_in.name
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_out:
            output_path = tmp_out.name

        img = Image.open(input_path)
        img_wm = img.copy()
        draw = ImageDraw.Draw(img_wm)

        # Пытаемся загрузить шрифт
        try:
            font_path = "C:/Windows/Fonts/arial.ttf"
            if not os.path.exists(font_path):
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font = ImageFont.truetype(font_path, size=img.height // 15)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img.width - text_w) // 2
        y = (img.height - text_h) // 2
        padding = 20
        draw.rectangle([x-padding, y-padding, x+text_w+padding, y+text_h+padding], fill=(0,0,0,180))
        draw.text((x, y), text, fill=(255,255,255), font=font)
        img_wm.save(output_path, 'JPEG', quality=85)

        with open(output_path, 'rb') as photo:
            msg = await bot.send_photo(ADMIN_CHAT_ID, FSInputFile(output_path))
            new_file_id = msg.photo[-1].file_id
            await msg.delete()

        os.unlink(input_path)
        os.unlink(output_path)
        return new_file_id
    except Exception as e:
        logging.error(f"Ошибка создания водяного знака: {e}")
        return None