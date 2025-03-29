from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from app.services.report_service import get_report_path
from app.api.dependencies import check_usage_limit
import os

router = APIRouter()

@router.get("/{task_id}/download")
async def download_report(task_id: str, _: None = Depends(check_usage_limit)):
    """下载分析报告"""
    report_path = get_report_path(task_id)
    
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")
    
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"time_series_analysis_{task_id}.pdf",
        headers={
            "Content-Disposition": f'attachment; filename="time_series_analysis_{task_id}.pdf"'
        }
    ) 