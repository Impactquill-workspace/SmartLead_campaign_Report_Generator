import asyncio
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session

from app.clients.smartlead_client import SmartleadApiClient
from app.services.client_service import ClientService
from app.services.campaign_service import CampaignService
from app.services.analytics_service import AnalyticsService
from app.services.report_service import ReportService
from app.utils.date_utils import parse_date_range, format_date_str
from app.utils.export_utils import generate_excel_report
from app.utils.email_utils import calculate_bounce_rate
from app.core.logging import logger


class WeeklyReportService:
    """
    Main orchestrator for generating Campaign-level email delivery and bounce reports.
    Extracts Date Range, Campaign Name, Total sent, Total bounce no, and Bounce percentage
    for all active campaigns from official Smartlead API endpoints.
    """

    def __init__(self, api_client: SmartleadApiClient, db: Optional[Session] = None):
        self.api_client = api_client
        self.db = db
        self.client_service = ClientService(api_client, db)
        self.campaign_service = CampaignService(api_client, db)
        self.analytics_service = AnalyticsService(api_client, db)
        self.report_service = ReportService(db)

    async def generate_weekly_report(
        self,
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        export_excel: bool = True,
        status_filter: Optional[str] = "ACTIVE",
        all_time: Optional[bool] = None,
        campaign_search: Optional[str] = None,
        client_id: Optional[Union[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Generates campaign-level delivery report:
        Columns: Date Range, Campaign Name, Total sent, Total bounce no, Bounce percentage.
        Default status_filter: 'ACTIVE'.
        If all_time is True or (all_time is None and start_date is None and end_date is None):
            Fetches all-time campaign stats (/campaigns/{id}/analytics).
            Date Range column shows: 'All Time'.
        Otherwise:
            Fetches date-range stats (/campaigns/{id}/analytics-by-date).
            Date Range column shows: 'YYYY-MM-DD to YYYY-MM-DD'.
        """
        # Default to WEEKLY report (previous calendar week) unless all_time is explicitly requested
        is_all_time = bool(all_time)

        if is_all_time:
            start_d, end_d = None, None
            start_str = "All Time"
            end_str = "All Time"
            date_range_str = "All Time"
        else:
            start_d, end_d = parse_date_range(start_date, end_date)
            start_str = format_date_str(start_d)
            end_str = format_date_str(end_d)
            date_range_str = f"{start_str} to {end_str}"

        logger.info("==================================================")
        logger.info(f"WEEKLY CAMPAIGN REPORT STARTED: Mode={'ALL TIME' if is_all_time else date_range_str} (Status: {status_filter or 'ALL'})")
        logger.info("==================================================")

        # Step 2: Fetch all clients
        clients = await self.client_service.fetch_and_sync_clients()
        if client_id is not None and str(client_id).strip() and str(client_id).strip() != "ALL":
            clients = [c for c in clients if str(c.get("client_id")) == str(client_id).strip()]
        logger.info(f"Step 2: Fetched {len(clients)} clients.")

        all_campaign_records: List[Dict[str, Any]] = []
        total_report_sent = 0
        total_report_bounced = 0
        total_report_invalid = 0
        total_report_blocked = 0
        total_report_leads = 0
        total_report_replies = 0
        total_report_positive = 0
        total_report_mimecast = 0

        # Step 3: Fetch campaigns and delivery statistics
        for client in clients:
            c_id = client["client_id"]
            c_name = client["name"]
            logger.info(f"Processing Client: '{c_name}' (ID: {c_id})")

            # Fetch campaigns filtered by status
            campaigns = await self.campaign_service.fetch_campaigns_for_client(
                c_id,
                status_filter=status_filter
            )
            # Filter by specific campaign search/keyword if provided by user
            if campaign_search and str(campaign_search).strip():
                keyword = str(campaign_search).strip().lower()
                campaigns = [c for c in campaigns if keyword in str(c.get("name", "")).lower()]

            total_camps = len(campaigns)
            logger.info(f"Client '{c_name}': Processing {total_camps} matching campaigns.")

            processed_count = 0
            progress_lock = asyncio.Lock()

            # Concurrently fetch analytics for campaigns of this client (paced by client rate limiter)
            async def _fetch_campaign_metrics(camp: Dict[str, Any]) -> Dict[str, Any]:
                nonlocal processed_count
                camp_id = str(camp["campaign_id"])
                camp_name = camp["name"]
                camp_status = camp.get("status", "ACTIVE")
                created_at_str = str(camp.get("created_at") or "")

                # Optimization: if campaign was created after the reporting window, skip API call
                if not is_all_time and end_str and created_at_str and created_at_str[:10] > end_str:
                    sent = 0
                    bounced = 0
                    invalid_emails = 0
                    blocked = 0
                    total_leads = 0
                    replied = 0
                    positive_replies = 0
                    mimecast_bounces = 0
                else:
                    invalid_emails = 0
                    replied = 0
                    positive_replies = 0
                    mimecast_bounces = 0
                    try:
                        if is_all_time:
                            stats = await self.analytics_service.fetch_campaign_all_time_analytics(
                                campaign_id=camp_id,
                                use_contacted=True,
                            )
                        else:
                            stats = await self.analytics_service.fetch_campaign_date_analytics(
                                campaign_id=camp_id,
                                start_date=start_d,
                                end_date=end_d,
                                use_contacted=True,
                            )
                        sent = int(stats.get("sent", 0))
                        bounced = int(stats.get("bounced", 0))
                        blocked = int(stats.get("blocked", 0))
                        replied = int(stats.get("replied", 0))
                    except Exception as e:
                        logger.warning(f"Error fetching analytics for Campaign {camp_id} ({camp_name}): {e}")
                        sent = 0
                        bounced = 0
                        blocked = 0
                        replied = 0

                    # Fetch blocked leads count from campaign_lead_stats
                    try:
                        analytics_data = await self.api_client.get_campaign_analytics(campaign_id=camp_id)
                        lead_stats = analytics_data.get("campaign_lead_stats") or {}
                        if isinstance(lead_stats, dict) and "blocked" in lead_stats:
                            blocked = int(lead_stats.get("blocked") or 0)
                        if is_all_time:
                            total_leads = int(analytics_data.get("total_count") or 0)
                            positive_replies = int(lead_stats.get("interested") or 0)
                    except Exception as e:
                        logger.warning(f"Error fetching campaign analytics for Campaign {camp_id}: {e}")

                    # Option B: Fetch weekly unique leads, invalid bounces, positive replies & Mimecast bounces via /statistics
                    if not is_all_time:
                        try:
                            if sent > 0 and start_d and end_d:
                                stat_data = await self.analytics_service.fetch_campaign_weekly_stats(
                                    campaign_id=camp_id,
                                    start_date=start_d,
                                    end_date=end_d,
                                    sent_count=sent,
                                    )
                                total_leads = stat_data.get("unique_leads", 0)
                                invalid_emails = stat_data.get("invalid_emails", 0)
                                positive_replies = stat_data.get("positive_replies", 0)
                                mimecast_bounces = stat_data.get("mimecast_bounces", 0)
                            else:
                                total_leads = 0
                                invalid_emails = 0
                                positive_replies = 0
                                mimecast_bounces = 0
                        except Exception as e:
                            logger.warning(f"Error fetching weekly unique leads & invalid stats for Campaign {camp_id}: {e}")
                            total_leads = 0
                            invalid_emails = 0
                            positive_replies = 0
                            mimecast_bounces = 0
                    else:
                        # All-time mode: if bounces exist, fetch all-time Mimecast bounces
                        if bounced > 0:
                            try:
                                stat_data = await self.analytics_service.fetch_campaign_weekly_stats(
                                    campaign_id=camp_id,
                                    start_date=None,
                                    end_date=None,
                                    sent_count=sent,
                                )
                                invalid_emails = stat_data.get("invalid_emails", 0)
                                mimecast_bounces = stat_data.get("mimecast_bounces", 0)
                            except Exception as e:
                                logger.warning(f"Error fetching all-time Mimecast bounces for Campaign {camp_id}: {e}")

                async with progress_lock:
                    processed_count += 1
                    if processed_count % 25 == 0 or processed_count == total_camps:
                        logger.info(f"Progress: {processed_count}/{total_camps} campaigns processed...")

                leads_for_rate = total_leads if total_leads > 0 else sent
                bounce_pct = calculate_bounce_rate(leads_count=leads_for_rate, bounced=bounced)
                delivered_emails = max(0, sent - bounced)
                reply_pct = (replied / delivered_emails * 100) if delivered_emails > 0 else 0.0

                if replied == 0:
                    positive_replies = 0
                else:
                    positive_replies = min(positive_replies, replied)
                positive_reply_pct = (positive_replies / replied * 100) if replied > 0 else 0.0

                return {
                    "date_range": date_range_str,
                    "campaign_id": camp_id,
                    "campaign_name": camp_name,
                    "total_sent": sent,
                    "total_bounced": bounced,
                    "total_invalid": invalid_emails,
                    "total_blocked": blocked,
                    "bounce_percentage": bounce_pct,
                    "total_leads": total_leads,
                    "total_replies": replied,
                    "reply_percentage": reply_pct,
                    "positive_replies": positive_replies,
                    "positive_reply_percentage": positive_reply_pct,
                    "mimecast_bounces": mimecast_bounces,
                    "client_id": c_id,
                    "client_name": c_name,
                    "status": camp_status,
                }

            # Gather concurrently
            tasks = [_fetch_campaign_metrics(c) for c in campaigns]
            client_campaign_metrics = await asyncio.gather(*tasks)

            for item in client_campaign_metrics:
                total_report_sent += item["total_sent"]
                total_report_bounced += item["total_bounced"]
                total_report_invalid += item.get("total_invalid", 0)
                total_report_blocked += item.get("total_blocked", 0)
                total_report_leads += item.get("total_leads", 0)
                total_report_replies += item.get("total_replies", 0)
                total_report_positive += item.get("positive_replies", 0)
                total_report_mimecast += item.get("mimecast_bounces", 0)
                all_campaign_records.append(item)


        # Sort campaigns alphabetically by Campaign Name
        all_campaign_records.sort(key=lambda x: x["campaign_name"].lower())

        leads_total_for_rate = total_report_leads if total_report_leads > 0 else total_report_sent
        overall_bounce_rate = calculate_bounce_rate(leads_count=leads_total_for_rate, bounced=total_report_bounced)

        report_summary: Dict[str, Any] = {
            "period_start": start_str,
            "period_end": end_str,
            "date_range_str": date_range_str,
            "status_filter": status_filter or "ACTIVE",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_clients": len(clients),
            "total_campaigns": len(all_campaign_records),
            "total_sent": total_report_sent,
            "total_bounced": total_report_bounced,
            "total_invalid": total_report_invalid,
            "total_blocked": total_report_blocked,
            "total_leads": total_report_leads,
            "total_replies": total_report_replies,
            "total_positive_replies": total_report_positive,
            "total_mimecast_bounces": total_report_mimecast,
            "overall_bounce_rate": overall_bounce_rate,
            "overall_reply_rate": (total_report_replies / max(1, total_report_sent - total_report_bounced) * 100) if (total_report_sent - total_report_bounced) > 0 else 0.0,
            "overall_positive_reply_rate": (total_report_positive / total_report_replies * 100) if total_report_replies > 0 else 0.0,
            "file_path": None,


            "campaigns": all_campaign_records,
            # Backwards compatibility structure for clients
            "clients": [
                {
                    "client_id": c["client_id"],
                    "client_name": c["name"],
                    "campaigns": [
                        camp for camp in all_campaign_records if camp["client_id"] == c["client_id"]
                    ],
                }
                for c in clients
            ],
        }

        # Step 4: Generate Excel Report matching required format
        if export_excel:
            file_path = generate_excel_report(report_summary)
            report_summary["file_path"] = file_path

            # Save report history entry
            self.report_service.save_report_history(
                period_start=start_d or date.today(),
                period_end=end_d or date.today(),
                file_path=file_path,
                total_clients=report_summary["total_clients"],
                total_mailboxes=report_summary["total_campaigns"],
                total_sent=report_summary["total_sent"],
                total_bounced=report_summary["total_bounced"],
            )

        logger.info("==================================================")
        logger.info(f"CAMPAIGN REPORT GENERATED SUCCESSFULLY")
        logger.info(f"Total Active Campaigns: {report_summary['total_campaigns']}")
        logger.info(f"Total Unique Leads Contacted: {total_report_leads}")
        logger.info(f"Total Sent: {total_report_sent}")
        logger.info(f"Total Bounced: {total_report_bounced}")
        logger.info(f"Total Invalid Emails: {total_report_invalid}")
        logger.info(f"Total Blocked: {total_report_blocked}")
        logger.info(f"Total Mimecast Bounces: {total_report_mimecast}")
        logger.info(f"Overall Bounce Rate: {overall_bounce_rate:.2f}%")
        if report_summary.get("file_path"):
            logger.info(f"Excel Report Path: {report_summary['file_path']}")
        logger.info("==================================================")

        return report_summary
