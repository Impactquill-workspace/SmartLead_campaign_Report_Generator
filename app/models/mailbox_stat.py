from datetime import datetime
from sqlalchemy import Column, Integer, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class MailboxStat(Base):
    __tablename__ = "mailbox_stats"

    id = Column(Integer, primary_key=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    sent = Column(Integer, default=0, nullable=False)
    bounced = Column(Integer, default=0, nullable=False)
    bounce_rate = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("mailbox_id", "period_start", "period_end", name="uq_mailbox_stat_period"),
    )

    # Relationships
    mailbox = relationship("Mailbox", back_populates="stats")
    client = relationship("Client", back_populates="mailbox_stats")

    def __repr__(self) -> str:
        return (
            f"<MailboxStat(mailbox_id={self.mailbox_id}, period={self.period_start}..{self.period_end}, "
            f"sent={self.sent}, bounced={self.bounced}, rate={self.bounce_rate:.2f}%)>"
        )
