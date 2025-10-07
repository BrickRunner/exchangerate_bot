from datetime import datetime, timedelta
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import get_settings
from api import fetch_rates, fetch_rates_by_date
from utils import format_rates_for_user
from keyboards import main_menu
from states import DateForm


async def cmd_start(m: types.Message):
    """Обработка команды /start"""
    await get_settings(m.from_user.id)
    await m.answer("Привет! Я бот курсов по данным ЦБ РФ. Выберите действие:", reply_markup=main_menu())


async def handle_send_now(m: types.Message):
    """Обработка запроса текущих курсов валют"""
    row = await get_settings(m.from_user.id)
    currencies = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    tz = int(row[4] or 0)
    res = await fetch_rates(currencies)
    user_now = datetime.utcnow() + timedelta(hours=tz)
    text = format_rates_for_user(res.get("base", "RUB"), user_now, res.get("rates", {}))
    await m.answer(text)


async def cmd_exchangerate_date(m: types.Message, state: FSMContext):
    """Обработка команды /exchangerate_date"""
    await m.answer("📅 Введите дату в формате DD.MM.YYYY (например: 25.09.2025):")
    await state.set_state(DateForm.waiting_for_date)


async def process_date(m: types.Message, state: FSMContext):
    """Обработка ввода даты"""
    try:
        dt = datetime.strptime(m.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await m.answer("❗ Неверный формат даты. Используйте DD.MM.YYYY (например: 25.09.2025)")
        return
    
    row = await get_settings(m.from_user.id)
    currencies = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    res = await fetch_rates_by_date(dt, currencies)
    text = format_rates_for_user(res.get("base", "RUB"), dt, res.get("rates", {}))
    await m.answer(text, reply_markup=main_menu())
    await state.clear()
