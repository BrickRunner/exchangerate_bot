import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "rates.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не установлен в .env")

# Настройки по умолчанию
DEFAULT_TIMEZONE = 3  # UTC+3 (Московское время)
DEFAULT_CURRENCIES = "USD,EUR"
DEFAULT_WORKDAYS = [1, 2, 3, 4, 5]  # Понедельник-Пятница
DEFAULT_NOTIFY_TIME = "08:00"

# API URLs
CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CBR_ARCHIVE_URL = "https://www.cbr-xml-daily.ru/archive/{year}/{month:02d}/{day:02d}/daily_json.js"
CBR_VALFULL_URL = "https://www.cbr.ru/scripts/XML_valFull.asp"
CBR_DYNAMIC_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"

# Определение словаря символов валют
CURRENCY_SYMBOLS = {
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
    "CNY": "¥",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "₣",
    "KZT": "₸",
    "TRY": "₺",
    "INR": "₹",
    "KRW": "₩",
    "AED": "د.إ",
    "UZS": "so'm",
    "BYN": "Br",
    "PLN": "zł",
    "CZK": "Kč",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "HUF": "Ft",
    "BGN": "лв",
    "RON": "lei",
    "BRL": "R$",
    "MXN": "$",
    "CAD": "$",
    "AUD": "$",
    "NZD": "$",
    "HKD": "$",
    "SGD": "$",
    "ZAR": "R",
    "ILS": "₪",
    "PHP": "₱",
    "THB": "฿",
    "MYR": "RM",
    "IDR": "Rp",
    "VND": "₫",
    "PKR": "₨",
    "EGP": "£",
    "SAR": "﷼",
    "KWD": "د.ك",
    "BHD": "ب.د",
    "QAR": "﷼",
    "TND": "د.ت",
    "CLP": "$",
    "COP": "$",
    "ARS": "$",
    "UYU": "$",
    "PEN": "S/",
    "DZD": "د.ج",
    "MAD": "د.م",
    "LBP": "ل.ل",
    "OMR": "ر.ع",
    "AZN": "₼",
}