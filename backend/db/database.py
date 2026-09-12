import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Falls back to a local SQLite file when DATABASE_URL isn't configured (no
# Postgres available yet) so the app can still start for local dev/demo use;
# set DATABASE_URL in .env to use real Postgres instead.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sih_local.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()