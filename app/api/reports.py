import os
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.clients.smartlead_client import SmartleadApiClient
from app.services.weekly_report_service import WeeklyReportService
from app.schemas.report import WeeklyReportResponse, GenerateReportRequest, GenerateReportResponse
from app.utils.date_utils import parse_date_range, format_date_str
from app.core.logging import logger

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/weekly", response_model=WeeklyReportResponse)
async def get_weekly_report(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query("ACTIVE", description="Campaign status filter (default: ACTIVE, or ALL)"),
    all_time: Optional[bool] = Query(None, description="Fetch all-time lifetime performance metrics (default: true if no dates given)"),
    campaign_search: Optional[str] = Query(None, description="Filter specific campaign name/keyword"),
    client_id: Optional[str] = Query(None, description="Filter specific client ID"),
    db: Session = Depends(get_db),
):
    """
    Returns campaign delivery report. Defaults to all-time lifetime metrics matching Smartlead UI.
    Accepts custom start_date, end_date, status filter, campaign_search, and client_id.
    """
    is_all_time = bool(all_time)
    s_date, e_date = None, None
    if not is_all_time:
        try:
            s_date, e_date = parse_date_range(start_date, end_date)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    client = SmartleadApiClient()
    try:
        service = WeeklyReportService(client, db)
        report_dict = await service.generate_weekly_report(
            start_date=s_date,
            end_date=e_date,
            export_excel=True,
            status_filter=status,
            all_time=is_all_time,
            campaign_search=campaign_search,
            client_id=client_id,
        )
        return report_dict
    finally:
        await client.aclose()


@router.get("/weekly/export")
async def export_weekly_report(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query("ACTIVE", description="Campaign status filter (default: ACTIVE, or ALL)"),
    all_time: Optional[bool] = Query(None, description="Fetch all-time lifetime performance metrics (default: true if no dates given)"),
    campaign_search: Optional[str] = Query(None, description="Filter specific campaign name/keyword"),
    client_id: Optional[str] = Query(None, description="Filter specific client ID"),
    db: Session = Depends(get_db),
):
    """
    Generates and downloads the Excel file matching the required 5-column format.
    """
    is_all_time = bool(all_time)
    s_date, e_date = None, None
    if not is_all_time:
        try:
            s_date, e_date = parse_date_range(start_date, end_date)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    client = SmartleadApiClient()
    try:
        service = WeeklyReportService(client, db)
        report_dict = await service.generate_weekly_report(
            start_date=s_date,
            end_date=e_date,
            export_excel=True,
            status_filter=status,
            all_time=is_all_time,
            campaign_search=campaign_search,
            client_id=client_id,
        )
    finally:
        await client.aclose()

    file_path = report_dict.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="Excel report file could not be generated.")

    file_name = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_name,
    )


@router.post("/generate", response_model=GenerateReportResponse)
async def trigger_generate_report(
    payload: GenerateReportRequest,
    db: Session = Depends(get_db),
):
    """
    Manually triggers generation of campaign report for the given date range or all-time.
    """
    is_all_time = bool(payload.all_time)
    s_date, e_date = None, None
    if not is_all_time:
        try:
            s_date, e_date = parse_date_range(payload.start_date, payload.end_date)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    client = SmartleadApiClient()
    try:
        service = WeeklyReportService(client, db)
        report_dict = await service.generate_weekly_report(
            start_date=s_date,
            end_date=e_date,
            export_excel=True,
            status_filter=payload.status or "ACTIVE",
            all_time=is_all_time,
        )
    finally:
        await client.aclose()

    range_label = "All Time" if is_all_time else f"{format_date_str(s_date)} to {format_date_str(e_date)}"
    return {
        "status": "success",
        "message": f"Report generated successfully for {range_label}",
        "report": report_dict,
    }
