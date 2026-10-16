import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.core.logging import logger


def generate_excel_report(report_data: Dict[str, Any], output_dir: str = "exports") -> str:
    """
    Generates an Excel report matching the required 5-column Campaign Delivery format:
    - Column A: Date Range
    - Column B: Campaign Name
    - Column C: Total sent
    - Column D: Total bounce no
    - Column E: Bounce percentage

    Sheet 1: Active Campaigns Report (Formatted matching user reference)
    Sheet 2: Report Metadata & Summary

    Formatting:
    - Bold black headers with soft light-green background (#D9EAD3)
    - Auto-filter on data table
    - Freeze top header row
    - Percentage formatting for bounce rate (0.00%)
    - Number formatting (#,##0) for counts
    - Auto-sized columns
    - Graceful fallback if file is currently open/locked in Excel
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    start_date = report_data.get("period_start", "")
    end_date = report_data.get("period_end", "")
    date_range_str = report_data.get("date_range_str") or f"{start_date} to {end_date}"

    if start_date == "All Time" or date_range_str == "All Time":
        base_file_name = "campaign_report_all_time"
    else:
        base_file_name = f"campaign_report_{start_date}_to_{end_date}"

    file_name = f"{base_file_name}.xlsx"
    file_path = os.path.join(output_dir, file_name)

    # If the file exists and is locked by Excel, fall back to a timestamped file name
    if os.path.exists(file_path):
        try:
            with open(file_path, "r+"):
                pass
        except (PermissionError, IOError):
            ts = datetime.utcnow().strftime("%H%M%S")
            file_name = f"{base_file_name}_{ts}.xlsx"
            file_path = os.path.join(output_dir, file_name)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove default blank sheet

    # Styling definitions
    # Soft light green matching the reference image header (#D9EAD3 / #E2EFDA)
    header_fill = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="000000")
    total_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    total_font = Font(name="Calibri", size=11, bold=True, color="000000")

    subtle_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    total_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='595959'),
        bottom=Side(style='double', color='595959')
    )

    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    # -------------------------------------------------------------
    # Sheet 1: Campaign Delivery Report (13 columns)
    # -------------------------------------------------------------
    ws1 = wb.create_sheet(title="Campaign Delivery Report")
    headers_sheet1 = [
        "Date Range",
        "Campaign Name",
        "Total Leads",
        "Total sent",
        "Total bounce no",
        "Bounce percentage",
        "Blocked Emails",
        "Invalid Emails",
        "Reply Count",
        "Reply percentage",
        "Positive Replies",
        "Positive Reply percentage",
        "Mimecast Bounces",
    ]
    ws1.append(headers_sheet1)

    campaigns: List[Dict[str, Any]] = report_data.get("campaigns", [])

    # If campaigns list is empty, but clients data is provided (legacy format fallback)
    if not campaigns and "clients" in report_data:
        # Extract campaigns from clients
        for client in report_data.get("clients", []):
            for c_entry in client.get("campaigns", []):
                campaigns.append(c_entry)

    row_count = 1
    total_sent_sum = 0
    total_bounced_sum = 0
    total_invalid_sum = 0
    total_blocked_sum = 0
    total_leads_sum = 0
    total_replies_sum = 0
    total_positive_sum = 0
    total_mimecast_sum = 0

    for camp in campaigns:
        row_count += 1
        camp_name = camp.get("campaign_name") or camp.get("name", "Unknown Campaign")
        sent = int(camp.get("total_sent", camp.get("sent", 0)))
        bounced = int(camp.get("total_bounced", camp.get("bounced", 0)))
        invalid = int(camp.get("total_invalid", camp.get("invalid", 0)))
        blocked = int(camp.get("total_blocked", camp.get("blocked", 0)))
        total_leads = int(camp.get("total_leads", 0))
        replies = int(camp.get("total_replies", camp.get("replied", 0)))
        pos_replies = int(camp.get("positive_replies", 0))
        mimecast_bounces = int(camp.get("mimecast_bounces", 0))
        leads_for_rate = total_leads if total_leads > 0 else sent
        bounce_rate_pct = (float(bounced) / float(leads_for_rate)) if leads_for_rate > 0 else 0.0
        delivered_emails = max(0, sent - bounced)
        reply_rate_pct = (float(replies) / float(delivered_emails)) if delivered_emails > 0 else 0.0
        pos_reply_rate_pct = (float(pos_replies) / float(replies)) if replies > 0 else 0.0

        total_sent_sum += sent
        total_bounced_sum += bounced
        total_invalid_sum += invalid
        total_blocked_sum += blocked
        total_leads_sum += total_leads
        total_replies_sum += replies
        total_positive_sum += pos_replies
        total_mimecast_sum += mimecast_bounces

        row_data = [
            date_range_str,
            camp_name,
            total_leads,
            sent,
            bounced,
            bounce_rate_pct,
            blocked,
            invalid,
            replies,
            reply_rate_pct,
            pos_replies,
            pos_reply_rate_pct,
            mimecast_bounces,
        ]
        ws1.append(row_data)

        curr_row = ws1[row_count]
        curr_row[0].alignment = center_align
        curr_row[1].alignment = left_align
        curr_row[2].alignment = right_align
        curr_row[2].number_format = "#,##0"
        curr_row[3].alignment = right_align
        curr_row[3].number_format = "#,##0"
        curr_row[4].alignment = right_align
        curr_row[4].number_format = "#,##0"
        curr_row[5].alignment = right_align
        curr_row[5].number_format = "0.00%"
        curr_row[6].alignment = right_align
        curr_row[6].number_format = "#,##0"
        curr_row[7].alignment = right_align
        curr_row[7].number_format = "#,##0"
        curr_row[8].alignment = right_align
        curr_row[8].number_format = "#,##0"
        curr_row[9].alignment = right_align
        curr_row[9].number_format = "0.00%"
        curr_row[10].alignment = right_align
        curr_row[10].number_format = "#,##0"
        curr_row[11].alignment = right_align
        curr_row[11].number_format = "0.00%"
        curr_row[12].alignment = right_align
        curr_row[12].number_format = "#,##0"

        for cell in curr_row:
            cell.border = subtle_border



    # Format Header Row 1
    for cell in ws1[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = subtle_border

    # Add Summary / Total Row at the bottom
    if row_count > 1:
        row_count += 1
        total_leads_for_rate = total_leads_sum if total_leads_sum > 0 else total_sent_sum
        overall_bounce_rate_pct = (total_bounced_sum / total_leads_for_rate) if total_leads_for_rate > 0 else 0.0
        total_delivered_sum = max(0, total_sent_sum - total_bounced_sum)
        overall_reply_rate_pct = (total_replies_sum / total_delivered_sum) if total_delivered_sum > 0 else 0.0
        overall_pos_rate_pct = (total_positive_sum / total_replies_sum) if total_replies_sum > 0 else 0.0
        total_row_data = [
            "Total",
            f"Active Campaigns: {len(campaigns)}",
            total_leads_sum,
            total_sent_sum,
            total_bounced_sum,
            overall_bounce_rate_pct,
            total_blocked_sum,
            total_invalid_sum,
            total_replies_sum,
            overall_reply_rate_pct,
            total_positive_sum,
            overall_pos_rate_pct,
            total_mimecast_sum,
        ]
        ws1.append(total_row_data)

        tot_row = ws1[row_count]
        for i, col_idx in enumerate(range(13)):
            cell = tot_row[col_idx]
            cell.font = total_font
            cell.fill = total_fill
            cell.border = total_border
            if col_idx == 0:
                cell.alignment = center_align
            elif col_idx == 1:
                cell.alignment = left_align
            elif col_idx in (5, 9, 11):
                cell.alignment = right_align
                cell.number_format = "0.00%"
            else:
                cell.alignment = right_align
                cell.number_format = "#,##0"

    # Freeze header row
    ws1.freeze_panes = "A2"
    if row_count > 2:
        ws1.auto_filter.ref = f"A1:M{row_count - 1}"

    # Auto-fit columns
    for col in ws1.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = max(max_len + 5, 16)

    # -------------------------------------------------------------
    # Sheet 2: Summary & Metadata
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="Report Summary")
    ws2.append(["Property", "Value"])

    total_leads_for_rate = total_leads_sum if total_leads_sum > 0 else total_sent_sum
    overall_rate_str = f"{(total_bounced_sum / total_leads_for_rate * 100):.2f}%" if total_leads_for_rate > 0 else "0.00%"
    total_delivered_sum = max(0, total_sent_sum - total_bounced_sum)
    overall_reply_str = f"{(total_replies_sum / total_delivered_sum * 100):.2f}%" if total_delivered_sum > 0 else "0.00%"
    overall_pos_str = f"{(total_positive_sum / total_replies_sum * 100):.2f}%" if total_replies_sum > 0 else "0.00%"

    meta_properties = [
        ("Date Range", date_range_str),
        ("Period Start", start_date),
        ("Period End", end_date),
        ("Campaign Status Filter", report_data.get("status_filter", "ACTIVE")),
        ("Total Active Campaigns", len(campaigns)),
        ("Total Unique Leads", total_leads_sum),
        ("Total Sent", total_sent_sum),
        ("Total Bounced", total_bounced_sum),
        ("Total Invalid Emails", total_invalid_sum),
        ("Total Blocked", total_blocked_sum),
        ("Total Replies", total_replies_sum),
        ("Total Positive Replies", total_positive_sum),
        ("Total Mimecast Bounces", total_mimecast_sum),
        ("Overall Bounce Percentage", overall_rate_str),
        ("Overall Reply Rate", overall_reply_str),
        ("Overall Positive Reply Rate", overall_pos_str),
        ("Generated At", report_data.get("generated_at", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))),
        ("API Source", "Smartlead Official API (https://server.smartlead.ai/api/v1)"),
    ]


    for prop_name, prop_val in meta_properties:
        ws2.append([prop_name, prop_val])

    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = subtle_border

    for r_idx in range(2, len(meta_properties) + 2):
        row = ws2[r_idx]
        row[0].font = Font(name="Calibri", size=11, bold=True)
        row[0].border = subtle_border
        row[1].border = subtle_border

    ws2.freeze_panes = "A2"
    for col in ws2.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = max(max_len + 6, 22)

    # Save workbook
    wb.save(file_path)
    logger.info(f"Excel report generated successfully at: {file_path}")
    return file_path
