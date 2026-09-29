"""Local development helper: we don't have a public webhook URL yet (that
comes with the Render deploy), so this polls Telegram's getUpdates API and
forwards each update to our own local /telegram/webhook endpoint -- exactly
what Telegram's servers would do via a real webhook. Run this in its own
terminal while developing so the bot responds live.

Only useful for local testing -- production uses a real webhook (see
README.md) since a long-running poller doesn't fit a sleep-eligible free
host. A bot can only use ONE delivery method at a time: don't run this at the
same time a webhook is registered for the same bot (call deleteWebhook first
if one was ever set), and don't call setWebhook while this is running.

Usage: .venv\\Scripts\\python.exe scripts\\telegram_poll_dev.py
"""

import time

import httpx

from app.config import settings

BACKEND_WEBHOOK_URL = "http://127.0.0.1:8000/telegram/webhook"
POLL_TIMEOUT = 25  # seconds -- Telegram long-polling wait


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (check backend/.env)")

    base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    offset = None
    print("Escuchando mensajes de Telegram en vivo... (Ctrl+C para detener)")

    with httpx.Client(timeout=POLL_TIMEOUT + 10) as client:
        # Make sure no webhook is registered -- getUpdates fails otherwise.
        client.post(f"{base_url}/deleteWebhook")

        while True:
            params = {"timeout": POLL_TIMEOUT}
            if offset is not None:
                params["offset"] = offset

            try:
                response = client.get(f"{base_url}/getUpdates", params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                print(f"Error consultando Telegram: {exc}")
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                text = update.get("message", {}).get("text", "")
                print(f"-> {text!r}")
                try:
                    client.post(BACKEND_WEBHOOK_URL, json=update)
                except httpx.HTTPError as exc:
                    print(f"Error reenviando al backend: {exc}")


if __name__ == "__main__":
    main()
