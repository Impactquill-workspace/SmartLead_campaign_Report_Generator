from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DateRangeFilter(BaseModel):
    start_date: date
    end_date: date


class CampaignAnalyticsByDateItem(BaseModel):
    date: str
    sent_count: int = 0
    bounce_count: int = 0
    open_count: int = 0
    reply_count: int = 0
    unsubscribed_count: int = 0


class MailboxAggregatedStat(BaseModel):
    client_id: str
    client_name: str
    email: str
    mailbox_id: Optional[str] = None
    sent: int = 0
    bounced: int = 0
    bounce_rate: float = 0.0
    attribution_notes: Optional[str] = None
    campaign_ids: List[str] = Field(default_factory=list)


class WebhookEventPayload(BaseModel):
    event: Optional[str] = None
    event_type: Optional[str] = None
    timestamp: Optional[datetime] = None
    campaign_id: Optional[str] = None
    lead_id: Optional[str] = None
    email_account_id: Optional[str] = None
    lead: Optional[Dict[str, Any]] = None
    email: Optional[Dict[str, Any]] = None
