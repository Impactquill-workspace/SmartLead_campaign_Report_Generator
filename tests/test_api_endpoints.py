import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.core.database import init_db

init_db()
client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "smartlead_api_configured" in data


def test_dashboard_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Smartlead Active Campaign" in resp.text


def test_webhook_ingestion():
    payload = {
        "event": "EMAIL_BOUNCED",
        "email_account_id": "acc_999",
        "from_email": "sender@company.com",
        "campaign_id": "camp_1",
        "lead_id": "lead_123",
        "timestamp": "2026-09-21T10:00:00Z"
    }
    resp = client.post("/api/webhooks/smartlead", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@patch("app.services.weekly_report_service.WeeklyReportService.generate_weekly_report")
def test_get_weekly_report_endpoint(mock_gen):
    mock_gen.return_value = {
        "period_start": "2026-09-21",
        "period_end": "2026-09-27",
        "generated_at": "2026-09-30 12:00:00 UTC",
        "total_clients": 1,
        "total_mailboxes": 1,
        "total_sent": 500,
        "total_bounced": 8,
        "overall_bounce_rate": 1.60,
        "file_path": None,
        "clients": [
            {
                "client_id": "123",
                "client_name": "Client A",
                "mailboxes": [
                    {
                        "email": "sales@abc.com",
                        "mailbox_id": "987",
                        "sent": 500,
                        "bounced": 8,
                        "bounce_rate": 1.60,
                        "attribution_status": "direct"
                    }
                ]
            }
        ]
    }

    resp = client.get("/api/reports/weekly?start_date=2026-09-21&end_date=2026-09-27")
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_start"] == "2026-09-21"
    assert data["total_sent"] == 500
    assert data["clients"][0]["client_name"] == "Client A"
    assert data["clients"][0]["mailboxes"][0]["email"] == "sales@abc.com"
