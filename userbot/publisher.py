import logging
from telethon import Button
from telethon.tl.types import InputMediaPhotoExternal
from config import PRIVATE_CHANNEL_ID

logger = logging.getLogger(__name__)


async def publish_announcement(client, description, price, photos):
    """
    Публикует объявление в приватный канал.

    :param client: Telethon client
    :param description: Текст описания объявления
    :param price: Цена объявления
    :param photos: Список путей к фотографиям
    """
    try:
        message_text = f"{description}\n\nЦена: {price}"

        # Отправка фото или текстового сообщения
        if photos:
            media_group = [InputMediaPhotoExternal(file) for file in photos]
            sent_messages = await client.send_file(
                PRIVATE_CHANNEL_ID,
                media_group,
                caption=message_text
            )
            message_ids = [msg.id for msg in sent_messages]
            logger.info(f"Отправлено объявление с фото, message_ids: {message_ids}")
        else:
            sent_message = await client.send_message(PRIVATE_CHANNEL_ID, message_text)
            message_id = sent_message.id
            logger.info(f"Отправлено текстовое объявление, message_id: {message_id}")

        return True

    except Exception as e:
        logger.error(f"Ошибка при публикации объявления: {e}")
        return False
