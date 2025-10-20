"""
Configuration de la base de données SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# Fix Render's postgres:// URL format for SQLAlchemy 1.4+ with psycopg driver
# Render provides DATABASE_URL as postgres:// (Heroku legacy format)
# but SQLAlchemy 1.4+ requires postgresql+psycopg:// (for psycopg v3 driver)
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

# Ensure SSL is enabled for Render Postgres (required for all connections)
if "sslmode=" not in database_url:
    # Add sslmode=require if not already present
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}sslmode=require"

# Engine SQLAlchemy
engine = create_engine(
    database_url,
    pool_pre_ping=True,  # Vérifie la connexion avant utilisation
    echo=settings.DEBUG,  # Log SQL queries en dev
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour les modèles
Base = declarative_base()


def get_db():
    """
    Dependency injection pour FastAPI
    Usage: def my_route(db: Session = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
