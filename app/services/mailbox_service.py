from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.clients.smartlead_client import SmartleadApiClient
from app.models.mailbox import Mailbox
from app.models.campaign import Campaign
from app.models.campaign_mailbox import CampaignMailbox
from app.models.client import Client
from app.utils.email_utils import normalize_email
from app.core.logging import logger


class MailboxService:
    def __init__(self, api_client: SmartleadApiClient, db: Optional[Session] = None):
        self.api_client = api_client
        self.db = db

    async def fetch_campaign_mailboxes(
        self,
        campaign_id: str,
        client_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all email accounts attached to a campaign from Smartlead.
        Synchronizes to Mailbox and CampaignMailbox tables.
        """
        raw_accounts = await self.api_client.get_campaign_email_accounts(campaign_id)
        mailboxes: List[Dict[str, Any]] = []

        for acc in raw_accounts:
            # Smartlead email account records typically have id / email_account_id and from_email / username / email
            acc_id = str(acc.get("id") or acc.get("email_account_id") or "")
            email_addr = (
                acc.get("from_email")
                or acc.get("email")
                or acc.get("username")
                or ""
            )
            norm_email = normalize_email(email_addr)

            if not norm_email and not acc_id:
                continue

            mailboxes.append({
                "email_account_id": acc_id if acc_id else None,
                "email": norm_email,
                "campaign_id": campaign_id,
                "client_id": client_id,
            })

        logger.info(f"Campaign {campaign_id}: Discovered {len(mailboxes)} assigned email accounts/mailboxes.")

        # Database Sync
        if self.db:
            db_campaign = self.db.query(Campaign).filter_by(smartlead_campaign_id=campaign_id).first()
            db_client = (
                self.db.query(Client).filter_by(smartlead_client_id=client_id).first()
                if client_id else None
            )

            for mb in mailboxes:
                # Find existing mailbox by account_id first, then normalized email
                existing_mb = None
                if mb["email_account_id"]:
                    existing_mb = self.db.query(Mailbox).filter_by(
                        smartlead_email_account_id=mb["email_account_id"]
                    ).first()
                if not existing_mb and mb["email"]:
                    existing_mb = self.db.query(Mailbox).filter_by(email=mb["email"]).first()

                if not existing_mb:
                    new_mb = Mailbox(
                        smartlead_email_account_id=mb["email_account_id"],
                        email=mb["email"],
                        client_id=db_client.id if db_client else None,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    self.db.add(new_mb)
                    self.db.flush()
                    mailbox_pk = new_mb.id
                else:
                    mailbox_pk = existing_mb.id
                    if mb["email_account_id"] and not existing_mb.smartlead_email_account_id:
                        existing_mb.smartlead_email_account_id = mb["email_account_id"]
                    if db_client and not existing_mb.client_id:
                        existing_mb.client_id = db_client.id
                    existing_mb.updated_at = datetime.utcnow()

                # Sync campaign_mailboxes association
                if db_campaign and mailbox_pk:
                    assoc = self.db.query(CampaignMailbox).filter_by(
                        campaign_id=db_campaign.id,
                        mailbox_id=mailbox_pk
                    ).first()
                    if not assoc:
                        self.db.add(CampaignMailbox(
                            campaign_id=db_campaign.id,
                            mailbox_id=mailbox_pk,
                            created_at=datetime.utcnow()
                        ))

            try:
                self.db.commit()
            except Exception as dbe:
                self.db.rollback()
                logger.error(f"Failed to commit mailbox synchronization: {dbe}")

        return mailboxes
