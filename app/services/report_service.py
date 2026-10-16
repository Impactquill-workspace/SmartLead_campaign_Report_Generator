from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.mailbox_stat import MailboxStat
from app.models.mailbox import Mailbox
from app.models.client import Client
from app.core.logging import logger


class ReportService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def save_mailbox_stats(
        self,
        aggregated_mailboxes: List[Dict[str, Any]],
        period_start: date,
        period_end: date,
    ) -> None:
        """
        Persists mailbox-level statistics to mailbox_stats table.
        Upserts records to satisfy unique constraint (mailbox_id + period_start + period_end).
        """
        if not self.db:
            return

        for stat in aggregated_mailboxes:
            c_smartlead_id = stat.get("client_id")
            mb_email = stat.get("email")
            mb_acc_id = stat.get("mailbox_id")

            # Resolve mailbox in database
            db_mailbox = None
            if mb_acc_id:
                db_mailbox = self.db.query(Mailbox).filter_by(
                    smartlead_email_account_id=str(mb_acc_id)
                ).first()
            if not db_mailbox and mb_email:
                db_mailbox = self.db.query(Mailbox).filter_by(email=mb_email).first()

            # Resolve client
            db_client = self.db.query(Client).filter_by(
                smartlead_client_id=str(c_smartlead_id)
            ).first()

            if not db_mailbox or not db_client:
                continue

            existing_stat = (
                self.db.query(MailboxStat)
                .filter_by(
                    mailbox_id=db_mailbox.id,
                    period_start=period_start,
                    period_end=period_end,
                )
                .first()
            )

            sent_val = int(stat.get("sent", 0))
            bounced_val = int(stat.get("bounced", 0))
            bounce_rate_val = float(stat.get("bounce_rate", 0.0))

            if existing_stat:
                existing_stat.sent = sent_val
                existing_stat.bounced = bounced_val
                existing_stat.bounce_rate = bounce_rate_val
                existing_stat.updated_at = datetime.utcnow()
            else:
                new_stat = MailboxStat(
                    mailbox_id=db_mailbox.id,
                    client_id=db_client.id,
                    period_start=period_start,
                    period_end=period_end,
                    sent=sent_val,
                    bounced=bounced_val,
                    bounce_rate=bounce_rate_val,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                self.db.add(new_stat)

        try:
            self.db.commit()
            logger.info(f"Saved {len(aggregated_mailboxes)} mailbox stat records for period {period_start}..{period_end}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to commit mailbox stats: {e}")

    def save_report_history(
        self,
        period_start: date,
        period_end: date,
        file_path: str,
        total_clients: int,
        total_mailboxes: int,
        total_sent: int,
        total_bounced: int,
    ) -> Report:
        """
        Stores high-level report generation summary into reports table.
        """
        report_record = Report(
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.utcnow(),
            file_path=file_path,
            total_clients=total_clients,
            total_mailboxes=total_mailboxes,
            total_sent=total_sent,
            total_bounced=total_bounced,
        )
        if self.db:
            try:
                self.db.add(report_record)
                self.db.commit()
                self.db.refresh(report_record)
                logger.info(f"Report history recorded with ID={report_record.id}")
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to record report history: {e}")
        return report_record

    def get_latest_report(self) -> Optional[Report]:
        """Retrieves the latest generated report record."""
        if not self.db:
            return None
        return self.db.query(Report).order_by(Report.generated_at.desc()).first()
