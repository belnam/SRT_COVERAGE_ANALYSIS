from .db import get_session
from sqlmodel import Session

def get_db():
    db: Session = get_session()
    try:
        yield db
    finally:
        db.close()
