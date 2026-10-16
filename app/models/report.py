from datetime import datetime
from sqlalchemy import Column, Integer, Date, DateTime, String

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file_path = Column(String(500), nullable=True)
    total_clients = Column(Integer, default=0, nullable=False)
    total_mailboxes = Column(Integer, default=0, nullable=False)
    total_sent = Column(Integer, default=0, nullable=False)
    total_bounced = Column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, period={self.period_start}..{self.period_end}, file='{self.file_path}')>"
