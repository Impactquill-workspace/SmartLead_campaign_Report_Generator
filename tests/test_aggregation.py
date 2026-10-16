import pytest
from app.services.aggregation_service import AggregationService


@pytest.fixture
def aggregation_service():
    return AggregationService()


def test_same_mailbox_multiple_campaigns(aggregation_service):
    """
    Test requirement:
    Campaign 1: mailbox1@test.com -> sent=100, bounced=2
    Campaign 2: mailbox1@test.com -> sent=200, bounced=4
    Expected:
    mailbox1@test.com -> sent=300, bounced=6, bounce_rate=2.00%
    """
    client_info = {"client_id": "client_1", "client_name": "Client A"}
    contributions = [
        {
            "campaign_id": "camp_1",
            "campaign_name": "Campaign 1",
            "email": "mailbox1@test.com",
            "email_account_id": "acc_101",
            "sent": 100,
            "bounced": 2,
            "attribution_status": "direct",
        },
        {
            "campaign_id": "camp_2",
            "campaign_name": "Campaign 2",
            "email": "mailbox1@test.com",
            "email_account_id": "acc_101",
            "sent": 200,
            "bounced": 4,
            "attribution_status": "direct",
        },
    ]

    results = aggregation_service.aggregate_campaign_mailboxes(
        client_info=client_info,
        campaign_mailbox_stats=contributions,
    )

    assert len(results) == 1
    mb = results[0]
    assert mb["email"] == "mailbox1@test.com"
    assert mb["mailbox_id"] == "acc_101"
    assert mb["sent"] == 300
    assert mb["bounced"] == 6
    assert mb["bounce_rate"] == 2.00
    assert sorted(mb["campaign_ids"]) == ["camp_1", "camp_2"]


def test_multiple_mailboxes_per_client(aggregation_service):
    """
    Client A with two mailboxes:
    - john@company.com: sent=500, bounced=8 -> 1.60%
    - sales@company.com: sent=700, bounced=14 -> 2.00%
    """
    client_info = {"client_id": "client_a", "client_name": "Client A"}
    contributions = [
        {
            "campaign_id": "camp_10",
            "campaign_name": "Campaign 10",
            "email": "john@company.com",
            "email_account_id": "acc_john",
            "sent": 500,
            "bounced": 8,
            "attribution_status": "direct",
        },
        {
            "campaign_id": "camp_20",
            "campaign_name": "Campaign 20",
            "email": "sales@company.com",
            "email_account_id": "acc_sales",
            "sent": 700,
            "bounced": 14,
            "attribution_status": "direct",
        },
    ]

    results = aggregation_service.aggregate_campaign_mailboxes(
        client_info=client_info,
        campaign_mailbox_stats=contributions,
    )

    assert len(results) == 2
    by_email = {m["email"]: m for m in results}

    assert by_email["john@company.com"]["sent"] == 500
    assert by_email["john@company.com"]["bounced"] == 8
    assert by_email["john@company.com"]["bounce_rate"] == 1.60

    assert by_email["sales@company.com"]["sent"] == 700
    assert by_email["sales@company.com"]["bounced"] == 14
    assert by_email["sales@company.com"]["bounce_rate"] == 2.00


def test_duplicate_campaign_mailbox_entry_prevention(aggregation_service):
    """
    If the exact same campaign and mailbox appears twice in raw contributions,
    it should only be counted once.
    """
    client_info = {"client_id": "c1", "client_name": "Client 1"}
    contributions = [
        {
            "campaign_id": "camp_dup",
            "email": "lead@test.com",
            "email_account_id": "acc_99",
            "sent": 100,
            "bounced": 5,
        },
        {
            "campaign_id": "camp_dup",
            "email": "lead@test.com",
            "email_account_id": "acc_99",
            "sent": 100,
            "bounced": 5,
        },
    ]

    results = aggregation_service.aggregate_campaign_mailboxes(
        client_info=client_info,
        campaign_mailbox_stats=contributions,
    )

    assert len(results) == 1
    assert results[0]["sent"] == 100
    assert results[0]["bounced"] == 5


def test_webhook_event_override(aggregation_service):
    """
    Test that real-time webhook events override or populate granular mailbox stats.
    """
    client_info = {"client_id": "c1", "client_name": "Client 1"}
    contributions = [
        {
            "campaign_id": "camp_multi",
            "email": "webhook_box@test.com",
            "email_account_id": "acc_wh",
            "sent": 0,
            "bounced": 0,
            "attribution_status": "multi_mailbox_limitation",
        }
    ]
    webhook_data = {
        "id:acc_wh": {"sent": 450, "bounced": 9}
    }

    results = aggregation_service.aggregate_campaign_mailboxes(
        client_info=client_info,
        campaign_mailbox_stats=contributions,
        webhook_mailbox_events=webhook_data,
    )

    assert len(results) == 1
    assert results[0]["sent"] == 450
    assert results[0]["bounced"] == 9
    assert results[0]["bounce_rate"] == 2.00
    assert results[0]["attribution_status"] == "webhook_tracked"
