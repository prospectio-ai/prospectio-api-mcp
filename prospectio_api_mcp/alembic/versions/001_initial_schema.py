"""Initial schema matching init.sql.

Revision ID: 001
Revises:
Create Date: 2026-03-22

"""
from typing import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create companies table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS companies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT,
            industry TEXT,
            compatibility TEXT,
            source TEXT,
            location TEXT,
            size TEXT,
            revenue TEXT,
            website TEXT,
            description TEXT,
            opportunities TEXT[],
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Create jobs table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            date_creation TIMESTAMP WITH TIME ZONE,
            description TEXT,
            job_title TEXT,
            location TEXT,
            salary TEXT,
            job_seniority TEXT,
            job_type TEXT,
            sectors TEXT,
            apply_url TEXT[],
            compatibility_score INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Create contacts table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS contacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
            name TEXT,
            email TEXT[],
            title TEXT,
            phone TEXT,
            profile_url TEXT,
            short_description VARCHAR(255),
            full_bio TEXT,
            confidence_score INTEGER,
            validation_status VARCHAR(50),
            validation_reasons TEXT[],
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Create profile table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS profile (
            id SERIAL PRIMARY KEY,
            job_title TEXT,
            location TEXT,
            bio TEXT,
            work_experience JSON,
            technos TEXT[],
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Create campaigns table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'draft',
            total_contacts INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITH TIME ZONE
        )
    """))

    # Create messages table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            contact_name VARCHAR(255),
            contact_email TEXT[],
            company_name VARCHAR(255),
            subject VARCHAR(500) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_messages_contact_id UNIQUE (contact_id)
        )
    """))

    # Create indexes
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_contacts_company_id ON contacts(company_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_contacts_job_id ON contacts(job_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(job_title)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_campaigns_created_at ON campaigns(created_at)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_messages_campaign_id ON messages(campaign_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_messages_contact_id ON messages(contact_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_messages_company_name ON messages(company_name)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_contacts_validation_status ON contacts(validation_status)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_contacts_confidence_score ON contacts(confidence_score)"))

    # Create function to automatically update updated_at timestamp
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """))

    # Create triggers
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER update_companies_updated_at
            BEFORE UPDATE ON companies
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER update_jobs_updated_at
            BEFORE UPDATE ON jobs
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER update_contacts_updated_at
            BEFORE UPDATE ON contacts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER update_profiles_updated_at
            BEFORE UPDATE ON profile
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER update_campaigns_updated_at
            BEFORE UPDATE ON campaigns
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS messages"))
    op.execute(sa.text("DROP TABLE IF EXISTS campaigns"))
    op.execute(sa.text("DROP TABLE IF EXISTS profile"))
    op.execute(sa.text("DROP TABLE IF EXISTS contacts"))
    op.execute(sa.text("DROP TABLE IF EXISTS jobs"))
    op.execute(sa.text("DROP TABLE IF EXISTS companies"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE"))
