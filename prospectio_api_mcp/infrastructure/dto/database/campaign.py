from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from infrastructure.dto.database.base import Base


class Campaign(Base):
    """
    SQLAlchemy model for campaigns table.
    Represents a prospecting campaign containing generated messages for contacts.
    """

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Primary key for the campaign",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Name of the campaign"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        doc="Description of the campaign"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        doc="Current status of the campaign (draft, in_progress, completed, failed)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when campaign was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when campaign was last updated"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when campaign was completed"
    )
    total_contacts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Total number of contacts in the campaign"
    )
    successful: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of successfully generated messages"
    )
    failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of failed message generations"
    )

    def __repr__(self) -> str:
        """
        String representation of the Campaign object.

        Returns:
            str: A string representation showing id, name, and status.
        """
        return f"Campaign(id={self.id!r}, name={self.name!r}, status={self.status!r})"
