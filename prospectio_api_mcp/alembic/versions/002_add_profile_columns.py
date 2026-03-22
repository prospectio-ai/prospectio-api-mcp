"""Add missing columns to profile table.

Adds full_name, email, phone, years_of_experience, education,
certifications, and languages columns that were added to init.sql
but not applied to existing databases (CREATE TABLE IF NOT EXISTS
does not alter existing tables).

Revision ID: 002
Revises: 001
Create Date: 2026-03-22

"""
from typing import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)"))
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS email VARCHAR(255)"))
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS phone VARCHAR(50)"))
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS years_of_experience INTEGER"))
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS education JSON"))
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS certifications JSON"))
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN IF NOT EXISTS languages JSON"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS languages"))
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS certifications"))
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS education"))
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS years_of_experience"))
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS phone"))
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS email"))
    op.execute(sa.text("ALTER TABLE profile DROP COLUMN IF EXISTS full_name"))
