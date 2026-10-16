from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.clients.smartlead_client import SmartleadApiClient
from app.models.event import MailboxEvent
from app.utils.email_utils import is_mimecast_domain
from app.core.logging import logger


class AnalyticsService:
    def __init__(self, api_client: SmartleadApiClient, db: Optional[Session] = None):
        self.api_client = api_client
        self.db = db

    async def fetch_campaign_all_time_analytics(
        self,
        campaign_id: str,
        use_contacted: bool = True,
    ) -> Dict[str, int]:
        """
        Retrieves campaign all-time analytics from Smartlead.
        Per user instruction: 'contacted' (unique_sent_count) means Total sent.
        """
        total_sent = 0
        total_bounced = 0
        total_replied = 0
        contacted = 0

        try:
            raw_data = await self.api_client.get_campaign_analytics(campaign_id=campaign_id)
            if isinstance(raw_data, dict):
                raw_sent = int(raw_data.get("sent_count") or raw_data.get("sent") or 0)
                contacted = int(raw_data.get("unique_sent_count") or raw_data.get("contacted") or 0)
                total_bounced = int(raw_data.get("bounce_count") or raw_data.get("bounced") or 0)
                total_replied = int(raw_data.get("reply_count") or 0)

                if use_contacted:
                    total_sent = contacted if contacted > 0 else raw_sent
                else:
                    total_sent = raw_sent
        except Exception as e:
            logger.warning(f"Failed to fetch all-time analytics for Campaign {campaign_id}: {e}")

        logger.debug(f"Campaign {campaign_id} All-Time: Sent(Contacted)={total_sent}, Bounced={total_bounced}, Replied={total_replied}")
        return {
            "sent": max(0, total_sent),
            "bounced": max(0, total_bounced),
            "contacted": max(0, contacted),
            "replied": max(0, total_replied),
        }

    async def fetch_campaign_date_analytics(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
        use_contacted: bool = True,
    ) -> Dict[str, int]:
        """
        Retrieves campaign date-range analytics from Smartlead.
        Endpoint: GET /campaigns/{campaign_id}/analytics-by-date

        Verified Smartlead API field meanings (cross-checked via /statistics endpoint):
          - sent_count   = total emails sent in the period (including follow-up sequences).
                           Used as 'Total sent' in the report.
          - bounce_count = exact number of unique leads who bounced in the period.
                           Verified to match /statistics is_bounced unique lead count exactly.
                           Used directly as 'Total bounce no' — NO scaling needed.
          - reply_count  = exact number of actual human replies received in the period.
          - Bounce %     = bounce_count / total_leads × 100
        """
        logger.info(f"Fetching analytics for Campaign {campaign_id} ({start_date} to {end_date})...")
        total_sent = 0
        total_bounced = 0
        total_blocked = 0
        total_replied = 0

        try:
            raw_data = await self.api_client.get_campaign_analytics_by_date(
                campaign_id=campaign_id,
                start_date=start_date,
                end_date=end_date,
            )

            def _extract(stat: Dict[str, Any]):
                sent    = int(stat.get("sent_count") or stat.get("sent") or 0)
                bounce  = int(stat.get("bounce_count") or stat.get("bounced") or 0)
                blocked = int(stat.get("block_count") or stat.get("blocked") or 0)
                replied = int(stat.get("reply_count") or 0)
                return sent, bounce, blocked, replied

            if isinstance(raw_data, list):
                for day_stat in raw_data:
                    s, b, blk, r = _extract(day_stat)
                    total_sent    += s
                    total_bounced += b
                    total_blocked += blk
                    total_replied += r
            elif isinstance(raw_data, dict):
                if "data" in raw_data and isinstance(raw_data["data"], list):
                    for day_stat in raw_data["data"]:
                        s, b, blk, r = _extract(day_stat)
                        total_sent    += s
                        total_bounced += b
                        total_blocked += blk
                        total_replied += r
                else:
                    total_sent    = int(raw_data.get("sent_count") or raw_data.get("total_sent") or raw_data.get("sent") or 0)
                    total_bounced = int(raw_data.get("bounce_count") or raw_data.get("total_bounced") or raw_data.get("bounced") or 0)
                    total_blocked = int(raw_data.get("block_count") or raw_data.get("blocked") or 0)
                    total_replied = int(raw_data.get("reply_count") or 0)

        except Exception as e:
            logger.warning(f"Failed to fetch date analytics for Campaign {campaign_id}: {e}")

        logger.info(f"Campaign {campaign_id} Analytics: Sent={total_sent}, Bounced={total_bounced}, Blocked={total_blocked}, Replied={total_replied}")
        return {
            "sent": max(0, total_sent),
            "bounced": max(0, total_bounced),
            "blocked": max(0, total_blocked),
            "replied": max(0, total_replied),
        }

    POSITIVE_SENTIMENT_CATEGORIES = {
        "interested",
        "meeting request",
        "information request",
        "maybe later",
    }

    async def fetch_campaign_weekly_stats(
        self,
        campaign_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sent_count: int = 0,
    ) -> Dict[str, int]:
        """
        Retrieves the exact number of unique leads contacted, invalid recipient emails,
        positive replies, and Mimecast bounces during the given window using GET /campaigns/{campaign_id}/statistics.

        Tareeqa 1 (Invalid Emails):
        In Smartlead, recipient-side bounces (undeliverable / invalid recipient mailbox / 5xx mailbox not found)
        are flagged with `is_bounced = True` and `sender_bounce = False`.

        Mimecast Bounces:
        Bounced leads whose recipient domain DNS MX record points to Mimecast (*.mimecast.com).

        Positive Replies:
        Identified by Smartlead category sentiment_type == 'positive':
        'Interested', 'Meeting Request', 'Information Request', 'Maybe Later'.
        """
        if sent_count == 0:
            return {"unique_leads": 0, "invalid_emails": 0, "positive_replies": 0, "mimecast_bounces": 0}

        start_iso = f"{start_date.isoformat()}T00:00:00.000Z" if start_date else None
        end_iso = f"{end_date.isoformat()}T23:59:59.999Z" if end_date else None

        unique_leads = set()
        invalid_lead_emails = set()
        invalid_fallback_count = 0
        positive_lead_emails = set()
        positive_fallback_count = 0
        mimecast_bounced_emails = set()
        mimecast_fallback_count = 0
        domain_cache = {}
        offset = 0
        limit = 1000

        try:
            while True:
                req_params = {"limit": limit, "offset": offset}
                if start_iso:
                    req_params["sent_time_start_date"] = start_iso
                if end_iso:
                    req_params["sent_time_end_date"] = end_iso

                stat_resp = await self.api_client.get_campaign_statistics(
                    campaign_id=campaign_id,
                    **req_params
                )
                records = stat_resp.get("data", [])
                if not records:
                    break
                for r in records:
                    email = r.get("lead_email")
                    clean_email = email.strip().lower() if email else None
                    if clean_email:
                        unique_leads.add(clean_email)

                    # Tareeqa 1: Recipient-side invalid bounce (is_bounced = True and sender_bounce = False)
                    if r.get("is_bounced"):
                        if not r.get("sender_bounce"):
                            if clean_email:
                                invalid_lead_emails.add(clean_email)
                            else:
                                invalid_fallback_count += 1

                        # Mimecast Bounce Filter: domain DNS MX points to Mimecast
                        if clean_email and "@" in clean_email:
                            domain = clean_email.split("@")[1]
                            if is_mimecast_domain(domain, cache=domain_cache):
                                mimecast_bounced_emails.add(clean_email)
                        elif not clean_email and "mimecast" in str(r.get("email_message") or "").lower():
                            mimecast_fallback_count += 1

                    # Positive Replies: category marked with positive sentiment
                    cat = (r.get("lead_category") or "").strip().lower()
                    if cat in self.POSITIVE_SENTIMENT_CATEGORIES:
                        if clean_email:
                            positive_lead_emails.add(clean_email)
                        else:
                            positive_fallback_count += 1

                total_stats = int(stat_resp.get("total_stats") or 0)
                offset += limit
                if offset >= total_stats or len(records) < limit:
                    break
        except Exception as e:
            logger.warning(f"Failed to fetch weekly stats for Campaign {campaign_id}: {e}")

        invalid_count = len(invalid_lead_emails) + invalid_fallback_count
        positive_count = len(positive_lead_emails) + positive_fallback_count
        mimecast_count = len(mimecast_bounced_emails) + mimecast_fallback_count
        logger.debug(
            f"Campaign {campaign_id} Weekly Unique Leads: {len(unique_leads)}, Invalid Emails: {invalid_count}, "
            f"Positive Replies: {positive_count}, Mimecast Bounces: {mimecast_count}"
        )
        return {
            "unique_leads": len(unique_leads),
            "invalid_emails": invalid_count,
            "positive_replies": positive_count,
            "mimecast_bounces": mimecast_count,
        }

    async def fetch_campaign_weekly_unique_leads(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
        sent_count: int = 0,
    ) -> int:
        """
        Retrieves the exact number of unique leads who received at least one email
        during the given date window using the GET /campaigns/{campaign_id}/statistics endpoint.
        """
        stats = await self.fetch_campaign_weekly_stats(
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date,
            sent_count=sent_count,
        )
        return stats["unique_leads"]

    async def fetch_campaign_mailbox_stats(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Dict[str, int]]:
        """
        Retrieves mailbox-level stats (sent, bounced) for a campaign by date range
        using Smartlead's official GET /campaigns/{campaign_id}/mailbox-statistics endpoint.
        Returns a dict mapping:
            f"id:{email_account_id}" -> {"sent": count, "bounced": count}
            f"email:{normalized_email}" -> {"sent": count, "bounced": count}
        """
        logger.info(f"Fetching mailbox statistics for Campaign {campaign_id} ({start_date} to {end_date})...")
        mailbox_stats_map: Dict[str, Dict[str, int]] = {}

        try:
            raw_stats = await self.api_client.get_all_campaign_mailbox_statistics(
                campaign_id=campaign_id,
                start_date=start_date,
                end_date=end_date,
            )

            for item in raw_stats:
                acc_id = str(item.get("email_account_id") or "")
                email = str(item.get("from_email") or item.get("email") or "").strip().lower()
                sent = int(item.get("sent_count") or item.get("sent") or 0)
                bounced = int(item.get("bounce_count") or item.get("bounced") or 0)

                stat_entry = {"sent": max(0, sent), "bounced": max(0, bounced)}

                if acc_id:
                    mailbox_stats_map[f"id:{acc_id}"] = stat_entry
                if email:
                    mailbox_stats_map[f"email:{email}"] = stat_entry

            total_s = sum(x.get("sent_count", 0) for x in raw_stats)
            total_b = sum(x.get("bounce_count", 0) for x in raw_stats)
            logger.info(
                f"Campaign {campaign_id} Mailbox Stats: Received {len(raw_stats)} records "
                f"(Sent: {total_s}, Bounced: {total_b})"
            )
        except Exception as e:
            logger.warning(f"Could not fetch mailbox statistics for Campaign {campaign_id}: {e}")

        return mailbox_stats_map

    def get_webhook_mailbox_stats_for_period(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Dict[str, int]]:
        """
        Queries database for any granular mailbox events logged via webhooks during the period.
        Returns a dictionary mapping:
        f"id:{email_account_id}" -> {"sent": count, "bounced": count}
        """
        if not self.db:
            return {}

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        results: Dict[str, Dict[str, int]] = {}

        try:
            records = (
                self.db.query(
                    MailboxEvent.smartlead_email_account_id,
                    MailboxEvent.mailbox_email,
                    MailboxEvent.event_type,
                    func.count(MailboxEvent.id).label("cnt")
                )
                .filter(
                    MailboxEvent.event_timestamp >= start_dt,
                    MailboxEvent.event_timestamp <= end_dt
                )
                .group_by(
                    MailboxEvent.smartlead_email_account_id,
                    MailboxEvent.mailbox_email,
                    MailboxEvent.event_type
                )
                .all()
            )

            for acc_id, mb_email, ev_type, cnt in records:
                key = f"id:{acc_id}" if acc_id else f"email:{mb_email}"
                if key not in results:
                    results[key] = {"sent": 0, "bounced": 0}

                ev_upper = (ev_type or "").upper()
                if "SENT" in ev_upper:
                    results[key]["sent"] += int(cnt)
                elif "BOUNC" in ev_upper:
                    results[key]["bounced"] += int(cnt)

            logger.info(f"Retrieved webhook events for {len(results)} mailboxes over period {start_date}..{end_date}")
        except Exception as e:
            logger.warning(f"Could not query webhook mailbox events: {e}")

        return results
