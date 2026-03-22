from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import or_, select
from domain.entities import job
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
        )

    def _convert_db_to_job(self, job_db: JobDB, company_name: Optional[str]) -> Job:
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
        )
