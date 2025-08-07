import os
from collections.abc import Generator
from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..util import EnvKey, get_user_data_dir

if TYPE_CHECKING:
    from .globals import GlobalVariables
    from .prefs import Preferences


# Get database URL from environment, default to SQLite in user data directory
def _get_default_database_url() -> str:
    """Get the default database URL using the appropriate user data directory."""
    data_dir = get_user_data_dir()
    # Create the data directory if it doesn't exist
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "cosmo.db"
    return f"sqlite:///{db_path}"


DATABASE_URL = os.getenv(EnvKey.DATABASE_URL, _get_default_database_url())

# Create engine with appropriate settings for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session for FastAPI routes."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def get_prefs(db: Session = Depends(get_db)) -> "Preferences":
    """Dependency to get Preferences instance for FastAPI routes."""
    from .prefs import Preferences

    return Preferences(db)


def get_globals(db: Session = Depends(get_db)) -> "GlobalVariables":
    """Dependency to get GlobalVariables instance for FastAPI routes."""
    from .globals import GlobalVariables

    return GlobalVariables(db)
