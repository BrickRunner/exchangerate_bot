# bot.py
import os
import asyncio
import aiosqlite
from datetime import datetime, date, timedelta
from typing import List, Optional

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "rates.db")
DEFAULT_CURRENCIES = os.getenv("DEFAULT_CURRENCIES", "USD,EUR").split(",")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

API_URL = "https://api.exchangerate.host/latest"

# --- Database helpers ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curr TEXT NOT NULL,
            rate REAL NOT NULL,
            base TEXT NOT NULL,
            date TEXT NOT NULL
        );
        """)
        await db.commit()

async def save_rates(rates: dict, base: str, dt: str):
    async with aiosqlite.connect(DB_PATH) as db:
        for curr, rate in rates.items():
            await db.execute(
                "INSERT INTO rates (curr, rate, base, date) VALUES (?, ?, ?, ?)",
                (curr, rate, base, dt)
            )
        await db.commit()

async def get_rates_between(curr: str, start_date: date, end_date: date) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT date, rate FROM rates WHERE curr = ? AND date BETWEEN ? AND ? ORDER BY date ASC",
            (curr, start_date.isoformat(), end_date.isoformat())
        )
        rows = await cur.fetchall()
        return rows

def compute_stats(rows: List[tuple]):
    if not rows:
        return None
    vals = [r for _, r in rows]
    avg = sum(vals) / len(vals)
    return {
        "count": len(vals),
        "avg": avg,
        "min": min(vals),
        "max": max(vals),
        "first": vals[0],
        "last": vals[-1],
        "change_percent": (vals[-1] - vals[0]) / vals[0] * 100 if vals[0] != 0 else None
    }

# --- Fetch rates ---
async def fetch_rates(currencies: List[str], base: str = "USD") -> dict:
    params = {"base": base, "symbols": ",".join(currencies)}
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params=params, timeout=20) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}")
            data = await resp.json()
            return {
                "base": data.get("base", base),
                "date": data.get("date", datetime.utcnow().date().isoformat()),
                "rates": data.get("rates", {})
            }

# --- Format message ---
def format_rates_message(base: str, dt: str, rates: dict) -> str:
    lines = [f"📊 Курсы валют за {dt} (base: {base})", ""]
    for c, r in rates.items():
        lines.append(f"{c}: {r:.6f}")
    lines.append("")
    lines.append("Команды: /stats week|month|year [CURR], /sendnow")
    return "\n".join(lines)

# --- Bot commands ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я шлю курсы валют и считаю статистику.\n"
        "Запрос статистики: /stats week|month|year [CURR]\n"
        "Получить курсы сейчас: /sendnow"
    )

@dp.message(Command("sendnow"))
async def cmd_sendnow(message: types.Message):
    currencies = [c.strip().upper() for c in DEFAULT_CURRENCIES if c.strip()]
    try:
        res = await fetch_rates(currencies, base="USD")
    except Exception as e:
        await message.answer(f"Ошибка при получении курса: {e}")
        return
    await save_rates(res["rates"], res["base"], res["date"])
    await message.answer(format_rates_message(res["base"], res["date"], res["rates"]))

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /stats week|month|year [CURR]")
        return
    period = parts[1].lower()
    if period not in ("week", "month", "year"):
        await message.answer("Период должен быть: week, month или year")
        return
    curr = parts[2].upper() if len(parts) >= 3 else DEFAULT_CURRENCIES[0].upper()

    today = datetime.utcnow().date()
    if period == "week":
        start = today - timedelta(days=7)
    elif period == "month":
        start = today - timedelta(days=30)
    else:
        start = today - timedelta(days=365)

    rows = await get_rates_between(curr, start, today)
    stats = compute_stats(rows)
    if not stats:
        await message.answer(f"Нет данных для {curr} за период {period}")
        return

    txt = (
        f"📈 Статистика для {curr} за {period} ({start} — {today}):\n"
        f"Записей: {stats['count']}\n"
        f"Среднее: {stats['avg']:.6f}\n"
        f"Min: {stats['min']:.6f}\n"
        f"Max: {stats['max']:.6f}\n"
        f"Первое значение: {stats['first']:.6f}\n"
        f"Последнее значение: {stats['last']:.6f}\n"
    )
    if stats['change_percent'] is not None:
        txt += f"Изменение: {stats['change_percent']:.3f}%\n"
    await message.answer(txt)

# --- Main ---
async def main():
    await init_db()
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import sys
    if sys.platform == "darwin":
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    asyncio.run(main())
