from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    smartlead_client_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    campaigns = relationship("Campaign", back_populates="client", cascade="all, delete-orphan")
    mailboxes = relationship("Mailbox", back_populates="client")
    mailbox_stats = relationship("MailboxStat", back_populates="client")

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, smartlead_id={self.smartlead_client_id}, name='{self.name}')>"
