import aiosqlite
import asyncio
from datetime import datetime

#docker cp container_name:/app/data/announcements.db .


OLD_DB_PATH = "old_announcements.db"  # Путь к старой базе (без timestamp)
NEW_DB_PATH = "announcements.db"      # Путь к новой базе (с timestamp)

async def migrate_database():
    """Перенос данных из старой БД в новую и добавление timestamp для новых записей."""
    try:
        # Открываем обе базы
        async with aiosqlite.connect(OLD_DB_PATH) as old_db, aiosqlite.connect(NEW_DB_PATH) as new_db:
            old_cursor = await old_db.execute("SELECT id, user_id, username, description, price, photo_file_ids, message_ids FROM announcements")
            old_records = await old_cursor.fetchall()

            # Загружаем ID объявлений, которые уже есть в новой БД
            new_cursor = await new_db.execute("SELECT id FROM announcements")
            existing_ids = {row[0] for row in await new_cursor.fetchall()}

            count_inserted = 0

            for record in old_records:
                ann_id, user_id, username, description, price, photo_file_ids, message_ids = record
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Генерируем новый timestamp

                if ann_id not in existing_ids:
                    # Добавляем запись, если её нет в новой базе
                    await new_db.execute(
                        "INSERT INTO announcements (id, user_id, username, description, price, photo_file_ids, message_ids, timestamp) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (ann_id, user_id, username, description, price, photo_file_ids, message_ids, current_time),
                    )
                    count_inserted += 1

            await new_db.commit()  # Сохраняем изменения

        print(f"✅ Перенос завершен: добавлено {count_inserted} записей.")

    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")

# Запускаем миграцию
asyncio.run(migrate_database())
