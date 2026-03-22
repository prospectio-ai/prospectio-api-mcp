"""Database service for Profile entity persistence."""

from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, delete
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.entities.profile import Profile
from domain.entities.work_experience import WorkExperience
from domain.entities.education import Education
from domain.entities.certification import Certification
from domain.entities.language import Language
from infrastructure.dto.database.profile import ProfileDTO


class ProfileDatabase(ProfileRepositoryPort):
    """
    SQLAlchemy implementation of the profile repository port.
    Handles inserting and updating profile data in the database using async operations.
    """

    def __init__(self, database_url: str):
        """
        Initialize the profile database repository.

        Args:
            database_url (str): Async database connection URL (should start with postgresql+asyncpg://).
        """
        self.database_url = database_url
        self.engine = create_async_engine(database_url)
        self.async_session = async_sessionmaker(self.engine)

    def _convert_dto_to_entity(self, profile_dto: ProfileDTO) -> Profile:
        """
        Convert ProfileDTO to Profile entity.

        Args:
            profile_dto (ProfileDTO): The database DTO to convert.

        Returns:
            Profile: The converted domain entity.
        """
        work_experiences: List[WorkExperience] = []
        if profile_dto.work_experience:
            work_experiences = [
                WorkExperience(**exp) for exp in profile_dto.work_experience
            ]

        education_list: List[Education] = []
        if profile_dto.education:
            education_list = [
                Education(**edu) for edu in profile_dto.education
            ]

        certifications_list: List[Certification] = []
        if profile_dto.certifications:
            certifications_list = [
                Certification(**cert) for cert in profile_dto.certifications
            ]

        languages_list: List[Language] = []
        if profile_dto.languages:
            languages_list = [
                Language(**lang) for lang in profile_dto.languages
            ]

        return Profile(
            full_name=profile_dto.full_name,
            email=profile_dto.email,
            phone=profile_dto.phone,
            job_title=profile_dto.job_title,
            location=profile_dto.location,
            bio=profile_dto.bio,
            years_of_experience=profile_dto.years_of_experience,
            work_experience=work_experiences,
            education=education_list,
            certifications=certifications_list,
            languages=languages_list,
            technos=profile_dto.technos or []
        )

    async def get_profile(self) -> Optional[Profile]:
        """
        Retrieve a profile from the database by ID.

        Args:
            profile_id (int): The profile ID to retrieve. Defaults to 1.

        Returns:
            Optional[Profile]: The profile entity if found, None otherwise.
        """
        async with self.async_session() as session:
            try:
                stmt = select(ProfileDTO).where(ProfileDTO.id == 1)
                result = await session.execute(stmt)
                profile_dto = result.scalar_one_or_none()

                if profile_dto:
                    return self._convert_dto_to_entity(profile_dto)
                return None

            except Exception as e:
                raise e

    async def upsert_profile(self, profile: Profile) -> ProfileDTO:
        """
        Insert or update a profile in the database.

        Args:
            profile: The profile entity to upsert.

        Returns:
            ProfileDTO: The created or updated profile with database ID.
        """
        async with self.async_session() as session:
            try:
                # Convert profile to dict and serialize nested objects
                profile_data = profile.model_dump()

                # Serialize work_experience list
                if profile_data.get("work_experience"):
                    profile_data["work_experience"] = [
                        exp.model_dump() if hasattr(exp, "model_dump") else exp
                        for exp in profile_data["work_experience"]
                    ]

                # Serialize education list
                if profile_data.get("education"):
                    profile_data["education"] = [
                        edu.model_dump() if hasattr(edu, "model_dump") else edu
                        for edu in profile_data["education"]
                    ]

                # Serialize certifications list
                if profile_data.get("certifications"):
                    profile_data["certifications"] = [
                        cert.model_dump() if hasattr(cert, "model_dump") else cert
                        for cert in profile_data["certifications"]
                    ]

                # Serialize languages list
                if profile_data.get("languages"):
                    profile_data["languages"] = [
                        lang.model_dump() if hasattr(lang, "model_dump") else lang
                        for lang in profile_data["languages"]
                    ]

                # Update existing profile
                stmt = (
                    insert(ProfileDTO)
                    .values(id=1, **profile_data)
                    .on_conflict_do_update(index_elements=["id"], set_=profile_data)
                    .returning(ProfileDTO)
                )
                result = await session.execute(stmt)
                profile_dto = result.scalar_one()

                await session.commit()
                await session.refresh(profile_dto)
                return profile_dto

            except Exception as e:
                await session.rollback()
                raise e

    async def delete_profile(self) -> None:
        """
        Delete the profile from the database.

        Returns:
            None
        """
        async with self.async_session() as session:
            try:
                stmt = delete(ProfileDTO).where(ProfileDTO.id == 1)
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
