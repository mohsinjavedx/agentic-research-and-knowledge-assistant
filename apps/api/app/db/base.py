from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata for persistent application entities and migrations."""
