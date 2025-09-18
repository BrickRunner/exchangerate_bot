# bot.py
import os
import asyncio
import aiosqlite
from datetime import datetime, timedelta, date
import aiohttp
from aiogram.exceptions import TelegramBadRequest
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "rates.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

# Символы валют (можно дополнять)
CURRENCY_SYMBOLS = {
    "RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥", "GBP": "£",
    "JPY": "¥", "CHF": "₣", "KZT": "₸", "TRY": "₺", "INR": "₹",
    "KRW": "₩", "AED": "د.إ", "UZS": "so'm", "BYN": "Br", "PLN": "zł",
    "CZK": "Kč", "SEK": "kr", "NOK": "kr", "DKK": "kr", "HUF": "Ft",
    "BGN": "лв", "RON": "lei", "BRL": "R$", "MXN": "$", "CAD": "$",
    "AUD": "$", "NZD": "$", "HKD": "$", "SGD": "$", "ZAR": "R"
}

# --- DB init ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # last_sent_date хранит ISO-дату (YYYY-MM-DD), чтобы не слать дважды в тот же день
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            currencies TEXT DEFAULT 'USD,EUR',
            notify_time TEXT DEFAULT '09:00',
            days TEXT DEFAULT '1,2,3,4,5',
            timezone INTEGER DEFAULT 3,
            last_sent_date TEXT DEFAULT ''
        );
        """)
        await db.commit()

# Получить настройки (возвращает tuple в порядке колонок)
async def get_settings(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, currencies, notify_time, days, timezone, last_sent_date FROM user_settings WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return await get_settings(user_id)
        return row

# Обновить поле и не забыть commit
async def update_settings(user_id: int, field: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE user_settings SET {field}=? WHERE user_id=?", (value, user_id))
        await db.commit()

# --- Fetch rates from CBR ---
async def fetch_rates(currencies: list):
    """Возвращает dict: {'base': 'RUB', 'date': 'DD.MM', 'rates': {CUR: value or None}}"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CBR_URL, timeout=20) as resp:
                data = await resp.json(content_type=None)
                # дата API в UTC+? — но мы используем локальную временную метку пользователя позже
                date_str = datetime.strptime(data["Date"], "%Y-%m-%dT%H:%M:%S%z").strftime("%d.%m")
                rates = {}
                for c in currencies:
                    v = data["Valute"].get(c)
                    rates[c] = v["Value"] if v else None
                return {"base": "RUB", "date": date_str, "rates": rates}
    except Exception:
        # при ошибке возвращаем пустые значения, чтобы бот не падал
        now = datetime.utcnow()
        return {"base": "RUB", "date": now.strftime("%d.%m"), "rates": {c: None for c in currencies}}

# --- Format message ---
def format_rates_for_user(base: str, dt: datetime, rates: dict) -> str:
    """
    base: 'RUB'
    dt: datetime object (локализованный по часовому поясу пользователя)
    rates: dict {CUR: value or None}
    """
    lines = [f"📊 Курсы валют на {dt.strftime('%d.%m %H:%M')} (локальное время)", ""]
    base_symbol = CURRENCY_SYMBOLS.get(base, base)
    for c, r in rates.items():
        symbol = CURRENCY_SYMBOLS.get(c, c)
        value = f"{r:.2f}" if (r is not None) else "—"
        lines.append(f"{c} ({symbol}): {value} {base_symbol}")
    lines.append("")
    return "\n".join(lines)

# --- Keyboards ---
def main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Курсы валют сейчас")],
            [KeyboardButton(text="⚙ Настройки")]
        ], resize_keyboard=True
    )
    return kb

def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Валюты", callback_data="set_currencies")],
        [InlineKeyboardButton(text="⏰ Время", callback_data="set_time")],
        [InlineKeyboardButton(text="📅 Дни", callback_data="set_days")],
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="set_timezone")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")]
    ])

# Helper: build currencies keyboard with marks according to selected list
def build_currencies_kb(selected: list):
    kb = []
    # разбиваем на строки по 3 валюты чтобы аккуратно выглядело
    row = []
    cnt = 0
    for c in CURRENCY_SYMBOLS.keys():
        mark = "✅" if c in selected else "❌"
        row.append(InlineKeyboardButton(text=f"{mark} {c}", callback_data=f"toggle_curr:{c}"))
        cnt += 1
        if cnt % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- Handlers ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await get_settings(m.from_user.id)  # ensure row exists
    await m.answer("Привет! Я бот курсов по данным ЦБ РФ. Выберите действие:", reply_markup=main_menu())

@dp.message(lambda message: message.text == "📊 Курсы валют сейчас")
async def handle_send_now(m: types.Message):
    row = await get_settings(m.from_user.id)
    currencies = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    tz = int(row[4] or 0)

    res = await fetch_rates(currencies)

    # локальное время пользователя (UTC + tz hours)
    user_now = datetime.utcnow() + timedelta(hours=tz)
    # используем user_now как datetime для отображения
    text = format_rates_for_user(res.get("base", "RUB"), user_now, res.get("rates", {}))
    await m.answer(text)

@dp.message(lambda message: message.text == "⚙ Настройки")
async def handle_settings(m: types.Message):
    await m.answer("⚙ Настройки — выберите раздел:", reply_markup=settings_menu())

# --- Currencies selection ---
@dp.callback_query(lambda c: c.data == "set_currencies")
async def cb_set_currencies(cb: types.CallbackQuery):
    row = await get_settings(cb.from_user.id)
    selected = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    kb = build_currencies_kb(selected)
    try:
        await cb.message.edit_text("Выберите валюты (нажмите, чтобы переключить):", reply_markup=kb)
    except TelegramBadRequest as e:
        # ignore "message is not modified"
        if "message is not modified" not in str(e):
            raise
    await cb.answer()

@dp.callback_query(lambda c: c.data.startswith("toggle_curr:"))
async def cb_toggle_curr(cb: types.CallbackQuery):
    cur = cb.data.split(":", 1)[1]
    row = await get_settings(cb.from_user.id)
    selected = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    if cur in selected:
        selected.remove(cur)
    else:
        selected.append(cur)
    # если пустой список — не сохраняем пустоту, сохраняем дефолт
    if selected:
        await update_settings(cb.from_user.id, "currencies", ",".join(selected))
    else:
        await update_settings(cb.from_user.id, "currencies", "")
    # показать обновлённую панель (новые галочки)
    await cb_set_currencies(cb)

# --- Time selection ---
@dp.callback_query(lambda c: c.data == "set_time")
async def cb_set_time(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")]])
    try:
        await cb.message.edit_text("Введите время рассылки в формате ЧЧ:ММ (24ч), например 09:00", reply_markup=kb)
    except TelegramBadRequest:
        pass
    await cb.answer()

@dp.message(lambda m: len(m.text) == 5 and m.text.count(":") == 1 and m.text.replace(":","").isdigit())
async def msg_set_time(m: types.Message):
    # проверка формата
    hh, mm = m.text.split(":")
    try:
        hh_i = int(hh); mm_i = int(mm)
        if not (0 <= hh_i < 24 and 0 <= mm_i < 60):
            raise ValueError
    except Exception:
        await m.answer("Неверный формат времени. Используйте ЧЧ:ММ (00:00 - 23:59).", reply_markup=main_menu())
        return
    await update_settings(m.from_user.id, "notify_time", m.text)
    await m.answer(f"✅ Время уведомлений обновлено: {m.text}", reply_markup=main_menu())

# --- Days selection ---
@dp.callback_query(lambda c: c.data == "set_days")
async def cb_set_days(cb: types.CallbackQuery):
    row = await get_settings(cb.from_user.id)
    selected = [d for d in (row[3] or "1,2,3,4,5").split(",") if d.strip()]
    days_map = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}
    kb = []
    # по 4 в строке
    row_buttons = []
    cnt = 0
    for i in range(1, 8):
        mark = "✅" if str(i) in selected else "❌"
        row_buttons.append(InlineKeyboardButton(text=f"{mark} {days_map[i]}", callback_data=f"toggle_day:{i}"))
        cnt += 1
        if cnt % 3 == 0:
            kb.append(row_buttons)
            row_buttons = []
    if row_buttons:
        kb.append(row_buttons)
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")])
    try:
        await cb.message.edit_text("Выберите дни рассылки (нажмите чтобы переключить):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except TelegramBadRequest:
        pass
    await cb.answer()

@dp.callback_query(lambda c: c.data.startswith("toggle_day:"))
async def cb_toggle_day(cb: types.CallbackQuery):
    day = cb.data.split(":", 1)[1]
    row = await get_settings(cb.from_user.id)
    selected = [d for d in (row[3] or "1,2,3,4,5").split(",") if d.strip()]
    if day in selected:
        selected.remove(day)
    else:
        selected.append(day)
    # сортируем дни
    selected_sorted = sorted(set(int(x) for x in selected)) if selected else []
    selected_str = ",".join(str(x) for x in selected_sorted)
    if selected_str == "":
        selected_str = ""
    await update_settings(cb.from_user.id, "days", selected_str)
    await cb_set_days(cb)

# --- Timezone selection ---
@dp.callback_query(lambda c: c.data == "set_timezone")
async def cb_set_timezone(cb: types.CallbackQuery):
    kb_rows = []
    row = []
    cnt = 0
    for tz in range(-12, 13):
        row.append(InlineKeyboardButton(text=f"GMT{tz:+}", callback_data=f"set_tz:{tz}"))
        cnt += 1
        if cnt % 4 == 0:
            kb_rows.append(row); row = []
    if row: kb_rows.append(row)
    kb_rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")])
    try:
        await cb.message.edit_text("Выберите часовой пояс (UTC offset):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    except TelegramBadRequest:
        pass
    await cb.answer()

@dp.callback_query(lambda c: c.data.startswith("set_tz:"))
async def cb_set_tz(cb: types.CallbackQuery):
    tz = int(cb.data.split(":", 1)[1])
    await update_settings(cb.from_user.id, "timezone", str(tz))
    # подтверждаем пользователю и возвращаем в меню настройки (с обновлённой клавиатурой)
    try:
        await cb.answer(f"🌍 Часовой пояс установлен: GMT{tz:+}")
    except Exception:
        pass
    await cb.message.edit_text("⚙ Настройки:", reply_markup=settings_menu())

# --- Back button ---
@dp.callback_query(lambda c: c.data == "back_settings")
async def cb_back(cb: types.CallbackQuery):
    try:
        await cb.message.edit_text("⚙ Настройки:", reply_markup=settings_menu())
    except TelegramBadRequest:
        pass
    await cb.answer()

# --- Scheduler loop (заменяет aioschedule) ---
async def scheduler_loop():
    """
    Раз в 30 секунд проверяем всех пользователей, у которых сейчас локальное время
    совпадает с настроенным notify_time и день недели включён, и если для них
    ещё сегодня не отправлялось, отправляем.
    """
    while True:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id, currencies, notify_time, days, timezone, last_sent_date FROM user_settings")
                rows = await cur.fetchall()
                for row in rows:
                    user_id, currencies, notify_time, days, tz, last_sent = row
                    if not notify_time:
                        continue
                    # parse
                    try:
                        hh, mm = map(int, notify_time.split(":"))
                    except Exception:
                        continue
                    tz = int(tz or 0)
                    # локальное время пользователя
                    user_now = datetime.utcnow() + timedelta(hours=tz)
                    # сравниваем часы и минуты
                    if user_now.hour == hh and user_now.minute == mm:
                        # проверяем день недели
                        daynum = user_now.isoweekday()  # 1..7
                        allowed_days = [int(d) for d in (days or "").split(",") if d.strip().isdigit()] or [1,2,3,4,5]
                        if daynum in allowed_days:
                            today_iso = (user_now.date()).isoformat()
                            if last_sent == today_iso:
                                # уже отправляли сегодня
                                continue
                            # готовим и отправляем
                            currs = [c.strip().upper() for c in (currencies or "USD,EUR").split(",") if c.strip()]
                            res = await fetch_rates(currs)
                            # используем user_now как локальное время для вывода
                            text = format_rates_for_user(res.get("base","RUB"), user_now, res.get("rates", {}))
                            try:
                                await bot.send_message(user_id, text)
                            except Exception:
                                # пользователь мог запретить сообщения, не ломаем цикл
                                pass
                            # пометим, что отправили сегодня
                            await db.execute("UPDATE user_settings SET last_sent_date=? WHERE user_id=?", (today_iso, user_id))
                            await db.commit()
            # спим небольшое время
            await asyncio.sleep(30)
        except Exception:
            # если что-то упало в цикле, не убиваем loop — подождём и повторим
            await asyncio.sleep(5)

# --- Run ---
async def main():
    await init_db()
    # Запускаем scheduler параллельно
    asyncio.create_task(scheduler_loop())
    # Старт бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
