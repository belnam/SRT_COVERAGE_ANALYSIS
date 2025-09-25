from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


DB_USERNAME = "postgres"
DB_PASSWORD = "password"
DB_URL= "localhost"
DB_PORT = "5432"
DB_NAME = "Analytics_Main"

SQLALCHEMY_DATABASE_URL = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_URL}:{DB_PORT}/{DB_NAME}'

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=1000,
    max_overflow=0,
    echo=True  
)

SQLModel.metadata.create_all(engine)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# def get_session():
#     with SessionLocal() as session:
#         yield session
def get_session():
    return Session(engine)

