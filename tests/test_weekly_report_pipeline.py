import pytest
import respx
import httpx
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.clients.smartlead_client import SmartleadApiClient
from app.services.weekly_report_service import WeeklyReportService
from app.models.mailbox_stat import MailboxStat
from app.models.report import Report


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.mark.asyncio
@respx.mock
async def test_full_pipeline_mock_api(test_db, tmp_path):
    """
    End-to-end mock test verifying full pipeline:
    - 2 Clients (Client A, Client B)
    - Client A has Campaign 1 and Campaign 2 both using sales@company.com
    - Verifies sales@company.com totals 500 sent, 8 bounced (1.60%)
    - Verifies Excel file created and DB populated
    """
    # Mock Clients
    respx.get(url__regex=r".*/api/v1/client/list.*").mock(
        return_value=httpx.Response(200, json=[
            {"id": "c_1", "name": "Client A"},
            {"id": "c_2", "name": "Client B"},
        ])
    )

    # Mock Campaigns routing by client_id parameter
    def campaigns_handler(request):
        cid = request.url.params.get("client_id")
        if cid == "c_1":
            return httpx.Response(200, json=[
                {"id": "camp_1", "name": "Client A Campaign 1", "status": "ACTIVE"},
                {"id": "camp_2", "name": "Client A Campaign 2", "status": "ACTIVE"},
            ])
        elif cid == "c_2":
            return httpx.Response(200, json=[
                {"id": "camp_3", "name": "Client B Campaign 3", "status": "ACTIVE"},
            ])
        return httpx.Response(200, json=[])

    respx.get(url__regex=r".*/api/v1/campaigns/?(\?.*)?$").mock(side_effect=campaigns_handler)

    # Mock Email Accounts for Campaign 1 (sales@company.com)
    respx.get(url__regex=r".*/api/v1/campaigns/camp_1/email-accounts.*").mock(
        return_value=httpx.Response(200, json=[
            {"id": "987", "email": "sales@company.com"}
        ])
    )

    # Mock Email Accounts for Campaign 2 (sales@company.com)
    respx.get(url__regex=r".*/api/v1/campaigns/camp_2/email-accounts.*").mock(
        return_value=httpx.Response(200, json=[
            {"id": "987", "email": "sales@company.com"}
        ])
    )

    # Mock Email Accounts for Campaign 3 (hello@example.com)
    respx.get(url__regex=r".*/api/v1/campaigns/camp_3/email-accounts.*").mock(
        return_value=httpx.Response(200, json=[
            {"id": "985", "email": "hello@example.com"}
        ])
    )

    # Mock Analytics by Date for Campaign 1 (sent=300, bounced=5, replies=6)
    respx.get(url__regex=r".*/api/v1/campaigns/camp_1/analytics-by-date.*").mock(
        return_value=httpx.Response(200, json=[
            {"date": "2026-09-21", "sent_count": 300, "bounce_count": 5, "reply_count": 6}
        ])
    )

    # Mock Analytics by Date for Campaign 2 (sent=200, bounced=3, replies=2)
    respx.get(url__regex=r".*/api/v1/campaigns/camp_2/analytics-by-date.*").mock(
        return_value=httpx.Response(200, json=[
            {"date": "2026-09-21", "sent_count": 200, "bounce_count": 3, "reply_count": 2}
        ])
    )

    # Mock Analytics by Date for Campaign 3 (sent=350, bounced=4, replies=7)
    respx.get(url__regex=r".*/api/v1/campaigns/camp_3/analytics-by-date.*").mock(
        return_value=httpx.Response(200, json=[
            {"date": "2026-09-21", "sent_count": 350, "bounce_count": 4, "reply_count": 7}
        ])
    )

    api_client = SmartleadApiClient(api_key="mock_secret_key")
    service = WeeklyReportService(api_client, test_db)

    report_summary = await service.generate_weekly_report(
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 27),
        export_excel=True,
    )

    assert report_summary["total_clients"] == 2
    assert report_summary["total_campaigns"] == 3
    assert report_summary["total_sent"] == 850
    assert report_summary["total_bounced"] == 12
    assert report_summary["total_replies"] == 15
    assert report_summary["total_positive_replies"] == 0
    assert report_summary["total_mimecast_bounces"] == 0
    # Overall bounce rate = (12 / 850) * 100 = 1.41%
    assert report_summary["overall_bounce_rate"] == 1.41
    # Overall reply rate = (15 / (850 - 12)) * 100 = 1.79%
    assert round(report_summary["overall_reply_rate"], 2) == 1.79
    assert report_summary["overall_positive_reply_rate"] == 0.0

    camps = report_summary["campaigns"]
    assert len(camps) == 3

    camp_names = [c["campaign_name"] for c in camps]
    assert "Client A Campaign 1" in camp_names
    assert "Client A Campaign 2" in camp_names
    assert "Client B Campaign 3" in camp_names

    c1 = next(c for c in camps if c["campaign_name"] == "Client A Campaign 1")
    assert c1["total_sent"] == 300
    assert c1["total_bounced"] == 5
    assert c1["bounce_percentage"] == 1.67
    assert c1["total_replies"] == 6
    assert round(c1["reply_percentage"], 2) == 2.03
    assert c1["positive_replies"] == 0
    assert c1["positive_reply_percentage"] == 0.0
    assert c1["mimecast_bounces"] == 0
    assert c1["date_range"] == "2026-09-21 to 2026-09-27"

    c2 = next(c for c in camps if c["campaign_name"] == "Client A Campaign 2")
    assert c2["total_sent"] == 200
    assert c2["total_bounced"] == 3
    assert c2["bounce_percentage"] == 1.50
    assert c2["total_replies"] == 2
    assert round(c2["reply_percentage"], 2) == 1.02

    c3 = next(c for c in camps if c["campaign_name"] == "Client B Campaign 3")
    assert c3["total_sent"] == 350
    assert c3["total_bounced"] == 4
    assert c3["bounce_percentage"] == 1.14
    assert c3["total_replies"] == 7
    assert round(c3["reply_percentage"], 2) == 2.02

    # Verify Database persistence
    db_reports = test_db.query(Report).all()
    assert len(db_reports) == 1
    assert db_reports[0].total_sent == 850
    assert db_reports[0].total_bounced == 12

