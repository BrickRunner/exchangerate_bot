from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_settings
from api import fetch_all_rates


def main_menu():
    """Создание главного меню"""
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Курсы валют сейчас")],
            [KeyboardButton(text="📉 Пороговые значения")],
            [KeyboardButton(text="📈 Статистика")],
            [KeyboardButton(text="⚙ Настройки")]
        ],
        resize_keyboard=True
    )
    return kb


def settings_menu():
    """Создание меню настроек"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Валюты", callback_data="set_currencies")],
        [InlineKeyboardButton(text="⏰ Время", callback_data="set_time")],
        [InlineKeyboardButton(text="📅 Дни", callback_data="set_days")],
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="set_timezone")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")]
    ])


def thresholds_menu():
    """Создание меню пороговых значений"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить порог", callback_data="add_threshold"),
         InlineKeyboardButton(text="➖ Удалить порог", callback_data="del_thresholds")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


async def build_currencies_kb(selected: list):
    """Создание клавиатуры для выбора валют"""
    kb = []
    row = []
    cnt = 0
    all_data = await fetch_all_rates()
    all_codes = sorted(all_data["rates"].keys())
    
    for c in all_codes:
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


async def build_threshold_currency_kb(user_id: int):
    """Создание клавиатуры для выбора валюты порога"""
    row = await get_settings(user_id)
    selected_currencies = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    kb = []
    row_buttons = []
    
    for idx, c in enumerate(selected_currencies, 1):
        row_buttons.append(InlineKeyboardButton(text=c, callback_data=f"th_curr:{c}"))
        if idx % 3 == 0:
            kb.append(row_buttons)
            row_buttons = []
    
    if row_buttons:
        kb.append(row_buttons)
    
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_days_kb(selected: list):
    """Создание клавиатуры для выбора дней"""
    days_map = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}
    kb = []
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
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_timezone_kb():
    """Создание клавиатуры для выбора часового пояса"""
    kb_rows = []
    row = []
    cnt = 0
    
    for tz in range(-12, 13):
        row.append(InlineKeyboardButton(text=f"GMT{tz:+}", callback_data=f"set_tz:{tz}"))
        cnt += 1
        if cnt % 4 == 0:
            kb_rows.append(row)
            row = []
    
    if row:
        kb_rows.append(row)
    
    kb_rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_settings")])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


def build_stats_currencies_kb(currencies: list):
    """Создание клавиатуры для выбора валюты статистики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=c, callback_data=f"stats_curr:{c}")] for c in currencies
    ] + [[InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]])


def build_stats_period_kb(currency: str):
    """Создание клавиатуры для выбора периода статистики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Неделя", callback_data=f"stats_period:{currency}:7")],
        [InlineKeyboardButton(text="🗓 Месяц", callback_data=f"stats_period:{currency}:30")],
        [InlineKeyboardButton(text="📆 Год", callback_data=f"stats_period:{currency}:365")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="stats")]
    ])