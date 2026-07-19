import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/ai_sql_query"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


engine = create_engine(get_database_url(), echo=False)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


Base = declarative_base()


def ping_database() -> bool:
    with SessionLocal() as session:
        result = session.execute(text("select 1"))
        return result.scalar_one() == 1
