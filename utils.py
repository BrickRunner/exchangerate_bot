from datetime import datetime
from config import CURRENCY_SYMBOLS


def calc_percent(current: float, threshold: float) -> str:
    """Вычисление процентного отличия порога от текущей цены"""
    try:
        if current == 0 or current is None:
            return ""
        diff = ((threshold - current) / current) * 100
        arrow = "📈" if diff > 0 else ("📉" if diff < 0 else "➖")
        return f"{arrow} {diff:+.2f}%"
    except Exception:
        return ""


def format_rates_for_user(base: str, dt_obj, rates: dict) -> str:
    """Форматирование курсов валют для пользователя"""
    if isinstance(dt_obj, datetime):
        dt_str = dt_obj.strftime('%d.%m.%Y %H:%M')
        label = " (локальное время)"
    else:
        dt_str = dt_obj.strftime('%d.%m.%Y')
        label = ""
    
    lines = [f"📊 Курсы валют на {dt_str}{label}", ""]
    base_symbol = CURRENCY_SYMBOLS.get(base, base)
    
    for c, data in rates.items():
        if data is None or data.get("value") is None:
            symbol = CURRENCY_SYMBOLS.get(c)
            if symbol:
                lines.append(f"{c} ({symbol}): — {base_symbol}")
            else:
                lines.append(f"{c}: — {base_symbol}")
        else:
            value = data["value"]
            nominal = data.get("nominal", 1)
            prev = data.get("previous")
            change_str = ""
            
            if prev is not None:
                try:
                    diff = ((value - prev) / prev) * 100
                    arrow = "📈" if diff > 0 else ("📉" if diff < 0 else "➖")
                    change_str = f" {arrow} {diff:+.2f}%"
                except Exception:
                    pass
            
            value_str = f"{value:.2f}"
            nominal_str = f" (за {nominal} шт)" if nominal != 1 else ""
            symbol = CURRENCY_SYMBOLS.get(c)
            
            if symbol:
                lines.append(f"{c} ({symbol}): {value_str} {base_symbol}{nominal_str}{change_str}")
            else:
                lines.append(f"{c}: {value_str} {base_symbol}{nominal_str}{change_str}")
    
    lines.append("")
    return "\n".join(lines)
