from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select

class SRTSummaryStats(SQLModel, table=True):
    stat_id: int = Field(default=None, primary_key=True)
    lp_counts: int 
    not_in_aap: int 
    aap_bought: int 
    aap_leased: int  
    aap_rental: int | None  = Field(default=None, index=True)
    week: int = Field( index=True)
    year: int = Field( index=True)
