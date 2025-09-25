from fastapi import APIRouter, Depends
from crud import srtcrud
from schemas import srt_summary_stats_schema
from sqlalchemy.orm import Session
from middleware.dependencies import get_db
from fastapi.responses import JSONResponse
from typing import List
router = APIRouter()

@router.get("/srt_summary_stats")
async def get_srt_summary_stats(
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 1500,
    sort_by: str = "year",
    order: str = "desc",
    year: int = None,
    week: int = None,
    
) :
   
    srt_summary_stats = srtcrud.get_summary(db, offset, limit, sort_by, order, year, week)
    return srt_summary_stats

@router.post("/srt_summary_stats")
async def add_summary_statistics(
    summary: srt_summary_stats_schema.SRTStatSchema,
    db: Session = Depends(get_db)
):
    summary_obj = srtcrud.add_summary_statistics(db, summary)
    if not summary_obj:
        return JSONResponse(status_code=404, content={"message": "Failed to add summary statistics."})
    return summary_obj

@router.put("/srt_summary_stats/{stat_id}")
async def update_summary_statistics(
    stat_id: int,
    summary_data: srt_summary_stats_schema.SRTStatUpdate,
    db: Session = Depends(get_db)
):
    summary_obj = srtcrud.update_summary_stats(db, stat_id, summary_data)
    if not summary_obj:
        return JSONResponse(status_code=404, content={"message": "Failed to update summary statistics."})
    return summary_obj

@router.delete("/srt_summary_stats/{stat_id}")
async def delete_summary_statistics(
    stat_id: int,
    db: Session = Depends(get_db)
):
    result = srtcrud.delete_summary_stat(db, stat_id)
    if not result:
        return JSONResponse(status_code=404, content={"message": "Failed to delete summary statistics."})
    return result