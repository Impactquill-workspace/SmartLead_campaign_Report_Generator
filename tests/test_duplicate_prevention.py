import pytest
from app.services.aggregation_service import AggregationService
from app.utils.email_utils import normalize_email


@pytest.fixture
def aggregation_service():
    return AggregationService()


def test_mailbox_key_with_account_id():
    key1 = AggregationService.get_mailbox_key("user@test.com", "12345")
    key2 = AggregationService.get_mailbox_key("USER@TEST.COM", 12345)
    assert key1 == "id:12345"
    assert key2 == "id:12345"
    assert key1 == key2


def test_mailbox_key_fallback_to_email():
    key1 = AggregationService.get_mailbox_key("  Info@Biz.Com  ", None)
    key2 = AggregationService.get_mailbox_key("info@biz.com", "")
    key3 = AggregationService.get_mailbox_key("info@biz.com", "None")

    assert key1 == "email:info@biz.com"
    assert key2 == "email:info@biz.com"
    assert key3 == "email:info@biz.com"


def test_case_insensitive_mailbox_deduplication(aggregation_service):
    """
    Ensures that "Support@Domain.com" and "support@domain.com"
    with the same account ID or fallback email are aggregated as a single mailbox.
    """
    client_info = {"client_id": "c1", "client_name": "Test Client"}
    contributions = [
        {
            "campaign_id": "c1",
            "email": "Support@Domain.com",
            "email_account_id": "acc_supp",
            "sent": 150,
            "bounced": 3,
        },
        {
            "campaign_id": "c2",
            "email": "support@domain.com",
            "email_account_id": "acc_supp",
            "sent": 250,
            "bounced": 5,
        },
    ]

    results = aggregation_service.aggregate_campaign_mailboxes(
        client_info=client_info,
        campaign_mailbox_stats=contributions,
    )

    assert len(results) == 1
    assert results[0]["email"] == "support@domain.com"
    assert results[0]["sent"] == 400
    assert results[0]["bounced"] == 8
    assert results[0]["bounce_rate"] == 2.00
