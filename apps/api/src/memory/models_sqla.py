"""
SQLAlchemy metadata for Alembic autogenerate.
- Keep this in sync with persistence_pg/PostgresStore schema.
"""

from __future__ import annotations

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Text, Float, Index

Base = declarative_base()


class MemoryORM(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True)
    text = Column(Text, nullable=False)
    type = Column(String, nullable=False)
    salience = Column(Float, nullable=False)
    created_at = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    persona_id = Column(String, nullable=False)
    embedding = Column(Text, nullable=True)
    metadata = Column(Text, nullable=True)
    project_id = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_mem_thread_persona", "thread_id", "persona_id"),
        Index("idx_mem_user", "user_id"),
        Index("idx_mem_project", "project_id"),
    )


class ProjectORM(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(String, nullable=False)