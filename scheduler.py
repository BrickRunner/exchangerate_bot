import asyncio
from datetime import datetime, timedelta
from aiogram import Bot

from database import get_all_users_settings, update_last_sent_date, get_user_thresholds
from api import fetch_rates
from utils import format_rates_for_user


async def scheduler_loop(bot: Bot):
    """Планировщик для отправки уведомлений"""
    while True:
        try:
            rows = await get_all_users_settings()
            
            for row in rows:
                user_id, currencies, notify_time, days, tz, last_sent = row
                
                if not notify_time:
                    continue
                
                try:
                    hh, mm = map(int, notify_time.split(":"))
                except Exception:
                    continue
                
                tz = int(tz or 0)
                user_now = datetime.utcnow() + timedelta(hours=tz)
                
                if user_now.hour == hh and user_now.minute == mm:
                    daynum = user_now.isoweekday()
                    allowed_days = [int(d) for d in (days or "").split(",") if d.strip().isdigit()] or [1, 2, 3, 4, 5]
                    
                    if daynum in allowed_days:
                        today_iso = (user_now.date()).isoformat()
                        
                        if last_sent == today_iso:
                            continue
                        
                        # Отправка курсов валют
                        currs = [c.strip().upper() for c in (currencies or "USD,EUR").split(",") if c.strip()]
                        res = await fetch_rates(currs)
                        text = format_rates_for_user(res.get("base", "RUB"), user_now, res.get("rates", {}))
                        
                        try:
                            await bot.send_message(user_id, text)
                        except Exception:
                            pass
                        
                        # Проверка пороговых значений
                        thresholds = await get_user_thresholds(user_id)
                        
                        if thresholds:
                            res_all = await fetch_rates([t[1] for t in thresholds])
                            
                            for tid, c, tval, comm in thresholds:
                                data = res_all["rates"].get(c)
                                if not data or not data.get("value") or data.get("previous") is None:
                                    continue
                                
                                curr_val = data["value"]
                                prev_val = data["previous"]
                                
                                # Проверка пересечения порога
                                if (curr_val >= tval and prev_val < tval) or (curr_val <= tval and prev_val > tval):
                                    text = f"⚠️ {c} достиг порогового значения {tval}!\nТекущий курс: {curr_val:.2f}"
                                    if comm:
                                        text += f"\nКомментарий: {comm}"
                                    try:
                                        await bot.send_message(user_id, text)
                                    except Exception:
                                        pass
                        
                        await update_last_sent_date(user_id, today_iso)
            
            await asyncio.sleep(30)
        
        except Exception:
            await asyncio.sleep(5)
