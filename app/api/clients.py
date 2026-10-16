from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.clients.smartlead_client import SmartleadApiClient
from app.services.client_service import ClientService
from app.schemas.client import ClientResponse, ClientSummary
from app.models.client import Client

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=List[Dict[str, Any]])
async def list_clients(
    db: Session = Depends(get_db),
    refresh: bool = False
):
    """
    Returns all registered clients. If refresh=True, re-syncs live from Smartlead.
    """
    if refresh:
        client_service = ClientService(SmartleadApiClient(), db)
        return await client_service.fetch_and_sync_clients()

    db_clients = db.query(Client).all()
    if not db_clients:
        client_service = ClientService(SmartleadApiClient(), db)
        return await client_service.fetch_and_sync_clients()

    return [
        {
            "id": c.id,
            "client_id": c.smartlead_client_id,
            "name": c.name,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in db_clients
    ]
