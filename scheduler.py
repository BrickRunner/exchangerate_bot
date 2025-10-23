import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
import logging
from typing import Set, Tuple

from database import get_all_users_settings, update_last_sent_date, get_user_thresholds
from api import fetch_rates
from utils import format_rates_for_user
from config import DEFAULT_CURRENCIES, DEFAULT_WORKDAYS, DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)

# Константы
SCHEDULER_POLL_INTERVAL = 60  # Интервал проверки в секундах (увеличен до 60 для избежания дубликатов)


async def scheduler_loop(bot: Bot):
    """Планировщик для отправки уведомлений"""
    # Множество для отслеживания уже отправленных уведомлений в текущей минуте
    sent_this_minute: Set[Tuple[int, int, int]] = set()  # (user_id, hour, minute)
    last_checked_minute = None

    logger.info("Scheduler started")

    while True:
        try:
            current_time = datetime.utcnow()
            current_minute = (current_time.hour, current_time.minute)

            # Сброс кеша при смене минуты
            if current_minute != last_checked_minute:
                sent_this_minute.clear()
                last_checked_minute = current_minute

            rows = await get_all_users_settings()
            if rows:
                logger.info(f"Scheduler check: {len(rows)} users at UTC {current_time.strftime('%H:%M:%S')}")

            for row in rows:
                user_id, currencies, notify_time, days, tz, last_sent = row

                if not notify_time:
                    continue

                try:
                    hh, mm = map(int, notify_time.split(":"))
                    if not (0 <= hh <= 23 and 0 <= mm <= 59):
                        logger.warning(f"Invalid time format for user {user_id}: {notify_time}")
                        continue
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse notify_time for user {user_id}: {notify_time}, error: {e}")
                    continue

                try:
                    tz = int(tz or DEFAULT_TIMEZONE)
                    if not (-12 <= tz <= 14):
                        logger.warning(f"Invalid timezone for user {user_id}: {tz}")
                        tz = DEFAULT_TIMEZONE
                except (ValueError, TypeError):
                    tz = DEFAULT_TIMEZONE

                user_now = datetime.utcnow() + timedelta(hours=tz)

                # Проверка на уже отправленное уведомление в эту минуту
                notification_key = (user_id, user_now.hour, user_now.minute)
                if notification_key in sent_this_minute:
                    continue

                if user_now.hour == hh and user_now.minute == mm:
                    logger.info(f"⏰ Time match for user {user_id}: {hh:02d}:{mm:02d}")
                    daynum = user_now.isoweekday()

                    try:
                        allowed_days = [int(d) for d in (days or "").split(",") if d.strip().isdigit()] or DEFAULT_WORKDAYS
                    except Exception as e:
                        logger.warning(f"Failed to parse allowed days for user {user_id}: {e}")
                        allowed_days = DEFAULT_WORKDAYS

                    if daynum in allowed_days:
                        today_iso = user_now.date().isoformat()

                        # Проверка, что уведомление еще не отправлялось сегодня
                        if last_sent == today_iso:
                            logger.info(f"Already sent notification today for user {user_id}")
                            continue

                        # Отправка курсов валют
                        try:
                            currs = [c.strip().upper() for c in (currencies or DEFAULT_CURRENCIES).split(",") if c.strip()]
                            res = await fetch_rates(currs)
                            text = format_rates_for_user(res.get("base", "RUB"), user_now, res.get("rates", {}))

                            await bot.send_message(user_id, text)
                            logger.info(f"Sent rate notification to user {user_id}")
                        except TelegramAPIError as e:
                            logger.warning(f"Failed to send message to user {user_id}: {e}")
                            # Пользователь мог заблокировать бота
                            continue
                        except Exception as e:
                            logger.error(f"Error sending rates to user {user_id}: {e}", exc_info=True)
                            continue

                        # Проверка пороговых значений
                        try:
                            thresholds = await get_user_thresholds(user_id)

                            if thresholds:
                                res_all = await fetch_rates([t[1] for t in thresholds])

                                for tid, c, tval, comm in thresholds:
                                    data = res_all["rates"].get(c)
                                    if not data or not data.get("value") or data.get("previous") is None:
                                        continue

                                    curr_val = data["value"]
                                    prev_val = data["previous"]

                                    # Проверка пересечения порога (только если пересекли, а не равны)
                                    if (curr_val > tval >= prev_val) or (curr_val < tval <= prev_val):
                                        text = f"⚠️ {c} достиг порогового значения {tval}!\nТекущий курс: {curr_val:.2f}"
                                        if comm:
                                            text += f"\nКомментарий: {comm}"
                                        try:
                                            await bot.send_message(user_id, text)
                                            logger.info(f"Sent threshold alert to user {user_id} for {c}")
                                        except TelegramAPIError as e:
                                            logger.warning(f"Failed to send threshold alert to user {user_id}: {e}")
                        except Exception as e:
                            logger.error(f"Error checking thresholds for user {user_id}: {e}", exc_info=True)

                        # Обновление даты последней отправки
                        await update_last_sent_date(user_id, today_iso)
                        # Отметка, что уведомление отправлено в эту минуту
                        sent_this_minute.add(notification_key)

            await asyncio.sleep(SCHEDULER_POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info("Scheduler cancelled, shutting down")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in scheduler: {e}", exc_info=True)
            await asyncio.sleep(5)
