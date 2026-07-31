from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.report import ExcelExportRequest, ExcelExportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/report", tags=["报表"])


@router.post("/excel")
async def export_excel(
    request: ExcelExportRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """导出 Excel 文件"""
    report_service = ReportService(db)
    try:
        excel_data = report_service.generate_excel(request, current_user_id)

        return StreamingResponse(
            excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={request.filename}"}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/excel/async", response_model=ExcelExportResponse)
async def export_excel_async(
    request: ExcelExportRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """异步导出 Excel 文件"""
    report_service = ReportService(db)
    try:
        task_id = report_service.generate_excel_async(request, current_user_id)
        return ExcelExportResponse(
            task_id=task_id,
            status="pending",
            message="导出任务已创建"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/pdf")
async def export_pdf(
    request: ExcelExportRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """导出 PDF 文件"""
    report_service = ReportService(db)

    try:
        pdf_buffer = report_service.generate_pdf(request, current_user_id)

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={request.filename or 'report.pdf'}"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="PDF 导出失败") from e
