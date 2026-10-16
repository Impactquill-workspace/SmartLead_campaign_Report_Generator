import pytest
import httpx
import respx
from app.clients.smartlead_client import SmartleadApiClient
from app.clients.smartlead_exceptions import (
    SmartleadAuthError,
    SmartleadRateLimitError,
    SmartleadServerError,
    SmartleadNotFoundError,
)


@pytest.mark.asyncio
async def test_missing_api_key_raises_auth_error():
    client = SmartleadApiClient(api_key="")
    with pytest.raises(SmartleadAuthError, match="SMARTLEAD_API_KEY is not configured"):
        await client.get_campaigns()


@pytest.mark.asyncio
@respx.mock
async def test_api_auth_failure_401():
    """HTTP 401 should immediately raise SmartleadAuthError without infinite retries."""
    respx.get("https://server.smartlead.ai/api/v1/campaigns/").mock(
        return_value=httpx.Response(401, json={"message": "Invalid API key"})
    )

    client = SmartleadApiClient(api_key="invalid_test_key", max_retries=1)
    with pytest.raises(SmartleadAuthError) as exc_info:
        await client.get_campaigns()

    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.response_text


@pytest.mark.asyncio
@respx.mock
async def test_api_rate_limit_429_retry_success():
    """HTTP 429 followed by 200 should be retried and succeed."""
    route = respx.get("https://server.smartlead.ai/api/v1/campaigns/")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0.01"}, json={"error": "Rate limit exceeded"}),
        httpx.Response(200, json=[{"id": 101, "name": "Cold Outreach 1"}]),
    ]

    client = SmartleadApiClient(api_key="valid_key", max_retries=2)
    campaigns = await client.get_campaigns()

    assert len(campaigns) == 1
    assert campaigns[0]["id"] == 101
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_api_rate_limit_429_exhaustion():
    """HTTP 429 exhausting retries raises SmartleadRateLimitError."""
    respx.get("https://server.smartlead.ai/api/v1/campaigns/").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0.01"}, json={"error": "Rate limited"})
    )

    client = SmartleadApiClient(api_key="valid_key", max_retries=1)
    with pytest.raises(SmartleadRateLimitError):
        await client.get_campaigns()


@pytest.mark.asyncio
@respx.mock
async def test_api_500_server_error_retry():
    """HTTP 500 error triggers backoff retry."""
    route = respx.get("https://server.smartlead.ai/api/v1/campaigns/101/email-accounts")
    route.side_effect = [
        httpx.Response(500, json={"error": "Internal Server Error"}),
        httpx.Response(200, json=[{"id": 501, "from_email": "sales@company.com"}]),
    ]

    client = SmartleadApiClient(api_key="valid_key", max_retries=2)
    accounts = await client.get_campaign_email_accounts("101")

    assert len(accounts) == 1
    assert accounts[0]["id"] == 501
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_campaign_analytics_by_date_success():
    """Tests GET /campaigns/{campaign_id}/analytics-by-date."""
    mock_analytics = [
        {"date": "2026-09-21", "sent_count": 50, "bounce_count": 1},
        {"date": "2026-09-22", "sent_count": 75, "bounce_count": 2},
    ]
    respx.get("https://server.smartlead.ai/api/v1/campaigns/202/analytics-by-date").mock(
        return_value=httpx.Response(200, json=mock_analytics)
    )

    client = SmartleadApiClient(api_key="valid_key")
    data = await client.get_campaign_analytics_by_date(
        campaign_id="202",
        start_date="2026-09-21",
        end_date="2026-09-27"
    )

    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["sent_count"] == 50


@pytest.mark.asyncio
async def test_deletion_and_mutations_are_strictly_blocked():
    """Verify that DELETE, POST, PUT, PATCH operations against Smartlead are strictly blocked."""
    from app.clients.smartlead_exceptions import SmartleadApiError
    client = SmartleadApiClient(api_key="valid_key")

    prohibited_methods = ["DELETE", "POST", "PUT", "PATCH"]
    for method in prohibited_methods:
        with pytest.raises(SmartleadApiError, match="strictly READ-ONLY"):
            await client._request(method=method, endpoint="campaigns/123")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_campaign_weekly_stats_tareeqa_1():
    """
    Verifies Tareeqa 1 logic:
    - Unique leads = distinct contacted email addresses
    - Invalid emails = is_bounced is True and sender_bounce is False
    - Sender mailbox issues (sender_bounce is True) are excluded from Invalid Emails
    """
    from datetime import date
    from app.services.analytics_service import AnalyticsService

    respx.get(url__regex=r".*/api/v1/campaigns/999/statistics.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_stats": 5,
                "data": [
                    {"lead_email": "a@example.com", "is_bounced": False, "sender_bounce": False},
                    {"lead_email": "b@example.com", "is_bounced": True, "sender_bounce": True},
                    {"lead_email": "c@example.com", "is_bounced": True, "sender_bounce": False},
                    {"lead_email": "d@example.com", "is_bounced": True, "sender_bounce": False},
                    {"lead_email": "a@example.com", "is_bounced": False, "sender_bounce": False},
                ],
            },
        )
    )

    client = SmartleadApiClient(api_key="valid_key")
    analytics_svc = AnalyticsService(api_client=client)

    stats = await analytics_svc.fetch_campaign_weekly_stats(
        campaign_id="999",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 27),
        sent_count=5,
    )

    assert stats["unique_leads"] == 4  # a, b, c, d
    assert stats["invalid_emails"] == 2  # c, d (b is excluded because sender_bounce=True)

    unique_count = await analytics_svc.fetch_campaign_weekly_unique_leads(
        campaign_id="999",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 27),
        sent_count=5,
    )
    assert unique_count == 4


@pytest.mark.asyncio
@respx.mock
async def test_fetch_campaign_weekly_stats_positive_replies():
    """
    Verifies Positive Replies logic:
    - Categories with sentiment_type == 'positive':
      'Interested', 'Meeting Request', 'Information Request', 'Maybe Later'.
    - Negative or neutral categories (e.g. 'Out Of Office', 'Do Not Contact') are excluded.
    """
    from datetime import date
    from app.services.analytics_service import AnalyticsService

    respx.get(url__regex=r".*/api/v1/campaigns/888/statistics.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_stats": 6,
                "data": [
                    {"lead_email": "lead1@example.com", "lead_category": "Interested", "reply_time": "2026-09-22T10:00:00Z"},
                    {"lead_email": "lead2@example.com", "lead_category": "Meeting Request", "reply_time": "2026-09-22T11:00:00Z"},
                    {"lead_email": "lead3@example.com", "lead_category": "Information Request", "reply_time": "2026-09-22T12:00:00Z"},
                    {"lead_email": "lead4@example.com", "lead_category": "Out Of Office", "reply_time": "2026-09-22T13:00:00Z"},
                    {"lead_email": "lead5@example.com", "lead_category": "Do Not Contact", "reply_time": "2026-09-22T14:00:00Z"},
                    {"lead_email": "lead1@example.com", "lead_category": "Interested", "reply_time": "2026-09-22T15:00:00Z"},
                ],
            },
        )
    )

    client = SmartleadApiClient(api_key="valid_key")
    analytics_svc = AnalyticsService(api_client=client)

    stats = await analytics_svc.fetch_campaign_weekly_stats(
        campaign_id="888",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 27),
        sent_count=6,
    )

    assert stats["unique_leads"] == 5
    assert stats["invalid_emails"] == 0
    assert stats["positive_replies"] == 3  # lead1, lead2, lead3 (lead1 deduplicated)


