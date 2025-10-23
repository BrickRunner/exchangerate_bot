from aiogram import types
from aiogram.exceptions import TelegramBadRequest

from database import get_settings, update_settings
from keyboards import (
    settings_menu, build_currencies_kb, build_days_kb, 
    build_timezone_kb, main_menu
)


async def handle_settings(m: types.Message):
    """Обработка выбора настроек"""
    await m.answer("⚙ Настройки — выберите раздел:", reply_markup=settings_menu())


async def cb_set_currencies(cb: types.CallbackQuery):
    """Обработка выбора валют в настройках"""
    row = await get_settings(cb.from_user.id)
    selected = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    kb = await build_currencies_kb(selected)
    try:
        await cb.message.edit_text("Выберите валюты (нажмите, чтобы переключить):", reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer()


async def cb_toggle_curr(cb: types.CallbackQuery):
    """Обработка переключения валюты"""
    cur = cb.data.split(":", 1)[1]
    row = await get_settings(cb.from_user.id)
    selected = [c.strip().upper() for c in (row[1] or "USD,EUR").split(",") if c.strip()]
    
    if cur in selected:
        selected.remove(cur)
    else:
        selected.append(cur)
    
    if selected:
        await update_settings(cb.from_user.id, "currencies", ",".join(selected))
    else:
        await update_settings(cb.from_user.id, "currencies", "")
    
    await cb_set_currencies(cb)


async def cb_set_time(cb: types.CallbackQuery):
    """Обработка выбора времени уведомлений"""
    row = await get_settings(cb.from_user.id)
    current_time = row[2] or "08:00"
    kb = settings_menu()
    try:
        await cb.message.edit_text(
            f"⏰ Текущее время уведомлений: <b>{current_time}</b>\n\n"
            "Введите новое время в формате ЧЧ:ММ или Ч:М (24ч)\n"
            "Примеры: 09:00, 9:0, 7:30, 23:45",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass
    await cb.answer()


async def msg_set_time(m: types.Message):
    """Обработка ввода времени уведомлений"""
    try:
        # Разделяем по двоеточию
        if ":" not in m.text:
            raise ValueError("Нет разделителя :")

        parts = m.text.split(":")
        if len(parts) != 2:
            raise ValueError("Неверное количество частей")

        hh, mm = parts
        hh_i = int(hh.strip())
        mm_i = int(mm.strip())

        # Валидация диапазона
        if not (0 <= hh_i < 24 and 0 <= mm_i < 60):
            raise ValueError("Время вне диапазона")

        # Форматирование в корректный вид ЧЧ:ММ
        formatted_time = f"{hh_i:02d}:{mm_i:02d}"

    except (ValueError, AttributeError) as e:
        await m.answer(
            "❌ Неверный формат времени!\n\n"
            "Используйте формат ЧЧ:ММ или Ч:М\n"
            "Примеры: 09:00, 9:0, 23:45, 7:30",
            reply_markup=main_menu()
        )
        return

    await update_settings(m.from_user.id, "notify_time", formatted_time)
    await m.answer(
        f"✅ Время уведомлений обновлено!\n\n"
        f"Текущее время: <b>{formatted_time}</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


async def cb_set_days(cb: types.CallbackQuery):
    """Обработка выбора дней уведомлений"""
    row = await get_settings(cb.from_user.id)
    selected = [d for d in (row[3] or "1,2,3,4,5").split(",") if d.strip()]
    kb = build_days_kb(selected)
    try:
        await cb.message.edit_text("Выберите дни рассылки (нажмите чтобы переключить):", reply_markup=kb)
    except TelegramBadRequest:
        pass
    await cb.answer()


async def cb_toggle_day(cb: types.CallbackQuery):
    """Обработка переключения дня уведомлений"""
    day = cb.data.split(":", 1)[1]
    row = await get_settings(cb.from_user.id)
    selected = [d for d in (row[3] or "1,2,3,4,5").split(",") if d.strip()]
    
    if day in selected:
        selected.remove(day)
    else:
        selected.append(day)
    
    selected_sorted = sorted(set(int(x) for x in selected)) if selected else []
    selected_str = ",".join(str(x) for x in selected_sorted)
    if selected_str == "":
        selected_str = ""
    
    await update_settings(cb.from_user.id, "days", selected_str)
    await cb_set_days(cb)


async def cb_set_timezone(cb: types.CallbackQuery):
    """Обработка выбора часового пояса"""
    row = await get_settings(cb.from_user.id)
    current_tz = row[4] or "3"  # По умолчанию UTC+3
    kb = build_timezone_kb()
    try:
        tz_display = f"UTC{int(current_tz):+d}" if int(current_tz) != 0 else "UTC+0"
        await cb.message.edit_text(
            f"🌍 Текущий часовой пояс: <b>{tz_display}</b>\n\n"
            "Выберите новый часовой пояс:",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass
    await cb.answer()


async def cb_set_tz(cb: types.CallbackQuery):
    """Установка часового пояса"""
    tz = int(cb.data.split(":", 1)[1])
    await update_settings(cb.from_user.id, "timezone", str(tz))
    try:
        tz_display = f"UTC{tz:+d}" if tz != 0 else "UTC+0"
        await cb.answer(f"🌍 Часовой пояс установлен: {tz_display}")
    except Exception:
        pass
    await cb.message.edit_text("⚙ Настройки:", reply_markup=settings_menu())


async def cb_back(cb: types.CallbackQuery):
    """Обработка возврата в меню настроек"""
    try:
        await cb.message.edit_text("⚙ Настройки:", reply_markup=settings_menu())
    except TelegramBadRequest:
        pass
    await cb.answer()