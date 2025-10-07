import aiosqlite
from config import DB_PATH


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS thresholds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            currency TEXT,
            value REAL,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            currencies TEXT DEFAULT 'USD,EUR',
            notify_time TEXT DEFAULT '08:00',
            days TEXT DEFAULT '1,2,3,4,5',
            timezone TEXT DEFAULT '0',
            last_sent_date TEXT
        );
        """)
        await db.commit()


async def get_settings(user_id: int):
    """Получение настроек пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, currencies, notify_time, days, timezone, last_sent_date FROM user_settings WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return await get_settings(user_id)
        return row


async def update_settings(user_id: int, field: str, value: str):
    """Обновление настроек пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE user_settings SET {field}=? WHERE user_id=?", (value, user_id))
        await db.commit()


async def get_user_thresholds(user_id: int):
    """Получение пороговых значений пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, currency, value, comment FROM thresholds WHERE user_id=?",
            (user_id,)
        )
        return await cur.fetchall()


async def add_threshold(user_id: int, currency: str, value: float, comment: str):
    """Добавление порогового значения"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO thresholds (user_id, currency, value, comment) VALUES (?,?,?,?)",
            (user_id, currency, value, comment)
        )
        await db.commit()


async def delete_threshold(threshold_id: int, user_id: int):
    """Удаление порогового значения"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT currency, value FROM thresholds WHERE id=? AND user_id=?",
            (threshold_id, user_id)
        )
        row = await cur.fetchone()
        if not row:
            return None
        currency, value = row
        await db.execute("DELETE FROM thresholds WHERE id=? AND user_id=?", (threshold_id, user_id))
        await db.commit()
        return (currency, value)


async def get_all_users_settings():
    """Получение настроек всех пользователей для scheduler"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, currencies, notify_time, days, timezone, last_sent_date FROM user_settings"
        )
        return await cur.fetchall()


async def update_last_sent_date(user_id: int, date_iso: str):
    """Обновление даты последней отправки"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_settings SET last_sent_date=? WHERE user_id=?", (date_iso, user_id))
        await db.commit()
