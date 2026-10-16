from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.mailbox import Mailbox

router = APIRouter(prefix="/mailboxes", tags=["Mailboxes"])


@router.get("/", response_model=List[Dict[str, Any]])
def list_mailboxes(
    client_id: Optional[int] = Query(None, description="Filter by client database ID"),
    db: Session = Depends(get_db),
):
    """
    Returns discovered and synchronized mailboxes from the database.
    """
    query = db.query(Mailbox)
    if client_id is not None:
        query = query.filter(Mailbox.client_id == client_id)

    mailboxes = query.all()
    return [
        {
            "id": mb.id,
            "smartlead_email_account_id": mb.smartlead_email_account_id,
            "email": mb.email,
            "client_id": mb.client_id,
            "created_at": mb.created_at.isoformat() if mb.created_at else None,
        }
        for mb in mailboxes
    ]
