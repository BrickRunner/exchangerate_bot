import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command

from config import BOT_TOKEN
from database import init_db
from scheduler import scheduler_loop
from states import DateForm, InlineThresholdForm

# Импорт обработчиков
from handlers import basic, settings, thresholds, stats_handlers

# Инициализация бота и диспетчера
bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def register_handlers():
    """Регистрация всех обработчиков"""
    
    # Базовые команды
    dp.message.register(basic.cmd_start, Command("start"))
    dp.message.register(basic.cmd_exchangerate_date, Command("exchangerate_date"))
    dp.message.register(basic.process_date, DateForm.waiting_for_date)
    dp.message.register(basic.handle_send_now, lambda m: m.text == "📊 Курсы валют сейчас")
    
    # Настройки
    dp.message.register(settings.handle_settings, lambda m: m.text == "⚙ Настройки")
    dp.message.register(
        settings.msg_set_time,
        lambda m: len(m.text) == 5 and m.text.count(":") == 1 and m.text.replace(":", "").isdigit()
    )
    dp.callback_query.register(settings.cb_set_currencies, lambda c: c.data == "set_currencies")
    dp.callback_query.register(settings.cb_toggle_curr, lambda c: c.data.startswith("toggle_curr:"))
    dp.callback_query.register(settings.cb_set_time, lambda c: c.data == "set_time")
    dp.callback_query.register(settings.cb_set_days, lambda c: c.data == "set_days")
    dp.callback_query.register(settings.cb_toggle_day, lambda c: c.data.startswith("toggle_day:"))
    dp.callback_query.register(settings.cb_set_timezone, lambda c: c.data == "set_timezone")
    dp.callback_query.register(settings.cb_set_tz, lambda c: c.data.startswith("set_tz:"))
    dp.callback_query.register(settings.cb_back, lambda c: c.data == "back_settings")
    
    # Пороговые значения
    dp.message.register(thresholds.handle_thresholds, lambda m: m.text == "📉 Пороговые значения")
    dp.message.register(thresholds.threshold_value_manual, InlineThresholdForm.entering_value)
    dp.message.register(thresholds.threshold_comment_manual, InlineThresholdForm.entering_comment_manual)
    dp.callback_query.register(thresholds.cb_add_threshold, lambda c: c.data == "add_threshold")
    dp.callback_query.register(thresholds.cb_delete_thresholds, lambda c: c.data == "del_thresholds")
    dp.callback_query.register(
        thresholds.cb_delete_specific_threshold,
        lambda c: c.data.startswith("del_thr:")
    )
    dp.callback_query.register(
        thresholds.cb_threshold_currency,
        lambda c: c.data.startswith("th_curr:")
    )
    dp.callback_query.register(thresholds.cb_back_main, lambda c: c.data == "back_main")
    
    # Статистика
    dp.message.register(stats_handlers.handle_stats, lambda m: m.text == "📈 Статистика")
    dp.callback_query.register(stats_handlers.cb_stats, lambda c: c.data == "stats")
    dp.callback_query.register(stats_handlers.cb_stats_period, lambda c: c.data.startswith("stats_curr:"))
    dp.callback_query.register(stats_handlers.cb_show_graph, lambda c: c.data.startswith("stats_period:"))


async def main():
    """Основная функция запуска бота"""
    await init_db()
    register_handlers()
    
    # Запуск планировщика в фоне
    asyncio.create_task(scheduler_loop(bot))
    
    # Запуск polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())