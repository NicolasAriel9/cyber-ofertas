"""Thin wrapper for sending Telegram alerts. Uses python-telegram-bot's plain
Bot class for sending only -- no long-polling/Application, since that would
need an always-on process that doesn't fit a sleep-eligible free host.
"""

from telegram import Bot
from telegram.error import TelegramError

from app.config import settings


async def send_message(chat_id: int, text: str, parse_mode: str | None = None) -> bool:
    if not settings.telegram_bot_token:
        return False
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except TelegramError:
        return False


def format_price_drop_message(*, product_title: str, store_name: str, old_price: float, new_price: float, url: str) -> str:
    old_fmt = f"{old_price:,.0f}".replace(",", ".")
    new_fmt = f"{new_price:,.0f}".replace(",", ".")
    return (
        f"📉 *Bajó de precio*\n\n"
        f"{product_title}\n\n"
        f"{store_name}: ~${old_fmt}~ → *${new_fmt}*\n"
        f"{url}"
    )
