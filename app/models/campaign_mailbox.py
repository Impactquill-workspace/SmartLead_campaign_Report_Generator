from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class CampaignMailbox(Base):
    __tablename__ = "campaign_mailboxes"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("campaign_id", "mailbox_id", name="uq_campaign_mailbox"),
    )

    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_mailboxes")
    mailbox = relationship("Mailbox", back_populates="campaign_mailboxes")

    def __repr__(self) -> str:
        return f"<CampaignMailbox(campaign_id={self.campaign_id}, mailbox_id={self.mailbox_id})>"
