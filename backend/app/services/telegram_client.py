"""Thin wrapper for sending Telegram alerts. Uses python-telegram-bot's plain
Bot class for sending only -- no long-polling/Application, since that would
need an always-on process that doesn't fit a sleep-eligible free host.
"""

from telegram import Bot
from telegram.error import TelegramError

from app.config import settings


async def send_message(chat_id: int, text: str) -> bool:
    if not settings.telegram_bot_token:
        return False
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except TelegramError:
        return False


def format_price_drop_message(*, product_title: str, store_name: str, old_price: float, new_price: float, url: str) -> str:
    return (
        f"\U0001f4c9 Bajó de precio: {product_title}\n"
        f"{store_name}: ${old_price:,.0f} → ${new_price:,.0f}\n"
        f"{url}"
    ).replace(",", ".")
