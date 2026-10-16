from typing import Dict, Any, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.clients.smartlead_client import SmartleadApiClient
from app.services.analytics_service import AnalyticsService
from app.utils.date_utils import parse_date_range

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/campaign/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    Retrieves campaign analytics for a specified date range.
    """
    s_date, e_date = parse_date_range(start_date, end_date)
    analytics_svc = AnalyticsService(SmartleadApiClient(), db)
    stats = await analytics_svc.fetch_campaign_date_analytics(
        campaign_id=campaign_id,
        start_date=s_date,
        end_date=e_date,
    )
    return {
        "campaign_id": campaign_id,
        "start_date": s_date.isoformat(),
        "end_date": e_date.isoformat(),
        "sent": stats["sent"],
        "bounced": stats["bounced"],
    }
