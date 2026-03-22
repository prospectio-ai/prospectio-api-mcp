"""
Tests for infrastructure/dto/database/ - SQLAlchemy DTO models.
Covers: Campaign, Message.

Note: WorkExperienceDTO is missing __tablename__ and cannot be imported
standalone. It's covered indirectly through campaign_database tests which
import the full DB model set.
"""
from infrastructure.dto.database.campaign import Campaign as CampaignDB
from infrastructure.dto.database.message import Message as MessageDB


class TestCampaignDTO:
    """Test suite for Campaign SQLAlchemy model."""

    def test_tablename(self):
        """Should map to 'campaigns' table."""
        assert CampaignDB.__tablename__ == "campaigns"

    def test_has_required_columns(self):
        """Should have all expected columns."""
        column_names = {c.name for c in CampaignDB.__table__.columns}
        expected = {
            "id", "name", "description", "status",
            "created_at", "updated_at", "completed_at",
            "total_contacts", "successful", "failed",
        }
        assert expected.issubset(column_names)

    def test_repr_format(self):
        """__repr__ should show id, name, and status."""
        campaign = CampaignDB()
        campaign.id = "test-id"
        campaign.name = "Test Campaign"
        campaign.status = "draft"
        repr_str = repr(campaign)
        assert "test-id" in repr_str
        assert "Test Campaign" in repr_str
        assert "draft" in repr_str

    def test_id_is_primary_key(self):
        """id column should be primary key."""
        pk_cols = [c.name for c in CampaignDB.__table__.primary_key.columns]
        assert "id" in pk_cols

    def test_default_status_is_draft(self):
        """Default status column value should be 'draft'."""
        col = CampaignDB.__table__.columns["status"]
        assert col.default.arg == "draft"

    def test_default_total_contacts_is_zero(self):
        """Default total_contacts should be 0."""
        col = CampaignDB.__table__.columns["total_contacts"]
        assert col.default.arg == 0


class TestMessageDTO:
    """Test suite for Message SQLAlchemy model."""

    def test_tablename(self):
        """Should map to 'messages' table."""
        assert MessageDB.__tablename__ == "messages"

    def test_has_required_columns(self):
        """Should have all expected columns."""
        column_names = {c.name for c in MessageDB.__table__.columns}
        expected = {
            "id", "campaign_id", "contact_id",
            "contact_name", "contact_email", "company_name",
            "subject", "message", "status", "error", "created_at",
        }
        assert expected.issubset(column_names)

    def test_unique_constraint_on_contact_id(self):
        """Should have unique constraint on contact_id."""
        from sqlalchemy import UniqueConstraint
        unique_constraints = [
            c for c in MessageDB.__table__.constraints
            if isinstance(c, UniqueConstraint)
            and 'contact_id' in {col.name for col in c.columns}
        ]
        assert len(unique_constraints) >= 1

    def test_repr_format(self):
        """__repr__ should show id, contact_id, and status."""
        msg = MessageDB()
        msg.id = "msg-id"
        msg.contact_id = "contact-id"
        msg.status = "success"
        repr_str = repr(msg)
        assert "msg-id" in repr_str
        assert "contact-id" in repr_str
        assert "success" in repr_str

    def test_campaign_id_is_foreign_key(self):
        """campaign_id should be a foreign key to campaigns table."""
        col = MessageDB.__table__.columns["campaign_id"]
        fk_tables = {fk.target_fullname.split(".")[0] for fk in col.foreign_keys}
        assert "campaigns" in fk_tables

    def test_contact_id_has_foreign_key_ref(self):
        """contact_id should reference the contacts table via foreign key."""
        col = MessageDB.__table__.columns["contact_id"]
        fk_refs = {fk.target_fullname for fk in col.foreign_keys}
        assert "contacts.id" in fk_refs

    def test_default_status_is_success(self):
        """Default status column value should be 'success'."""
        col = MessageDB.__table__.columns["status"]
        assert col.default.arg == "success"
