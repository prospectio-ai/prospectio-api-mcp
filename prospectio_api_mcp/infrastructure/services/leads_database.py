from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import or_, select, delete, func, exists, cast, Text
from sqlalchemy.dialects.postgresql import ARRAY
from domain.ports.leads_repository import LeadsRepositoryPort
from domain.entities.leads import Leads
from infrastructure.dto.database.company import Company as CompanyDB
from infrastructure.dto.database.job import Job as JobDB
from infrastructure.dto.database.contact import Contact as ContactDB
from domain.entities.company import Company, CompanyEntity
from domain.entities.job import Job, JobEntity
from domain.entities.contact import Contact, ContactEntity
from datetime import datetime
from math import ceil


class LeadsDatabase(LeadsRepositoryPort):
    """
    SQLAlchemy implementation of the leads repository port.
    Handles inserting leads data into the database using async operations.
    """

    def __init__(self, database_url: str):
        """
        Initialize the leads database repository.

        Args:
            database_url (str): Async database connection URL (should start with postgresql+asyncpg://).
        """
        self.database_url = database_url
        self.engine = create_async_engine(database_url)

    async def save_leads(self, leads: Leads) -> None:
        """
        Insert leads into the database using async SQLAlchemy.

        Args:
            leads (Leads): The leads data to insert containing companies, jobs, and contacts.
        """
        async with AsyncSession(self.engine) as session:
            try:
                # Prepare collections for batch insert
                companies_to_insert: List[CompanyDB] = []
                jobs_to_insert: List[JobDB] = []
                contacts_to_insert: List[ContactDB] = []

                # Process companies
                if leads.companies and leads.companies.companies:
                    for company_data in leads.companies.companies:
                        company_db = self._convert_company_to_db(company_data)
                        companies_to_insert.append(company_db)

                # Process jobs
                if leads.jobs and leads.jobs.jobs:
                    for job_data in leads.jobs.jobs:
                        job_db = self._convert_job_to_db(job_data)
                        jobs_to_insert.append(job_db)

                # Process contacts
                if leads.contacts and leads.contacts.contacts:
                    for contact_data in leads.contacts.contacts:
                        contact_db = self._convert_contact_to_db(contact_data)
                        contacts_to_insert.append(contact_db)

                session.add_all(companies_to_insert)
                await session.flush()

                session.add_all(jobs_to_insert)
                await session.flush()

                session.add_all(contacts_to_insert)
                await session.commit()

            except Exception as e:
                await session.rollback()
                raise e

    async def get_jobs(self, offset: int, limit: int) -> JobEntity:
        """
        Retrieve jobs from the database with pagination.

        Args:
            offset (int): Number of jobs to skip.
            limit (int): Maximum number of jobs to return.

        Returns:
            JobEntity: Domain entity containing list of jobs.
        """
        async with AsyncSession(self.engine) as session:
            try:
                total_jobs_result = await session.execute(select(JobDB.id))
                total_jobs = total_jobs_result.scalars().all()
                total_pages = ceil(len(total_jobs) / limit) if limit > 0 else 1

                result = await session.execute(
                    select(JobDB)
                    .order_by(JobDB.compatibility_score.desc())
                    .offset(offset)
                    .limit(limit)
                )
                job_dbs = result.scalars().all()

                company_ids = {job.company_id for job in job_dbs if job.company_id}

                companies_result = await session.execute(
                    select(CompanyDB.id, CompanyDB.name).where(CompanyDB.id.in_(company_ids))
                )
                companies_map = {row.id: row.name for row in companies_result.fetchall()}


                jobs = [self._convert_db_to_job(job_db, companies_map.get(job_db.company_id)) for job_db in job_dbs]
                return JobEntity(jobs=jobs, pages=total_pages)
            except Exception as e:
                raise e

    async def get_jobs_by_title_and_location(
        self, title: list[str], location: list[str]
    ) -> JobEntity:
        """
        Retrieve jobs from the database that match any of the provided titles and the specified location (case-insensitive, partial match).

        Args:
            title (list[str]): List of job titles to search for (partial, case-insensitive match on any).
            location (str): The job location to search for (partial, case-insensitive match).

        Returns:
            JobEntity: Domain entity containing the list of jobs matching the criteria. Returns an empty JobEntity if no jobs are found.
        """
        async with AsyncSession(self.engine) as session:
            try:
                stmt = select(JobDB).where(
                    or_(*[JobDB.job_title.ilike(f"%{t}%") for t in title]),
                    or_(*[JobDB.location.ilike(f"%{loc}%") for loc in location]),
                )
                result = await session.execute(stmt)
                job_db = result.scalars().all()

                if job_db:
                    jobs = [self._convert_db_to_job(job, None) for job in job_db]
                    return JobEntity(jobs=jobs) # type: ignore
                return JobEntity(jobs=[]) # type: ignore

            except Exception as e:
                raise e

    async def get_companies_by_names(self, company_names: List[str]) -> CompanyEntity:
        """
        Retrieve companies by their names from the database.

        Args:
            company_names (List[str]): List of company names to search for.

        Returns:
            CompanyEntity: Domain entity containing list of companies matching the names.
        """
        async with AsyncSession(self.engine) as session:
            try:
                result = await session.execute(
                    select(CompanyDB).where(CompanyDB.name.in_(company_names))
                )
                company_dbs = result.scalars().all()

                companies = [
                    self._convert_db_to_company(company_db)
                    for company_db in company_dbs
                ]

                return CompanyEntity(companies=companies) # type: ignore

            except Exception as e:
                raise e

    async def get_companies(self, offset: int, limit: int) -> CompanyEntity:
        """
        Retrieve companies from the database with pagination.

        Args:
            offset (int): Number of companies to skip (default: 0).
            limit (int): Maximum number of companies to return (default: 10).

        Returns:
            CompanyEntity: Domain entity containing list of companies.
        """
        async with AsyncSession(self.engine) as session:
            try:
                total_companies_result = await session.execute(select(CompanyDB.id))
                total_companies = total_companies_result.scalars().all()
                total_pages = ceil(len(total_companies) / limit) if limit > 0 else 1

                result = await session.execute(
                    select(CompanyDB).order_by(CompanyDB.id).offset(offset).limit(limit)
                )
                company_dbs = result.scalars().all()
                companies = [
                    self._convert_db_to_company(company_db)
                    for company_db in company_dbs
                ]
                return CompanyEntity(companies=companies, pages=total_pages) # type: ignore
            except Exception as e:
                raise e

    async def get_contacts(self, offset: int, limit: int) -> ContactEntity:
        """
        Retrieve contacts from the database with pagination.

        Args:
            offset (int): Number of contacts to skip (default: 0).
            limit (int): Maximum number of contacts to return (default: 10).

        Returns:
            ContactEntity: Domain entity containing list of contacts.
        """
        async with AsyncSession(self.engine) as session:
            try:
                total_contacts_result = await session.execute(select(ContactDB.id))
                total_contacts = total_contacts_result.scalars().all()
                total_pages = ceil(len(total_contacts) / limit) if limit > 0 else 1

                result = await session.execute(
                    select(ContactDB).order_by(ContactDB.id).offset(offset).limit(limit)
                )

                contact_dbs = result.scalars().all()

                company_ids = {contact_db.company_id for contact_db in contact_dbs if contact_db.company_id}
                job_ids = {contact_db.job_id for contact_db in contact_dbs if contact_db.job_id}

                companies_result = await session.execute(
                    select(CompanyDB.id, CompanyDB.name).where(CompanyDB.id.in_(company_ids))
                )
                companies_map = {row.id: row.name for row in companies_result.fetchall()}

                jobs_result = await session.execute(
                    select(JobDB.id, JobDB.job_title).where(JobDB.id.in_(job_ids))
                )
                jobs_map = {row.id: row.job_title for row in jobs_result.fetchall()}

                contacts = [
                    self._convert_db_to_contact(
                        contact_db,
                        companies_map.get(contact_db.company_id),
                        jobs_map.get(contact_db.job_id)
                    )
                    for contact_db in contact_dbs
                ]
                return ContactEntity(contacts=contacts, pages=total_pages)
            except Exception as e:
                raise e

    async def get_contacts_by_name_and_title(
        self, names: list[str], titles: list[str]
    ) -> ContactEntity:
        """
        Retrieve contacts from the database that match any of the provided names AND any of the provided titles (case-insensitive, partial match, AND condition).

        Args:
            names (list[str]): List of contact names to search for (partial, case-insensitive match on any).
            titles (list[str]): List of contact titles to search for (partial, case-insensitive match on any).

        Returns:
            ContactEntity: Domain entity containing the list of contacts matching both name and title criteria. Returns an empty ContactEntity if no contacts are found.
        """
        async with AsyncSession(self.engine) as session:
            try:
                stmt = select(ContactDB).where(
                    or_(*[ContactDB.name.ilike(f"%{name}%") for name in names])
                    & or_(*[ContactDB.title.ilike(f"%{title}%") for title in titles])
                )
                result = await session.execute(stmt)
                contact_dbs = result.scalars().all()
                contacts = [
                    self._convert_db_to_contact(contact_db, None, None)
                    for contact_db in contact_dbs
                ]
                return ContactEntity(contacts=contacts) # type: ignore
            except Exception as e:
                raise e

    async def get_contact_by_id(self, contact_id: str) -> Optional[Contact]:
        """
        Retrieve a contact by its ID from the database.

        Args:
            contact_id (str): The unique identifier of the contact.

        Returns:
            Optional[Contact]: The contact entity if found, otherwise None.
        """
        async with AsyncSession(self.engine) as session:
            try:
                result = await session.execute(
                    select(ContactDB).where(ContactDB.id == contact_id)
                )
                contact_db = result.scalars().first()
                if contact_db:
                    return self._convert_db_to_contact(contact_db, None, None)
                return None
            except Exception as e:
                raise e
    
    async def get_company_by_id(self, company_id: str) -> Optional[Company]:
        """
        Retrieve a company by its ID from the database.

        Args:
            company_id (str): The unique identifier of the company.
        Returns:
            Optional[Company]: The company entity if found, otherwise None.
        """
        async with AsyncSession(self.engine) as session:
            try:
                result = await session.execute(
                    select(CompanyDB).where(CompanyDB.id == company_id)
                )
                company_db = result.scalars().first()
                if company_db:
                    return self._convert_db_to_company(company_db)
                return None
            except Exception as e:
                raise e

    async def get_leads(
        self,
        offset: int,
        limit: int
    ) -> Leads:
        """
        Retrieve paginated jobs and only the related companies and contacts for those jobs.

        Args:
            jobs_offset (int): Number of jobs to skip (default: 0).
            jobs_limit (int): Maximum number of jobs to return (default: 10).

        Returns:
            Leads: Domain entity containing jobs, their companies, and their contacts.
        """
        async with AsyncSession(self.engine) as session:
            try:

                total_jobs_result = await session.execute(select(JobDB.id))
                total_jobs = total_jobs_result.scalars().all()
                total_pages = ceil(len(total_jobs) / limit) if limit > 0 else 1

                jobs_result = await session.execute(
                    select(JobDB)
                    .order_by(JobDB.compatibility_score.desc())
                    .offset(offset)
                    .limit(limit)
                )
                job_dbs = jobs_result.scalars().all()
                jobs = [self._convert_db_to_job(job_db, None) for job_db in job_dbs]
                job_ids = [job_db.id for job_db in job_dbs]
                company_ids = list(
                    {
                        job_db.company_id
                        for job_db in job_dbs
                        if job_db.company_id is not None
                    }
                )

                if company_ids:
                    companies_result = await session.execute(
                        select(CompanyDB).where(CompanyDB.id.in_(company_ids))
                    )
                    company_dbs = companies_result.scalars().all()
                else:
                    company_dbs = []
                companies = [
                    self._convert_db_to_company(company_db)
                    for company_db in company_dbs
                ]

                if job_ids or company_ids:
                    contacts_result = await session.execute(
                        select(ContactDB).where(
                            (ContactDB.job_id.in_(job_ids))
                            | (ContactDB.company_id.in_(company_ids))
                        )
                    )
                    contact_dbs = contacts_result.scalars().all()
                else:
                    contact_dbs = []
                contacts = [
                    self._convert_db_to_contact(contact_db, None, None)
                    for contact_db in contact_dbs
                ]

                return Leads(
                    companies=CompanyEntity(companies=companies), # type: ignore
                    jobs=JobEntity(jobs=jobs), # type: ignore
                    contacts=ContactEntity(contacts=contacts), # type: ignore
                    pages=total_pages
                )
            except Exception as e:
                raise e

    async def get_all_contacts_with_companies(self) -> list:
        """Retrieve all contacts with their associated companies."""
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(ContactDB, CompanyDB)
                .outerjoin(CompanyDB, ContactDB.company_id == CompanyDB.id)
            )
            rows = result.all()
            return [
                (
                    self._convert_db_to_contact(contact_db, company_db.name if company_db else None, None),
                    self._convert_db_to_company(company_db) if company_db else None,
                )
                for contact_db, company_db in rows
            ]

    async def delete_all_data(self) -> None:
        """Delete all leads data from the database."""
        async with AsyncSession(self.engine) as session:
            try:
                await session.execute(ContactDB.__table__.delete())
                await session.execute(JobDB.__table__.delete())
                await session.execute(CompanyDB.__table__.delete())
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    async def company_exists_by_name(self, name: str) -> bool:
        """Check if a company exists by name."""
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(CompanyDB.id).where(CompanyDB.name == name).limit(1)
            )
            return result.scalars().first() is not None

    async def get_company_by_name(self, name: str) -> Optional[Company]:
        """Retrieve a company by its name."""
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(CompanyDB).where(CompanyDB.name == name).limit(1)
            )
            company_db = result.scalars().first()
            if company_db:
                return self._convert_db_to_company(company_db)
            return None

    async def contact_exists_by_email(self, emails: list[str]) -> bool:
        """Check if a contact exists by email."""
        async with AsyncSession(self.engine) as session:
            for email in emails:
                result = await session.execute(
                    select(ContactDB.id).where(ContactDB.email.contains([email])).limit(1)
                )
                if result.scalars().first() is not None:
                    return True
            return False

    async def contact_exists_by_name_and_company(self, name: str, company_id) -> bool:
        """Check if a contact exists by name and company."""
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(ContactDB.id).where(
                    ContactDB.name == name,
                    ContactDB.company_id == company_id,
                ).limit(1)
            )
            return result.scalars().first() is not None

    async def save_company(self, company: Company) -> Company:
        """Save a company to the database."""
        async with AsyncSession(self.engine) as session:
            try:
                company_db = self._convert_company_to_db(company)
                session.add(company_db)
                await session.commit()
                return company
            except Exception as e:
                await session.rollback()
                raise e

    async def save_contact(self, contact: Contact) -> Contact:
        """Save a contact to the database."""
        async with AsyncSession(self.engine) as session:
            try:
                contact_db = self._convert_contact_to_db(contact)
                session.add(contact_db)
                await session.commit()
                return contact
            except Exception as e:
                await session.rollback()
                raise e

    async def job_exists(self, job_title: str, company_name: str) -> bool:
        """Check if a job exists by title and company name."""
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(JobDB.id)
                .join(CompanyDB, JobDB.company_id == CompanyDB.id)
                .where(JobDB.job_title == job_title, CompanyDB.name == company_name)
                .limit(1)
            )
            return result.scalars().first() is not None

    async def save_job(self, job) -> None:
        """Save a job to the database."""
        async with AsyncSession(self.engine) as session:
            try:
                from domain.entities.job import Job as JobDomain
                if isinstance(job, JobDomain):
                    job_db = self._convert_job_to_db(job)
                else:
                    job_db = job
                session.add(job_db)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    async def get_or_create_company_stub(self, name: str) -> Company:
        """Get an existing company or create a stub company by name."""
        existing = await self.get_company_by_name(name)
        if existing:
            return existing
        import uuid
        stub = Company(id=str(uuid.uuid4()), name=name)
        return await self.save_company(stub)

    def _convert_company_to_db(self, company_data: Company) -> CompanyDB:
        """
        Convert domain company entity to database company model.

        Args:
            company_data: Domain company entity.

        Returns:
            CompanyDB: Database company model.
        """
        return CompanyDB(
            id=company_data.id,
            name=company_data.name,
            industry=company_data.industry,
            compatibility=company_data.compatibility,
            source=company_data.source,
            location=company_data.location,
            size=company_data.size,
            revenue=company_data.revenue,
            website=company_data.website,
            description=company_data.description,
            opportunities=company_data.opportunities,
        )

    def _convert_job_to_db(self, job_data: Job) -> JobDB:
        """
        Convert domain job entity to database job model.

        Args:
            job_data: Domain job entity.

        Returns:
            JobDB: Database job model.
        """
        return JobDB(
            id=job_data.id,
            company_id=job_data.company_id,
            date_creation=(
                datetime.fromisoformat(job_data.date_creation)
                if job_data.date_creation
                else datetime.fromisoformat(datetime.now().isoformat())
            ),
            description=job_data.description,
            job_title=job_data.job_title,
            location=job_data.location,
            salary=job_data.salary,
            job_seniority=job_data.job_seniority,
            job_type=job_data.job_type,
            sectors=job_data.sectors,
            apply_url=job_data.apply_url,
            compatibility_score=job_data.compatibility_score,
        )

    def _convert_contact_to_db(self, contact_data: Contact) -> ContactDB:
        """
        Convert domain contact entity to database contact model.

        Args:
            contact_data: Domain contact entity.

        Returns:
            ContactDB: Database contact model.
        """
        return ContactDB(
            company_id=contact_data.company_id,
            job_id=contact_data.job_id,
            name=contact_data.name,
            email=contact_data.email,
            title=contact_data.title,
            phone=contact_data.phone,
            profile_url=contact_data.profile_url,
            short_description=contact_data.short_description,
            full_bio=contact_data.full_bio,
            confidence_score=contact_data.confidence_score,
            validation_status=contact_data.validation_status,
            validation_reasons=contact_data.validation_reasons,
        )

    def _convert_db_to_job(self, job_db: JobDB, company_name: Optional[str] = None) -> Job:
        """
        Convert database job model to domain job entity.

        Args:
            job_db: Database job model.

        Returns:
            Job: Domain job entity.
        """
        return Job(
            id=job_db.id,
            company_id=job_db.company_id,
            company_name=company_name,
            date_creation=(
                job_db.date_creation.isoformat() if job_db.date_creation else None
            ),
            description=job_db.description,
            job_title=job_db.job_title,
            location=job_db.location,
            salary=job_db.salary,
            job_seniority=job_db.job_seniority,
            job_type=job_db.job_type,
            sectors=job_db.sectors,
            apply_url=job_db.apply_url,
            compatibility_score=job_db.compatibility_score,
        )

    def _convert_db_to_company(self, company_db: CompanyDB) -> Company:
        """
        Convert database company model to domain company entity.

        Args:
            company_db: Database company model.

        Returns:
            Company: Domain company entity.
        """
        return Company(
            id=company_db.id,
            name=company_db.name,
            industry=company_db.industry,
            compatibility=company_db.compatibility,
            source=company_db.source,
            location=company_db.location,
            size=company_db.size,
            revenue=company_db.revenue,
            website=company_db.website,
            description=company_db.description,
            opportunities=company_db.opportunities,
        )

    def _convert_db_to_contact(self, contact_db: ContactDB, company_name: Optional[str], job_title: Optional[str]) -> Contact:
        """
        Convert database contact model to domain contact entity.

        Args:
            contact_db: Database contact model.

        Returns:
            Contact: Domain contact entity.
        """
        return Contact(
            id=contact_db.id,
            company_id=contact_db.company_id,
            company_name=company_name,
            job_id=contact_db.job_id,
            job_title=job_title,
            name=contact_db.name,
            email=contact_db.email,
            title=contact_db.title,
            phone=contact_db.phone,
            profile_url=contact_db.profile_url,
            short_description=contact_db.short_description,
            full_bio=contact_db.full_bio,
            confidence_score=contact_db.confidence_score,
            validation_status=contact_db.validation_status,
            validation_reasons=contact_db.validation_reasons,
        )

    async def get_all_contacts_with_companies(self) -> List[Tuple[Contact, Company]]:
        """
        Retrieve all contacts with their associated companies from the database.

        Returns:
            List[Tuple[Contact, Company]]: List of tuples containing contact and company pairs.
        """
        async with AsyncSession(self.engine) as session:
            try:
                # Fetch all contacts
                contacts_result = await session.execute(select(ContactDB))
                contact_dbs = contacts_result.scalars().all()

                if not contact_dbs:
                    return []

                # Get all unique company IDs
                company_ids = list({
                    contact_db.company_id
                    for contact_db in contact_dbs
                    if contact_db.company_id is not None
                })

                # Fetch all companies in one query
                companies_map: dict[str, CompanyDB] = {}
                if company_ids:
                    companies_result = await session.execute(
                        select(CompanyDB).where(CompanyDB.id.in_(company_ids))
                    )
                    company_dbs = companies_result.scalars().all()
                    companies_map = {company_db.id: company_db for company_db in company_dbs}

                # Build result list of tuples
                result: List[Tuple[Contact, Company]] = []
                for contact_db in contact_dbs:
                    company_db = companies_map.get(contact_db.company_id) if contact_db.company_id else None
                    if company_db:
                        contact = self._convert_db_to_contact(
                            contact_db,
                            company_db.name,
                            None
                        )
                        company = self._convert_db_to_company(company_db)
                        result.append((contact, company))

                return result
            except Exception as e:
                raise e

    async def company_exists_by_name(self, name: str) -> bool:
        """
        Check if a company with the given name already exists in the database.

        Args:
            name: The name of the company to check.

        Returns:
            bool: True if a company with this name exists, False otherwise.
        """
        async with AsyncSession(self.engine) as session:
            try:
                result = await session.execute(
                    select(exists().where(CompanyDB.name == name))
                )
                return result.scalar() or False
            except Exception as e:
                raise e

    async def get_company_by_name(self, name: str) -> Optional[Company]:
        """
        Retrieve a company by its name from the database.

        Args:
            name: The name of the company to search for.

        Returns:
            Optional[Company]: The company if found, None otherwise.
        """
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(CompanyDB).where(CompanyDB.name == name)
            )
            company_db = result.scalar_one_or_none()
            if company_db:
                return self._convert_db_to_company(company_db)
            return None

    async def contact_exists_by_email(self, emails: list[str]) -> bool:
        """
        Check if a contact with any of the given emails already exists in the database.
        Uses PostgreSQL array overlap operator to check if any email in the input list
        exists in any contact's email array.

        Args:
            emails: List of email addresses to check.

        Returns:
            bool: True if a contact with any of these emails exists, False otherwise.
        """
        if not emails:
            return False

        async with AsyncSession(self.engine) as session:
            try:
                # Use PostgreSQL's && (overlap) operator for array comparison
                # Cast the input list to ARRAY(Text) to match the column type (text[])
                result = await session.execute(
                    select(exists().where(
                        ContactDB.email.overlap(cast(emails, ARRAY(Text)))
                    ))
                )
                return result.scalar() or False
            except Exception as e:
                raise e

    async def contact_exists_by_name_and_company(
        self, name: str, company_id: Optional[str]
    ) -> bool:
        """
        Check if a contact with the given name and company already exists in the database.

        Used for deduplication when a contact has no email address.
        Comparison is case-insensitive on name.

        Args:
            name: The name of the contact to check.
            company_id: The company ID to check (can be None).

        Returns:
            bool: True if a contact with this name and company exists, False otherwise.
        """
        async with AsyncSession(self.engine) as session:
            try:
                if company_id:
                    result = await session.execute(
                        select(exists().where(
                            (func.lower(ContactDB.name) == func.lower(name)) &
                            (ContactDB.company_id == company_id)
                        ))
                    )
                else:
                    result = await session.execute(
                        select(exists().where(
                            (func.lower(ContactDB.name) == func.lower(name)) &
                            (ContactDB.company_id.is_(None))
                        ))
                    )
                return result.scalar() or False
            except Exception as e:
                raise e

    async def save_company(self, company: Company) -> Company:
        """
        Save a single company to the database.

        Args:
            company: The company entity to save.

        Returns:
            Company: The saved company with its generated ID.
        """
        async with AsyncSession(self.engine) as session:
            try:
                company_db = self._convert_company_to_db(company)
                session.add(company_db)
                await session.commit()
                await session.refresh(company_db)
                return self._convert_db_to_company(company_db)
            except Exception as e:
                await session.rollback()
                raise e

    async def save_contact(self, contact: Contact) -> Contact:
        """
        Save a single contact to the database.

        Args:
            contact: The contact entity to save.

        Returns:
            Contact: The saved contact with its generated ID.
        """
        async with AsyncSession(self.engine) as session:
            try:
                contact_db = self._convert_contact_to_db(contact)
                session.add(contact_db)
                await session.commit()
                await session.refresh(contact_db)
                return self._convert_db_to_contact(contact_db, None, None)
            except Exception as e:
                await session.rollback()
                raise e

    async def delete_all_data(self) -> None:
        """
        Delete all leads data (contacts, jobs, companies) from the database.
        Deletes in correct order to respect foreign key constraints:
        1. Contacts (references jobs and companies)
        2. Jobs (references companies)
        3. Companies

        Returns:
            None
        """
        async with AsyncSession(self.engine) as session:
            try:
                # Delete in order to respect foreign key constraints
                await session.execute(delete(ContactDB))
                await session.execute(delete(JobDB))
                await session.execute(delete(CompanyDB))
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    async def job_exists(self, job_title: str, company_name: str) -> bool:
        """
        Check if a job with the given title and company name already exists in the database.
        Comparison is case-insensitive.

        Args:
            job_title: The title of the job.
            company_name: The name of the company.

        Returns:
            bool: True if a job with this title and company exists, False otherwise.
        """
        async with AsyncSession(self.engine) as session:
            try:
                # First get all company IDs by name (case-insensitive)
                # Multiple companies with same name may exist
                company_result = await session.execute(
                    select(CompanyDB.id).where(
                        func.lower(CompanyDB.name) == func.lower(company_name)
                    )
                )
                company_ids = company_result.scalars().all()

                if not company_ids:
                    return False

                # Check if a job with this title exists for any of these companies (case-insensitive)
                result = await session.execute(
                    select(exists().where(
                        (func.lower(JobDB.job_title) == func.lower(job_title)) &
                        (JobDB.company_id.in_(company_ids))
                    ))
                )
                return result.scalar() or False
            except Exception as e:
                raise e

    async def save_job(self, job: Job) -> Job:
        """
        Save a single job to the database.

        Args:
            job: The job entity to save.

        Returns:
            Job: The saved job with its generated ID.
        """
        async with AsyncSession(self.engine) as session:
            try:
                job_db = self._convert_job_to_db(job)
                session.add(job_db)
                await session.commit()
                await session.refresh(job_db)
                return self._convert_db_to_job(job_db, job.company_name)
            except Exception as e:
                await session.rollback()
                raise e

    async def get_or_create_company_stub(self, name: str) -> Company:
        """
        Get an existing company by name or create a minimal stub company.

        This is used when saving jobs to ensure the company_id foreign key
        constraint is satisfied. Creates a stub company with only the name
        if the company does not exist yet.

        Args:
            name: The name of the company.

        Returns:
            Company: The existing or newly created stub company with its ID.
        """
        async with AsyncSession(self.engine) as session:
            # First try to find existing company (case-insensitive)
            result = await session.execute(
                select(CompanyDB).where(
                    func.lower(CompanyDB.name) == func.lower(name)
                )
            )
            company_db = result.scalar_one_or_none()

            if company_db:
                return self._convert_db_to_company(company_db)

        # Company not found, create a new stub
        async with AsyncSession(self.engine) as session:
            try:
                stub_company = CompanyDB(name=name)
                session.add(stub_company)
                await session.commit()
                await session.refresh(stub_company)
                return self._convert_db_to_company(stub_company)
            except Exception as e:
                await session.rollback()
                # If creation failed (e.g., due to race condition), try to fetch again
                async with AsyncSession(self.engine) as retry_session:
                    result = await retry_session.execute(
                        select(CompanyDB).where(
                            func.lower(CompanyDB.name) == func.lower(name)
                        )
                    )
                    company_db = result.scalar_one_or_none()
                    if company_db:
                        return self._convert_db_to_company(company_db)
                raise e
