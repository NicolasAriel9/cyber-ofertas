"""One-off setup: configure the bot's public-facing presentation (command
menu, description, short description) via the Bot API, in Spanish. Safe to
re-run any time the wording changes -- these calls just overwrite the
previous configuration. Things the Bot API can't set (profile photo, "about"
text) still need to be done once in BotFather manually -- see the printed
reminder at the end.

Usage: .venv\\Scripts\\python.exe scripts\\configure_telegram_bot.py
"""

import httpx

from app.config import settings

BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

COMMANDS = [
    {"command": "start", "description": "Vincular tu cuenta a Cyber Ofertas"},
    {"command": "ayuda", "description": "Ver qué puede hacer este bot"},
]

DESCRIPTION = (
    "Te aviso por Telegram cuando un producto que sigues en Cyber Ofertas "
    "baja de precio durante el Cyber. Vincula tu cuenta desde la app para empezar."
)

SHORT_DESCRIPTION = "Avisos de bajada de precio para tus favoritos en Cyber Ofertas."


def call(method: str, **payload) -> None:
    response = httpx.post(f"{BASE}/{method}", json=payload, timeout=15.0)
    response.raise_for_status()
    data = response.json()
    status = "OK" if data.get("ok") else f"FAILED: {data}"
    print(f"{method}: {status}")


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (check backend/.env)")

    call("setMyCommands", commands=COMMANDS, language_code="es")
    call("setMyCommands", commands=COMMANDS)  # default for any other language too
    call("setMyDescription", description=DESCRIPTION, language_code="es")
    call("setMyShortDescription", short_description=SHORT_DESCRIPTION, language_code="es")

    print(
        "\nHecho. Dos cosas que la API no puede configurar -- hazlas una vez en "
        "@BotFather si quieres:\n"
        "  /setuserpic   -> subir una foto de perfil para el bot\n"
        "  /setabouttext -> texto corto que aparece en su perfil (debajo de la foto)"
    )


if __name__ == "__main__":
    main()
