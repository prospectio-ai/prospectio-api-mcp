from typing import Optional, List
from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from infrastructure.dto.database.base import Base


class Contact(Base):
    """
    Represents a business contact with optional fields: name, email, phone, and company name.
    SQLAlchemy model for database persistence.
    """

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Primary key for the contact",
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("companies.id", ondelete="CASCADE"),
        doc="ID of the company associated with the contact",
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        doc="ID of the job associated with the contact",
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), doc="Name of the contact")
    email: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String), doc="Email address of the contact"
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255), doc="Title of the contact"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50), doc="Phone number of the contact"
    )
    profile_url: Mapped[Optional[str]] = mapped_column(
        String(500), doc="URL to the contact's profile (e.g., LinkedIn)"
    )
    short_description: Mapped[Optional[str]] = mapped_column(
        String(255), doc="Short bio of the contact (~100 chars)"
    )
    full_bio: Mapped[Optional[str]] = mapped_column(
        doc="Full biography of the contact (500-1500 chars)"
    )
    confidence_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        doc="Validation confidence score (0-100). Scores >= 70 are verified."
    )
    validation_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        doc="Validation status: 'verified', 'likely_valid', or 'needs_review'"
    )
    validation_reasons: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String),
        doc="List of reasons explaining the confidence score"
    )

    def __repr__(self) -> str:
        """
        String representation of the Contact object.

        Returns:
            str: A string representation showing id, name, and email.
        """
        return f"Contact(id={self.id!r}, name={self.name!r}, email={self.email!r})"


# Type alias for a list of contacts
ContactList = List[Contact]
