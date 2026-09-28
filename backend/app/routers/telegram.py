import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.config import settings
from app.db import get_db
from app.models import Subscriber
from app.schemas import TelegramLinkCodeOut
from app.services.telegram_client import send_message
from app.utils import ensure_aware

router = APIRouter(tags=["telegram"])

LINK_CODE_TTL = timedelta(minutes=15)


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
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not text.startswith("/start ") or chat_id is None:
        return {"ok": True}

    code = text.removeprefix("/start ").strip()
    subscriber = (
        db.query(Subscriber)
        .filter(Subscriber.link_code == code)
        .first()
    )
    if subscriber is None or subscriber.link_code_expires_at is None:
        return {"ok": True}

    if ensure_aware(subscriber.link_code_expires_at) < datetime.now(timezone.utc):
        return {"ok": True}

    subscriber.telegram_chat_id = chat_id
    subscriber.link_code = None
    subscriber.link_code_expires_at = None
    db.commit()

    await send_message(chat_id, f"✅ Listo {subscriber.name}, quedaste conectado a Cyber Ofertas.")
    return {"ok": True}
