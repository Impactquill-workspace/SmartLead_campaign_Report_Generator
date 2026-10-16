from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    smartlead_client_id: str
    name: str


class ClientCreate(ClientBase):
    pass


class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientSummary(BaseModel):
    client_id: str
    client_name: str
    total_mailboxes: int
    total_sent: int
    total_bounced: int
    overall_bounce_rate: float
