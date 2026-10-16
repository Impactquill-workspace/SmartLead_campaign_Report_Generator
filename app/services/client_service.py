from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.clients.smartlead_client import SmartleadApiClient
from app.models.client import Client
from app.core.logging import logger


class ClientService:
    def __init__(self, api_client: SmartleadApiClient, db: Optional[Session] = None):
        self.api_client = api_client
        self.db = db

    async def fetch_and_sync_clients(self) -> List[Dict[str, Any]]:
        """
        Fetches clients from Smartlead API and syncs to database if a DB session is provided.
        Handles both agency accounts with multiple clients and single accounts with a default client.
        """
        raw_clients = []
        try:
            raw_clients = await self.api_client.get_clients()
            logger.info(f"Retrieved {len(raw_clients)} clients from Smartlead API.")
        except Exception as e:
            logger.warning(f"Could not fetch clients from /client/list: {e}. Falling back to default workspace client.")

        client_list: List[Dict[str, Any]] = []

        if raw_clients:
            for item in raw_clients:
                c_id = str(item.get("id") or item.get("client_id") or "")
                c_name = str(item.get("name") or item.get("company_name") or f"Client {c_id}")
                if c_id:
                    client_list.append({"client_id": c_id, "name": c_name})
        else:
            # Single workspace / Default client
            client_list.append({"client_id": "default", "name": "Primary Workspace"})

        # Sync to database if session provided
        if self.db:
            for c_data in client_list:
                existing = self.db.query(Client).filter_by(smartlead_client_id=c_data["client_id"]).first()
                if not existing:
                    new_client = Client(
                        smartlead_client_id=c_data["client_id"],
                        name=c_data["name"],
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    self.db.add(new_client)
                else:
                    existing.name = c_data["name"]
                    existing.updated_at = datetime.utcnow()
            try:
                self.db.commit()
            except Exception as dbe:
                self.db.rollback()
                logger.error(f"Failed to commit client sync to database: {dbe}")

        return client_list
