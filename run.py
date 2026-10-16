import sys
import asyncio
import argparse
import uvicorn

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.config import get_settings
from app.core.logging import logger
from app.core.database import init_db, SessionLocal
from app.clients.smartlead_client import SmartleadApiClient
from app.services.weekly_report_service import WeeklyReportService
from app.utils.date_utils import parse_date_range, format_date_str


async def run_test_smartlead():
    """
    Safely tests Smartlead API connection, verifying authentication and printing safe metrics.
    Never prints or reveals the API key.
    """
    settings = get_settings()
    masked_key = settings.masked_api_key

    print("==================================================")
    print("SMARTLEAD API CONNECTION TEST")
    print("==================================================")
    print(f"API Base URL: {settings.api_base_url}")
    print(f"API Key:      {masked_key}")
    print(f"Dry Run Mode: {settings.dry_run}")
    print("Sending safe verification request...")

    client = SmartleadApiClient()
    result = await client.test_connection()

    print("\nResult:")
    print(f"Status:  {result.get('status')}")
    print(f"Message: {result.get('message')}")
    if "campaigns_count" in result:
        print(f"Accessible Campaigns: {result['campaigns_count']}")
    print("==================================================")


async def run_generate_report(start_date: str = None, end_date: str = None, status: str = "ACTIVE", all_time: bool = False):
    """
    Generates campaign delivery report for weekly date range (or all-time if explicitly specified).
    """
    settings = get_settings()
    init_db()

    is_all_time = bool(all_time)

    print("==================================================")
    print("SMARTLEAD ACTIVE CAMPAIGN DELIVERY REPORT")
    print("==================================================")
    if is_all_time:
        print("Mode:            ALL TIME (Lifetime performance)")
    else:
        start_d, end_d = parse_date_range(start_date, end_date)
        print(f"Date Range:      {format_date_str(start_d)} through {format_date_str(end_d)}")
    print(f"Campaign Status: {status}")
    print(f"API Key:         {settings.masked_api_key}")
    print(f"Database:        {settings.database_url.split('://')[0]}://***")
    print("Running data extraction and aggregation pipeline...\n")

    db = SessionLocal()
    api_client = SmartleadApiClient()
    try:
        service = WeeklyReportService(api_client, db)
        summary = await service.generate_weekly_report(
            start_date=start_date if not is_all_time else None,
            end_date=end_date if not is_all_time else None,
            export_excel=True,
            status_filter=status,
            all_time=is_all_time,
        )

        print("\n==================================================")
        print("REPORT SUMMARY")
        print("==================================================")
        print(f"Date Range:             {summary['period_start']} to {summary['period_end']}")
        print(f"Total Campaigns:        {summary.get('total_campaigns', 0)}")
        print(f"Total Unique Leads:     {summary.get('total_leads', 0):,}")
        print(f"Total Emails Sent:      {summary['total_sent']:,}")
        print(f"Total Bounced:          {summary['total_bounced']:,}")
        print(f"Total Invalid Emails:   {summary.get('total_invalid', 0):,}")
        print(f"Total Blocked:          {summary.get('total_blocked', 0):,}")
        print(f"Total Replies:          {summary.get('total_replies', 0):,}")
        print(f"Total Positive Replies: {summary.get('total_positive_replies', 0):,}")
        print(f"Total Mimecast Bounces: {summary.get('total_mimecast_bounces', 0):,}")
        print(f"Overall Bounce Rate:    {summary['overall_bounce_rate']:.2f}%")
        print(f"Overall Reply Rate:     {summary.get('overall_reply_rate', 0.0):.2f}%")
        print(f"Overall Positive Rate:  {summary.get('overall_positive_reply_rate', 0.0):.2f}%")

        if summary.get("file_path"):
            print(f"Excel Export File:      {summary['file_path']}")
        print("==================================================")

        # Print Campaign Breakdown matching requested columns
        print("\nCAMPAIGN DELIVERY BREAKDOWN:")
        print(f"{'Date Range':<25} | {'Campaign Name':<30} | {'Total Leads':<11} | {'Total sent':<10} | {'Bounce no':<9} | {'Bounce %':<8} | {'Blocked':<7} | {'Invalid':<7} | {'Replies':<7} | {'Reply %':<8} | {'Pos Rep':<7} | {'Pos %':<7} | {'Mimecast':<8}")
        print("-" * 175)
        for camp in summary.get("campaigns", []):
            raw_name = camp.get('campaign_name', '')
            name_disp = raw_name[:28].encode('ascii', errors='replace').decode('ascii')
            print(
                f"{camp['date_range']:<25} | "
                f"{name_disp:<30} | "
                f"{camp.get('total_leads', 0):<11,d} | "
                f"{camp['total_sent']:<10,d} | "
                f"{camp['total_bounced']:<9,d} | "
                f"{camp['bounce_percentage']:>5.2f}%  | "
                f"{camp.get('total_blocked', 0):<7,d} | "
                f"{camp.get('total_invalid', 0):<7,d} | "
                f"{camp.get('total_replies', 0):<7,d} | "
                f"{camp.get('reply_percentage', 0.0):>5.2f}%  | "
                f"{camp.get('positive_replies', 0):<7,d} | "
                f"{camp.get('positive_reply_percentage', 0.0):>5.2f}% | "
                f"{camp.get('mimecast_bounces', 0):<8,d}"
            )
    finally:
        await api_client.aclose()
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Smartlead Active Campaign Delivery Analytics CLI & Server Runner"
    )
    parser.add_argument(
        "--test-smartlead",
        action="store_true",
        help="Test connection and authentication to the Smartlead API safely",
    )
    parser.add_argument(
        "--generate-weekly-report",
        action="store_true",
        help="Generate report (defaults to all-time lifetime stats matching Smartlead dashboard)",
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate report for custom date range or all-time",
    )
    parser.add_argument(
        "--all-time",
        action="store_true",
        default=False,
        help="Explicitly fetch all-time lifetime statistics",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="ACTIVE",
        help="Campaign status filter (default: ACTIVE, use ALL to check all campaigns)",
    )
    parser.add_argument(
        "--server",
        "--serve",
        dest="serve",
        action="store_true",
        help="Start the FastAPI web server with dashboard",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind FastAPI server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind FastAPI server to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for server development",
    )

    args = parser.parse_args()

    if args.test_smartlead:
        asyncio.run(run_test_smartlead())
    elif args.generate_weekly_report:
        asyncio.run(run_generate_report(args.start_date, args.end_date, status=args.status, all_time=args.all_time))
    elif args.generate_report:
        asyncio.run(run_generate_report(args.start_date, args.end_date, status=args.status, all_time=args.all_time))
    elif args.serve:
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)
    else:
        # Default behavior if no flag passed: start server
        print("Starting Smartlead Weekly Mailbox Analytics server...")
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
