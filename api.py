import aiohttp
from datetime import datetime, date
import xml.etree.ElementTree as ET
from config import CBR_URL, CBR_ARCHIVE_URL, CBR_VALFULL_URL, CBR_DYNAMIC_URL


async def fetch_all_rates():
    """Получение текущих курсов валют"""
    async with aiohttp.ClientSession() as session:
        async with session.get(CBR_URL, timeout=20) as resp:
            data = await resp.json(content_type=None)
            date_str = datetime.strptime(data["Date"], "%Y-%m-%dT%H:%M:%S%z").strftime("%d.%m")
            rates = {}
            for code, v in data["Valute"].items():
                value = v["Value"]
                nominal = v["Nominal"]
                prev = v.get("Previous")
                rates[code] = {
                    "value": value,
                    "nominal": nominal,
                    "previous": prev
                }
            return {"base": "RUB", "date": date_str, "rates": rates}


async def fetch_rates_by_date(dt: date, currencies: list):
    """Получение курсов валют за конкретную дату"""
    url = CBR_ARCHIVE_URL.format(year=dt.year, month=dt.month, day=dt.day)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    raise ValueError("Нет данных за эту дату")
                data = await resp.json(content_type=None)
                rates = {}
                for code in currencies:
                    v = data["Valute"].get(code)
                    if not v:
                        rates[code] = {"value": None, "nominal": 1, "previous": None}
                    else:
                        rates[code] = {
                            "value": v["Value"],
                            "nominal": v["Nominal"],
                            "previous": v.get("Previous"),
                        }
                return {"base": "RUB", "date": dt.strftime("%d.%m.%Y"), "rates": rates}
    except Exception:
        return {
            "base": "RUB",
            "date": dt.strftime("%d.%m"),
            "rates": {c: {"value": None, "nominal": 1, "previous": None} for c in currencies}
        }


async def fetch_rates(currencies: list):
    """Получение курсов валют для списка валют"""
    try:
        all_data = await fetch_all_rates()
        rates = {c: all_data["rates"].get(c) for c in currencies}
        return {"base": "RUB", "date": all_data["date"], "rates": rates}
    except Exception:
        now = datetime.utcnow()
        return {
            "base": "RUB",
            "date": now.strftime("%d.%m"),
            "rates": {c: {"value": None, "nominal": 1} for c in currencies}
        }


async def get_currency_id(currency: str) -> str:
    """Получение ID валюты из справочника ЦБ РФ"""
    async with aiohttp.ClientSession() as session:
        async with session.get(CBR_VALFULL_URL) as resp:
            if resp.status != 200:
                raise ValueError("Не удалось загрузить справочник валют")
            xml_text = await resp.text()
            root = ET.fromstring(xml_text)
            for item in root.findall('Item'):
                char_code = item.find('ISO_Char_Code')
                if char_code is not None and char_code.text == currency:
                    return item.get('ID')
            raise ValueError(f"Валюта {currency} не найдена в справочнике")


async def fetch_historical_data(currency: str, start_date: date, end_date: date):
    """Получение исторических данных по валюте"""
    currency_id = await get_currency_id(currency)
    url = (
        f"{CBR_DYNAMIC_URL}?"
        f"date_req1={start_date.strftime('%d/%m/%Y')}&"
        f"date_req2={end_date.strftime('%d/%m/%Y')}&"
        f"VAL_NM_RQ={currency_id}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError("Не удалось загрузить исторические данные")
            xml_text = await resp.text()
            root = ET.fromstring(xml_text)
            data = []
            for record in root.findall('Record'):
                date_str = record.get('Date')
                try:
                    nominal = int(record.find('Nominal').text)
                    value_str = record.find('Value').text.replace(',', '.')
                    value = float(value_str)
                    dt = datetime.strptime(date_str, "%d.%m.%Y").date()
                    data.append((dt, value / nominal))
                except (AttributeError, ValueError):
                    continue
            return data