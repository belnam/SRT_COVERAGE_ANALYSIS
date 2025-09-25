from sqlmodel import Session, select
from model import srt_summary_stats_model
from schemas import srt_summary_stats_schema
from fastapi import HTTPException, status

"""Add/create new summary statistics"""
def add_summary_statistics(db: Session, summary: srt_summary_stats_schema.SRTStatSchema):
    summary_obj = srt_summary_stats_model.SRTSummaryStats(**summary.model_dump())
    db.add(summary_obj)
    db.commit()
    db.refresh(summary_obj)
    return summary_obj

def add_summary_stats(db: Session, summary: srt_summary_stats_schema.SRTStatSchema):
    summary_obj = srt_summary_stats_model.SRTSummaryStats(**summary.model_dump())
    db.add(summary_obj)
    db.commit()
    db.refresh(summary_obj)
    return summary_obj

"""Read all data from DB table"""
def get_summary(db: Session, offset: int = 0, limit: int = 100, sort_by: str = "year", order: str = "desc", year: int = None, week: int = None):
    stmt = select(srt_summary_stats_model.SRTSummaryStats)
    if year:
        stmt = stmt.where(srt_summary_stats_model.SRTSummaryStats.year == year)
    if week:
        stmt = stmt.where(srt_summary_stats_model.SRTSummaryStats.week == week)
    if sort_by:
        if order == "asc":
            stmt = stmt.order_by(getattr(srt_summary_stats_model.SRTSummaryStats, sort_by).asc())
        else:
            stmt = stmt.order_by(getattr(srt_summary_stats_model.SRTSummaryStats, sort_by).desc())
    stmt = stmt.offset(offset).limit(limit)
    results = db.exec(stmt).all()
    # if not results:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No summary statistics found.")
    return results



"""Update summary statistics table"""
def update_summary_stats(db: Session, stat_id: int, summary_data: srt_summary_stats_schema.SRTStatUpdate):
    summary_obj = db.get(srt_summary_stats_model.SRTSummaryStats, stat_id)
    if not summary_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Summary stat with ID {stat_id} not found.")
    
    for key, value in summary_data.dict(exclude_unset=True).items():
        setattr(summary_obj, key, value)
        
    db.add(summary_obj)
    db.commit()
    db.refresh(summary_obj)
    return summary_obj

"""Delete Summary statistics table"""
def delete_summary_stat(db: Session, stat_id: int):
    summary_obj = db.get(srt_summary_stats_model.SRTSummaryStats, stat_id)
    if not summary_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Summary stat with ID {stat_id} not found.")
    
    db.delete(summary_obj)
    db.commit()
    return {"detail": f"Summary stat with ID {stat_id} deleted successfully."}

