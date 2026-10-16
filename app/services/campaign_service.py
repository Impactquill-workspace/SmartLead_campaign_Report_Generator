from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.clients.smartlead_client import SmartleadApiClient
from app.models.campaign import Campaign
from app.models.client import Client
from app.core.logging import logger


class CampaignService:
    def __init__(self, api_client: SmartleadApiClient, db: Optional[Session] = None):
        self.api_client = api_client
        self.db = db

    async def fetch_campaigns_for_client(
        self,
        client_id: str,
        status_filter: Optional[str] = "ACTIVE"
    ) -> List[Dict[str, Any]]:
        """
        Retrieves campaigns for a given client_id, syncs all to database, and filters by status.
        """
        api_filter_id = None if client_id == "default" else client_id
        raw_campaigns = await self.api_client.get_campaigns(client_id=api_filter_id)

        all_campaigns: List[Dict[str, Any]] = []
        for camp in raw_campaigns:
            camp_id = str(camp.get("id") or camp.get("campaign_id") or "")
            camp_name = str(camp.get("name") or f"Campaign {camp_id}")
            camp_status = str(camp.get("status") or "").strip().upper()
            if camp_id:
                all_campaigns.append({
                    "campaign_id": camp_id,
                    "name": camp_name,
                    "status": camp_status or "UNKNOWN",
                    "client_id": client_id,
                })

        logger.info(f"Retrieved {len(all_campaigns)} total campaigns for client_id='{client_id}'.")

        # Database Sync: Persist all discovered campaigns
        if self.db:
            db_client = self.db.query(Client).filter_by(smartlead_client_id=client_id).first()
            db_client_pk = db_client.id if db_client else None

            for c_data in all_campaigns:
                existing = self.db.query(Campaign).filter_by(
                    smartlead_campaign_id=c_data["campaign_id"]
                ).first()
                if not existing:
                    new_camp = Campaign(
                        smartlead_campaign_id=c_data["campaign_id"],
                        client_id=db_client_pk,
                        name=c_data["name"],
                        status=c_data["status"],
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    self.db.add(new_camp)
                else:
                    existing.name = c_data["name"]
                    existing.status = c_data["status"]
                    existing.client_id = db_client_pk
                    existing.updated_at = datetime.utcnow()
            try:
                self.db.commit()
            except Exception as dbe:
                self.db.rollback()
                logger.error(f"Failed to sync campaigns to database: {dbe}")

        # Filter campaigns by status (default: ACTIVE)
        if status_filter and status_filter.strip().upper() != "ALL":
            target_status = status_filter.strip().upper()
            filtered = [c for c in all_campaigns if c["status"] == target_status]
            logger.info(
                f"Filtered campaigns by status '{target_status}': {len(filtered)} of {len(all_campaigns)} campaigns kept."
            )
            return filtered

        return all_campaigns
