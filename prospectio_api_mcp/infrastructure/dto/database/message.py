from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from infrastructure.dto.database.base import Base


class Message(Base):
    """
    SQLAlchemy model for messages table.
    Represents a generated prospecting message for a contact.

    IMPORTANT: Each contact can only have ONE message ever (enforced by UniqueConstraint on contact_id).
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("contact_id", name="uq_messages_contact_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Primary key for the message",
    )
    campaign_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        doc="ID of the campaign this message belongs to",
    )
    contact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        doc="ID of the contact this message is for (unique constraint - one message per contact)",
    )
    contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Name of the contact"
    )
    contact_email: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Email addresses of the contact"
    )
    company_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Name of the company"
    )
    subject: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Generated subject line"
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Generated message body"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="success",
        doc="Message generation status (success, failed)"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Error message if generation failed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when message was created"
    )

    def __repr__(self) -> str:
        """
        String representation of the Message object.

        Returns:
            str: A string representation showing id, contact_id, and status.
        """
        return f"Message(id={self.id!r}, contact_id={self.contact_id!r}, status={self.status!r})"
