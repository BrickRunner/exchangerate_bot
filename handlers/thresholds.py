from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database import get_user_thresholds, add_threshold, delete_threshold
from api import fetch_rates
from utils import calc_percent
from keyboards import thresholds_menu, build_threshold_currency_kb, main_menu
from states import InlineThresholdForm


async def handle_thresholds(m: types.Message):
    """Обработка запроса пороговых значений"""
    rows = await get_user_thresholds(m.from_user.id)
    thresholds = [(r[1], r[2], r[3], r[0]) for r in rows]
    codes = [t[0] for t in thresholds]
    res_all = await fetch_rates(codes) if codes else {"rates": {}}
    
    text = "📉 Ваши пороговые значения:\n\n"
    if not thresholds:
        text += "У вас пока нет установленных пороговых значений."
    else:
        for currency, value, comment, tid in thresholds:
            curr_val = res_all["rates"].get(currency, {}).get("value")
            percent_str = calc_percent(curr_val, value) if curr_val else ""
            comment_str = f" — Комментарий: {comment}" if comment else ""
            text += f"{currency}: {value:.2f} {percent_str}{comment_str}\n"
    
    text += "\nВыберите действие:"
    await m.answer(text, reply_markup=thresholds_menu())


async def cb_add_threshold(cb: types.CallbackQuery, state: FSMContext):
    """Обработка добавления порогового значения"""
    kb = await build_threshold_currency_kb(cb.from_user.id)
    try:
        await cb.message.edit_text("Выберите валюту для порога:", reply_markup=kb)
    except TelegramBadRequest:
        pass
    await state.set_state(InlineThresholdForm.choosing_currency)
    await cb.answer()


async def cb_delete_thresholds(cb: types.CallbackQuery):
    """Обработка удаления пороговых значений"""
    rows = await get_user_thresholds(cb.from_user.id)
    if not rows:
        try:
            await cb.message.edit_text("У вас нет порогов для удаления.", reply_markup=thresholds_menu())
        except TelegramBadRequest:
            pass
        await cb.answer()
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = []
    for tid, currency, value, comment in rows:
        kb.append([InlineKeyboardButton(text=f"{currency} {value:.2f}", callback_data=f"del_thr:{tid}")])
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")])
    
    try:
        await cb.message.edit_text(
            "Выберите порог, который хотите удалить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except TelegramBadRequest:
        pass
    await cb.answer()


async def cb_delete_specific_threshold(cb: types.CallbackQuery):
    """Обработка удаления конкретного порога"""
    tid = int(cb.data.split(":", 1)[1])
    result = await delete_threshold(tid, cb.from_user.id)
    
    if not result:
        try:
            await cb.answer("Порог не найден или уже удалён.", show_alert=True)
        except Exception:
            pass
        return await cb_delete_thresholds(cb)
    
    currency, value = result
    try:
        await cb.answer(f"Порог {currency} {value:.2f} удалён.")
    except Exception:
        pass
    return await cb_delete_thresholds(cb)


async def cb_threshold_currency(cb: types.CallbackQuery, state: FSMContext):
    """Обработка выбора валюты для порога"""
    cur = cb.data.split(":", 1)[1]
    await state.update_data(currency=cur)
    try:
        await cb.message.edit_text(f"Введите пороговое значение для {cur} (например 100.50):")
    except TelegramBadRequest:
        pass
    await state.set_state(InlineThresholdForm.entering_value)
    await cb.answer()


async def threshold_value_manual(m: types.Message, state: FSMContext):
    """Обработка ввода значения порога"""
    try:
        val = float(m.text.strip().replace(",", "."))
    except ValueError:
        await m.answer("❌ Введите корректное число!")
        return
    
    await state.update_data(value=val)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")]], resize_keyboard=True
    )
    await m.answer(
        "Введите комментарий к порогу (можно оставить пустым), или нажмите кнопку ниже: <b>Пропустить</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(InlineThresholdForm.entering_comment_manual)


async def threshold_comment_manual(m: types.Message, state: FSMContext):
    """Обработка ввода комментария к порогу"""
    txt = m.text.strip()
    if txt.lower() in ("/skip", "пропустить", "**пропустить**"):
        comment = ""
    else:
        comment = txt
    
    data = await state.get_data()
    currency = data.get("currency")
    value = data.get("value")
    
    if not currency or value is None:
        await m.answer("Ошибка состояния — повторите добавление порога.", reply_markup=main_menu())
        await state.clear()
        return
    
    await add_threshold(m.from_user.id, currency, value, comment)
    
    res = await fetch_rates([currency])
    curr_val = res["rates"].get(currency, {}).get("value")
    percent_str = calc_percent(curr_val, value) if curr_val else ""
    
    await m.answer(
        f"✅ Порог {currency} {value} добавлен! {percent_str}\nКомментарий: {comment or 'нет'}",
        reply_markup=main_menu()
    )
    await state.clear()


async def cb_back_main(cb: types.CallbackQuery):
    """Обработка возврата в главное меню"""
    rows = await get_user_thresholds(cb.from_user.id)
    text = "📉 Ваши пороговые значения:\n\n"
    if not rows:
        text += "У вас пока нет установленных пороговых значений."
    else:
        for tid, currency, value, comment in rows:
            comment_str = f" ({comment})" if comment else ""
            text += f"{currency}: {value:.2f}{comment_str}\n"
    text += "\nВыберите действие:"
    try:
        await cb.message.edit_text(text, reply_markup=thresholds_menu())
    except TelegramBadRequest:
        pass
    await cb.answer()