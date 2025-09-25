from typing import Optional, Annotated
from sqlmodel import SQLModel

class  SRTStatSchema(SQLModel):
    lp_counts: int
    not_in_aap: int
    aap_bought: int
    aap_leased: int
    aap_rental: int | None 
    week: int
    year: int

    def __init__(self, dictionary):
        for k, v in dictionary.items():
             setattr(self, k, v)

    # def __init__(self, **data):
    #     super().__init__(**data)

class SRTStatUpdate(SQLModel):
    lp_counts: Optional[int] = None
    not_in_app: Optional[int] = None
    aap_bought: Optional[int] = None
    aap_leased: Optional[int] = None
    aap_rental: Optional[int] = None
    week: Optional[int] = None
    year: Optional[int] = None
