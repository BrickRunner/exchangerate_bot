"""
Скрипт миграции для обновления часового пояса существующих пользователей с 0 на 3 (UTC+3)
Запустите этот скрипт один раз после обновления кода.
"""

import asyncio
import aiosqlite
from config import DB_PATH


async def migrate_timezones():
    """Миграция часовых поясов с 0 на 3 для существующих пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем всех пользователей с timezone = 0
        cursor = await db.execute(
            "SELECT user_id, timezone FROM user_settings WHERE timezone = '0'"
        )
        users = await cursor.fetchall()

        if not users:
            print("✅ Нет пользователей для миграции (все уже имеют корректный часовой пояс)")
            return

        print(f"🔄 Найдено пользователей с timezone=0: {len(users)}")

        # Обновляем timezone с 0 на 3
        await db.execute(
            "UPDATE user_settings SET timezone = '3' WHERE timezone = '0'"
        )
        await db.commit()

        print(f"✅ Обновлено пользователей: {len(users)}")
        print(f"   Часовой пояс изменен с UTC+0 на UTC+3 (Московское время)")

        # Показываем обновленных пользователей
        for user_id, old_tz in users:
            print(f"   - User ID: {user_id}")


async def main():
    """Главная функция миграции"""
    print("=" * 60)
    print("Миграция часовых поясов")
    print("=" * 60)
    print()

    try:
        await migrate_timezones()
        print()
        print("=" * 60)
        print("✅ Миграция завершена успешно!")
        print("=" * 60)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Ошибка миграции: {e}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(main())
