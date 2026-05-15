"""Shared SQLAlchemy declarative base with PostgreSQL naming conventions.

The naming convention ensures consistent, predictable names for indexes,
constraints, and foreign keys across all models and Alembic migrations.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Uses a shared ``MetaData`` instance with PostgreSQL naming conventions
    so that Alembic auto-generates predictable constraint names.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
