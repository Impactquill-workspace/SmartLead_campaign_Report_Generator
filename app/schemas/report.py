from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field


class ReportMailboxItem(BaseModel):
    email: str
    mailbox_id: Optional[str] = None
    sent: int = 0
    bounced: int = 0
    bounce_rate: float = 0.0
    attribution_status: str = "direct"  # direct, webhook_tracked, or limitation_noted


class CampaignReportItem(BaseModel):
    date_range: Optional[str] = None
    campaign_id: Optional[Union[str, int]] = None
    campaign_name: str
    total_leads: int = 0
    total_sent: int = 0
    total_bounced: int = 0
    bounce_percentage: float = 0.0
    total_blocked: int = 0
    total_invalid: int = 0
    total_replies: int = 0
    reply_percentage: float = 0.0
    positive_replies: int = 0
    positive_reply_percentage: float = 0.0
    mimecast_bounces: int = 0
    client_id: Optional[Union[str, int]] = None
    client_name: Optional[str] = None
    status: Optional[str] = None


class ReportClientItem(BaseModel):
    client_id: str
    client_name: str
    mailboxes: List[ReportMailboxItem] = Field(default_factory=list)


class WeeklyReportResponse(BaseModel):
    period_start: str
    period_end: str
    date_range_str: Optional[str] = None
    status_filter: Optional[str] = "ACTIVE"
    generated_at: Optional[str] = None
    total_clients: int = 0
    total_campaigns: int = 0
    total_mailboxes: int = 0
    total_leads: int = 0
    total_sent: int = 0
    total_bounced: int = 0
    total_invalid: int = 0
    total_blocked: int = 0
    total_replies: int = 0
    total_positive_replies: int = 0
    total_mimecast_bounces: int = 0
    overall_bounce_rate: float = 0.0
    overall_reply_rate: float = 0.0
    overall_positive_reply_rate: float = 0.0
    file_path: Optional[str] = None
    campaigns: List[CampaignReportItem] = Field(default_factory=list)
    clients: List[Any] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    start_date: Optional[str] = Field(default=None, description="Start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(default=None, description="End date in YYYY-MM-DD format")
    status: Optional[str] = Field(default="ACTIVE", description="Campaign status filter")
    all_time: Optional[bool] = Field(default=False, description="Fetch all time stats")
    force_refresh: bool = Field(default=False, description="Whether to re-fetch live Smartlead data")


class GenerateReportResponse(BaseModel):
    status: str
    message: str
    report: WeeklyReportResponse
