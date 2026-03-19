"""
Reports API endpoints for viewing and downloading user reports/deliveries.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.delivery import Delivery, DeliveryStatus
from app.services.delivery_enhanced import mark_delivery_downloaded, get_user_deliveries
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class ReportResponse(BaseModel):
    """Response schema for report/delivery."""
    id: str
    symbol: str
    symbol_id: int | None
    timeframe: str | None
    status: str
    report_type: str
    report_content: str | None
    has_file: bool
    file_path: str | None
    email_sent_at: datetime | None
    download_count: int
    last_downloaded_at: datetime | None
    created_at: datetime
    error_message: str | None
    
    class Config:
        from_attributes = True


class ReportsListResponse(BaseModel):
    """Response schema for list of reports."""
    reports: List[ReportResponse]
    total: int


@router.get("/reports", response_model=ReportsListResponse)
async def get_my_reports(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's reports/deliveries.
    Returns list of generated reports with analysis content.
    """
    try:
        deliveries = get_user_deliveries(current_user.id, db, limit)
        
        reports = []
        for delivery in deliveries:
            reports.append(ReportResponse(
                id=delivery.id,
                symbol=delivery.symbol or "N/A",
                symbol_id=delivery.symbol_id,
                timeframe=delivery.timeframe,
                status=delivery.status.value,
                report_type=delivery.report_type or "confluence",
                report_content=delivery.report_content,
                has_file=delivery.file_path is not None and Path(delivery.file_path).exists() if delivery.file_path else False,
                file_path=delivery.file_path,
                email_sent_at=delivery.email_sent_at,
                download_count=delivery.download_count or 0,
                last_downloaded_at=delivery.last_downloaded_at,
                created_at=delivery.created_at,
                error_message=delivery.error_message
            ))
        
        return ReportsListResponse(
            reports=reports,
            total=len(reports)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report_details(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific report.
    """
    try:
        delivery = db.query(Delivery).filter(
            Delivery.id == report_id,
            Delivery.user_id == current_user.id
        ).first()
        
        if not delivery:
            raise HTTPException(status_code=404, detail="Report not found")
        
        has_file = False
        if delivery.file_path:
            has_file = Path(delivery.file_path).exists()
        
        return ReportResponse(
            id=delivery.id,
            symbol=delivery.symbol or "N/A",
            symbol_id=delivery.symbol_id,
            timeframe=delivery.timeframe,
            status=delivery.status.value,
            report_type=delivery.report_type or "confluence",
            report_content=delivery.report_content,
            has_file=has_file,
            file_path=delivery.file_path,
            email_sent_at=delivery.email_sent_at,
            download_count=delivery.download_count or 0,
            last_downloaded_at=delivery.last_downloaded_at,
            created_at=delivery.created_at,
            error_message=delivery.error_message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {str(e)}")


@router.get("/reports/{report_id}/download")
async def download_report_file(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download the plot/chart file for a report.
    Increments download counter.
    """
    try:
        delivery = db.query(Delivery).filter(
            Delivery.id == report_id,
            Delivery.user_id == current_user.id
        ).first()
        
        if not delivery:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if not delivery.file_path:
            raise HTTPException(status_code=404, detail="No file available for this report")
        
        file_path = Path(delivery.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Report file not found on server")
        
        # Mark as downloaded
        mark_delivery_downloaded(report_id, db)
        
        # Return file
        return FileResponse(
            path=str(file_path),
            media_type="image/png",
            filename=f"{delivery.symbol}_{delivery.created_at.strftime('%Y%m%d')}.png"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")


@router.get("/reports/{report_id}/content")
async def get_report_content(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the text content of a report (analysis).
    Returns as markdown/text.
    """
    try:
        delivery = db.query(Delivery).filter(
            Delivery.id == report_id,
            Delivery.user_id == current_user.id
        ).first()
        
        if not delivery:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if not delivery.report_content:
            raise HTTPException(status_code=404, detail="No report content available")
        
        return Response(
            content=delivery.report_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"inline; filename={delivery.symbol}_report.md"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch report content: {str(e)}")


@router.get("/reports/symbol/{symbol}")
async def get_reports_by_symbol(
    symbol: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all reports for a specific symbol.
    """
    try:
        deliveries = db.query(Delivery).filter(
            Delivery.user_id == current_user.id,
            Delivery.symbol == symbol.upper()
        ).order_by(Delivery.created_at.desc()).limit(limit).all()
        
        reports = []
        for delivery in deliveries:
            reports.append(ReportResponse(
                id=delivery.id,
                symbol=delivery.symbol or "N/A",
                symbol_id=delivery.symbol_id,
                timeframe=delivery.timeframe,
                status=delivery.status.value,
                report_type=delivery.report_type or "confluence",
                report_content=delivery.report_content,
                has_file=delivery.file_path is not None and Path(delivery.file_path).exists() if delivery.file_path else False,
                file_path=delivery.file_path,
                email_sent_at=delivery.email_sent_at,
                download_count=delivery.download_count or 0,
                last_downloaded_at=delivery.last_downloaded_at,
                created_at=delivery.created_at,
                error_message=delivery.error_message
            ))
        
        return ReportsListResponse(
            reports=reports,
            total=len(reports)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")
