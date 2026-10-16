from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index

from app.core.database import Base


class MailboxEvent(Base):
    __tablename__ = "mailbox_events"

    id = Column(Integer, primary_key=True, index=True)
    smartlead_email_account_id = Column(String(100), nullable=True, index=True)
    mailbox_email = Column(String(255), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # EMAIL_SENT, EMAIL_BOUNCE, EMAIL_BOUNCED
    campaign_id = Column(String(100), nullable=True, index=True)
    lead_id = Column(String(100), nullable=True)
    event_timestamp = Column(DateTime, nullable=False, index=True)
    raw_payload = Column(String(2000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_mailbox_event_acc_type_time", "smartlead_email_account_id", "event_type", "event_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<MailboxEvent(account_id={self.smartlead_email_account_id}, type={self.event_type}, time={self.event_timestamp})>"
