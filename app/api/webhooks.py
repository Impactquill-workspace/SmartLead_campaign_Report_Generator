from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import MailboxEvent
from app.core.logging import logger
from app.utils.email_utils import normalize_email

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/smartlead")
async def receive_smartlead_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Ingests official Smartlead webhook events (e.g., EMAIL_SENT, EMAIL_BOUNCE, EMAIL_BOUNCED).
    Stores event for high-accuracy mailbox-level historical attribution.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event") or payload.get("event_type") or "UNKNOWN"
    acc_id = payload.get("email_account_id") or payload.get("from_email_id")
    lead_data = payload.get("lead") or {}
    email_data = payload.get("email") or {}
    from_email = (
        payload.get("from_email")
        or email_data.get("from_email")
        or payload.get("email_account_email")
        or ""
    )
    camp_id = payload.get("campaign_id") or payload.get("email_campaign_id")
    lead_id = payload.get("lead_id") or lead_data.get("id")

    # Timestamp parsing
    ts_str = payload.get("timestamp") or payload.get("created_at")
    event_time = datetime.utcnow()
    if ts_str:
        try:
            event_time = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        except Exception:
            event_time = datetime.utcnow()

    event_record = MailboxEvent(
        smartlead_email_account_id=str(acc_id) if acc_id else None,
        mailbox_email=normalize_email(from_email) if from_email else None,
        event_type=str(event_type).upper(),
        campaign_id=str(camp_id) if camp_id else None,
        lead_id=str(lead_id) if lead_id else None,
        event_timestamp=event_time,
        raw_payload=str(payload)[:1900],
        created_at=datetime.utcnow(),
    )
    db.add(event_record)
    try:
        db.commit()
        logger.info(f"Webhook event '{event_type}' recorded for account {acc_id}")
    except Exception as dbe:
        db.rollback()
        logger.error(f"Failed to record webhook event: {dbe}")
        raise HTTPException(status_code=500, detail="Database error saving webhook event")

    return {"status": "success", "message": "Event recorded"}
