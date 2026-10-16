from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.clients.smartlead_client import SmartleadApiClient
from app.services.campaign_service import CampaignService
from app.models.campaign import Campaign

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.get("/", response_model=List[Dict[str, Any]])
async def list_campaigns(
    client_id: Optional[str] = Query(None, description="Filter campaigns by client_id"),
    db: Session = Depends(get_db),
    refresh: bool = False
):
    """
    Returns campaigns, optionally filtered by client_id.
    """
    if refresh:
        service = CampaignService(SmartleadApiClient(), db)
        return await service.fetch_campaigns_for_client(client_id or "default")

    query = db.query(Campaign)
    campaigns = query.all()
    if not campaigns:
        service = CampaignService(SmartleadApiClient(), db)
        return await service.fetch_campaigns_for_client(client_id or "default")

    return [
        {
            "id": c.id,
            "campaign_id": c.smartlead_campaign_id,
            "client_id": c.client_id,
            "name": c.name,
            "status": c.status,
        }
        for c in campaigns
    ]
