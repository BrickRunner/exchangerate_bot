import aiohttp
from datetime import datetime, date
import xml.etree.ElementTree as ET
import logging
from typing import Dict, List, Tuple, Optional
from config import CBR_URL, CBR_ARCHIVE_URL, CBR_VALFULL_URL, CBR_DYNAMIC_URL

logger = logging.getLogger(__name__)

# Глобальная сессия для переиспользования соединений
_session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    """Получение или создание глобальной HTTP-сессии"""
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"User-Agent": "ExchangeRateBot/1.0"}
        _session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    return _session


async def close_session():
    """Закрытие глобальной HTTP-сессии"""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def fetch_all_rates() -> Dict:
    """Получение текущих курсов валют"""
    try:
        session = await get_session()
        async with session.get(CBR_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logger.error(f"CBR API returned status {resp.status}")
                raise ValueError(f"API returned status {resp.status}")

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
            logger.info(f"Fetched {len(rates)} exchange rates")
            return {"base": "RUB", "date": date_str, "rates": rates}
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching rates: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching rates: {e}", exc_info=True)
        raise


async def fetch_rates_by_date(dt: date, currencies: List[str]) -> Dict:
    """Получение курсов валют за конкретную дату"""
    url = CBR_ARCHIVE_URL.format(year=dt.year, month=dt.month, day=dt.day)
    try:
        session = await get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logger.warning(f"No data for date {dt}: status {resp.status}")
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
            logger.info(f"Fetched rates for {len(currencies)} currencies on {dt}")
            return {"base": "RUB", "date": dt.strftime("%d.%m.%Y"), "rates": rates}
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching rates for {dt}: {e}")
        return {
            "base": "RUB",
            "date": dt.strftime("%d.%m"),
            "rates": {c: {"value": None, "nominal": 1, "previous": None} for c in currencies}
        }
    except Exception as e:
        logger.error(f"Error fetching rates for {dt}: {e}", exc_info=True)
        return {
            "base": "RUB",
            "date": dt.strftime("%d.%m"),
            "rates": {c: {"value": None, "nominal": 1, "previous": None} for c in currencies}
        }


async def fetch_rates(currencies: List[str]) -> Dict:
    """Получение курсов валют для списка валют"""
    try:
        all_data = await fetch_all_rates()
        rates = {c: all_data["rates"].get(c) for c in currencies}
        return {"base": "RUB", "date": all_data["date"], "rates": rates}
    except Exception as e:
        logger.error(f"Error fetching rates for currencies {currencies}: {e}", exc_info=True)
        now = datetime.utcnow()
        return {
            "base": "RUB",
            "date": now.strftime("%d.%m"),
            "rates": {c: {"value": None, "nominal": 1} for c in currencies}
        }


async def get_currency_id(currency: str) -> str:
    """Получение ID валюты из справочника ЦБ РФ"""
    try:
        session = await get_session()
        async with session.get(CBR_VALFULL_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch currency directory: status {resp.status}")
                raise ValueError("Не удалось загрузить справочник валют")

            xml_text = await resp.text()
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError as e:
                logger.error(f"Invalid XML response from currency directory: {e}")
                raise ValueError("Получен некорректный ответ от API")

            for item in root.findall('Item'):
                char_code = item.find('ISO_Char_Code')
                if char_code is not None and char_code.text == currency:
                    return item.get('ID')

            logger.warning(f"Currency {currency} not found in directory")
            raise ValueError(f"Валюта {currency} не найдена в справочнике")
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching currency ID for {currency}: {e}")
        raise


async def fetch_historical_data(currency: str, start_date: date, end_date: date) -> List[Tuple[date, float]]:
    """Получение исторических данных по валюте"""
    try:
        currency_id = await get_currency_id(currency)
        url = (
            f"{CBR_DYNAMIC_URL}?"
            f"date_req1={start_date.strftime('%d/%m/%Y')}&"
            f"date_req2={end_date.strftime('%d/%m/%Y')}&"
            f"VAL_NM_RQ={currency_id}"
        )

        session = await get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch historical data: status {resp.status}")
                raise ValueError("Не удалось загрузить исторические данные")

            xml_text = await resp.text()
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError as e:
                logger.error(f"Invalid XML in historical data response: {e}")
                raise ValueError("Получен некорректный ответ от API")

            data = []
            for record in root.findall('Record'):
                date_str = record.get('Date')
                try:
                    nominal_elem = record.find('Nominal')
                    value_elem = record.find('Value')

                    if nominal_elem is None or value_elem is None:
                        continue

                    nominal = int(nominal_elem.text)
                    value_str = value_elem.text.replace(',', '.')
                    value = float(value_str)
                    dt = datetime.strptime(date_str, "%d.%m.%Y").date()
                    data.append((dt, value / nominal))
                except (AttributeError, ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid record for date {date_str}: {e}")
                    continue

            logger.info(f"Fetched {len(data)} historical records for {currency}")
            return data
    except Exception as e:
        logger.error(f"Error fetching historical data for {currency}: {e}", exc_info=True)
        raise