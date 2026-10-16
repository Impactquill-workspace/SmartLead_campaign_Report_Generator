import pytest
from app.utils.email_utils import calculate_bounce_rate, normalize_email, is_mimecast_domain


def test_standard_bounce_rate():
    # 500 sent, 10 bounced -> 2.00%
    assert calculate_bounce_rate(sent=500, bounced=10) == 2.00

    # 500 sent, 8 bounced -> 1.60%
    assert calculate_bounce_rate(sent=500, bounced=8) == 1.60

    # 700 sent, 14 bounced -> 2.00%
    assert calculate_bounce_rate(sent=700, bounced=14) == 2.00

    # 350 sent, 4 bounced -> 1.142857... -> 1.14%
    assert calculate_bounce_rate(sent=350, bounced=4) == 1.14


def test_zero_sent():
    # If sent == 0, bounce_rate must be 0.0
    assert calculate_bounce_rate(sent=0, bounced=0) == 0.0
    assert calculate_bounce_rate(sent=0, bounced=5) == 0.0


def test_zero_bounced():
    assert calculate_bounce_rate(sent=1000, bounced=0) == 0.0


def test_negative_values_handling():
    # Negative values must be clamped to 0
    assert calculate_bounce_rate(sent=-100, bounced=5) == 0.0
    assert calculate_bounce_rate(sent=100, bounced=-5) == 0.0


def test_bounced_exceeds_sent():
    # Upstream data anomaly where bounced > sent
    rate = calculate_bounce_rate(sent=10, bounced=15)
    assert rate == 150.00


def test_email_normalization():
    assert normalize_email("  Sales@Company.COM  ") == "sales@company.com"
    assert normalize_email("User.Name+Tag@Domain.Org") == "user.name+tag@domain.org"
    assert normalize_email("") == ""


def test_mimecast_domain_detection():
    # Empty string handling
    assert is_mimecast_domain("") is False
    assert is_mimecast_domain(None) is False

    # Cache usage
    custom_cache = {"example.com": True, "nonmimecast.com": False}
    assert is_mimecast_domain("example.com", cache=custom_cache) is True
    assert is_mimecast_domain("nonmimecast.com", cache=custom_cache) is False

    # Live domains
    assert is_mimecast_domain("google.com") is False
    assert is_mimecast_domain("microsoft.com") is False
    assert is_mimecast_domain("thrivenetworks.com") is True
