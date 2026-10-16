from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class Mailbox(Base):
    __tablename__ = "mailboxes"

    id = Column(Integer, primary_key=True, index=True)
    smartlead_email_account_id = Column(String(100), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="mailboxes")
    campaign_mailboxes = relationship("CampaignMailbox", back_populates="mailbox", cascade="all, delete-orphan")
    stats = relationship("MailboxStat", back_populates="mailbox", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Mailbox(id={self.id}, smartlead_id={self.smartlead_email_account_id}, email='{self.email}')>"
