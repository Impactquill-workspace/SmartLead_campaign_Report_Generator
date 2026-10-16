import pytest
import respx
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.clients.smartlead_client import SmartleadApiClient
from app.services.weekly_report_service import WeeklyReportService


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
async def test_all_time_report_pipeline(test_db, tmp_path):
    """
    Verifies all-time reporting pipeline correctly fetches from /campaigns/{id}/analytics
    and outputs 5 columns with 'All Time' as the Date Range.
    """
    # Mock Clients
    respx.get(url__regex=r".*/api/v1/client/list.*").mock(
        return_value=httpx.Response(200, json=[
            {"id": "c_1", "name": "Primary Client"},
        ])
    )

    # Mock Campaigns
    respx.get(url__regex=r".*/api/v1/campaigns/?(\?.*)?$").mock(
        return_value=httpx.Response(200, json=[
            {"id": "1001", "name": "Active Alpha Campaign", "status": "ACTIVE"},
            {"id": "1002", "name": "Active Beta Campaign", "status": "ACTIVE"},
        ])
    )

    # Mock Top-Level /campaigns/{id}/analytics for Campaign 1001
    respx.get(url__regex=r".*/api/v1/campaigns/1001/analytics.*").mock(
        return_value=httpx.Response(200, json={
            "id": 1001,
            "sent_count": "1500",
            "bounce_count": "75",
        })
    )

    # Mock Top-Level /campaigns/{id}/analytics for Campaign 1002
    respx.get(url__regex=r".*/api/v1/campaigns/1002/analytics.*").mock(
        return_value=httpx.Response(200, json={
            "id": 1002,
            "sent_count": "500",
            "bounce_count": "10",
        })
    )

    api_client = SmartleadApiClient(api_key="mock_secret_key")
    service = WeeklyReportService(api_client, test_db)

    report = await service.generate_weekly_report(
        export_excel=False,
        status_filter="ACTIVE",
        all_time=True,
    )

    assert report["total_campaigns"] == 2
    assert report["total_sent"] == 2000
    assert report["total_bounced"] == 85
    assert report["overall_bounce_rate"] == 4.25
    assert report["date_range_str"] == "All Time"

    camp1 = next(c for c in report["campaigns"] if c["campaign_id"] == "1001")
    assert camp1["date_range"] == "All Time"
    assert camp1["total_sent"] == 1500
    assert camp1["total_bounced"] == 75
    assert camp1["bounce_percentage"] == 5.0

    await api_client.aclose()
