from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class MailboxBase(BaseModel):
    smartlead_email_account_id: Optional[str] = None
    email: str
    client_id: Optional[int] = None


class MailboxCreate(MailboxBase):
    pass


class MailboxResponse(MailboxBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MailboxMetric(BaseModel):
    email: str
    mailbox_id: Optional[str] = None
    sent: int
    bounced: int
    bounce_rate: float
    data_attribution: str = "direct"  # direct, webhook, or campaign_inferred
