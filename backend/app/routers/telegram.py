import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import require_auth
from app.config import settings
from app.db import get_db
from app.models import Subscriber
from app.schemas import TelegramLinkCodeOut
from app.services.assistant import answer_question
from app.services.telegram_client import send_message
from app.utils import ensure_aware

router = APIRouter(tags=["telegram"])

LINK_CODE_TTL = timedelta(minutes=15)

WELCOME_TEXT = (
    "👋 ¡Hola! Soy el bot de *Cyber Ofertas*.\n\n"
    "Te aviso apenas un producto que sigues baje de precio durante el Cyber.\n\n"
    "Para vincular tu cuenta, abre la app, ve a la pestaña *Telegram* y toca "
    '"Generar link de conexión" — te va a traer de vuelta aquí.'
)

HELP_TEXT = (
    "🤖 *Cyber Ofertas*\n\n"
    "• Te aviso solo cuando algo que sigues baja de precio.\n"
    "• Pregúntame lo que quieras del catálogo, ej: \"cuál es el notebook más "
    'barato de Lenovo\" o \"ofertas de Samsung bajo 200 mil".\n'
    "• Si no estás vinculado todavía, hazlo desde la app → pestaña *Telegram*."
)

NOT_LINKED_TEXT = (
    "Todavía no vinculé tu cuenta 🔒 Abre la app, ve a la pestaña *Telegram* y "
    'toca "Generar link de conexión" para poder ayudarte.'
)

LINK_EXPIRED_TEXT = (
    "⚠️ Ese link ya no es válido (expiró o generaste uno nuevo). Vuelve a la app, "
    "pestaña *Telegram*, y toca de nuevo \"Generar link de conexión\"."
)


@router.post("/subscribers/{subscriber_id}/telegram-link-code", response_model=TelegramLinkCodeOut, dependencies=[Depends(require_auth)])
def create_link_code(subscriber_id: int, db: Session = Depends(get_db)):
    subscriber = db.get(Subscriber, subscriber_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    code = secrets.token_hex(4)
    subscriber.link_code = code
    subscriber.link_code_expires_at = datetime.now(timezone.utc) + LINK_CODE_TTL
    db.commit()

    return TelegramLinkCodeOut(
        code=code,
        deep_link=f"https://t.me/{settings.telegram_bot_username}?start={code}",
        expires_at=subscriber.link_code_expires_at,
    )


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    update = await request.json()
    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")

    if chat_id is None:
        return {"ok": True}

    if text == "/start":
        await send_message(chat_id, WELCOME_TEXT, parse_mode="Markdown")
        return {"ok": True}

    if text.startswith("/start "):
        code = text.removeprefix("/start ").strip()
        subscriber = db.query(Subscriber).filter(Subscriber.link_code == code).first()

        is_expired = subscriber is not None and (
            subscriber.link_code_expires_at is None
            or ensure_aware(subscriber.link_code_expires_at) < datetime.now(timezone.utc)
        )
        if subscriber is None or is_expired:
            await send_message(chat_id, LINK_EXPIRED_TEXT, parse_mode="Markdown")
            return {"ok": True}

        subscriber.telegram_chat_id = chat_id
        subscriber.link_code = None
        subscriber.link_code_expires_at = None
        db.commit()

        await send_message(
            chat_id,
            f"✅ *¡Listo, {subscriber.name}!*\nQuedaste conectado. Te voy a avisar apenas algo que sigues baje de precio.",
            parse_mode="Markdown",
        )
        return {"ok": True}

    if text in ("/ayuda", "/help"):
        await send_message(chat_id, HELP_TEXT, parse_mode="Markdown")
        return {"ok": True}

    if not text:
        return {"ok": True}

    subscriber = db.query(Subscriber).filter(Subscriber.telegram_chat_id == chat_id).first()
    if subscriber is None:
        await send_message(chat_id, NOT_LINKED_TEXT, parse_mode="Markdown")
        return {"ok": True}

    answer = await run_in_threadpool(answer_question, db, text)
    await send_message(chat_id, answer)
    return {"ok": True}
