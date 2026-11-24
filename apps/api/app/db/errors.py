"""Database failure families, including errors raised before SQLAlchemy wraps them."""

from asyncpg import InterfaceError, PostgresError
from sqlalchemy.exc import SQLAlchemyError

DATABASE_ERRORS = (SQLAlchemyError, OSError, PostgresError, InterfaceError)
