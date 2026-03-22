import logging
import re
from typing import Callable, Optional

from email_validator import EmailNotValidError, caching_resolver, validate_email
from langgraph.types import Send

from config import DuckDuckGoConfig, LLMConfig, WebSearchConfig
from domain.entities.company import Company, CompanyEntity
from domain.entities.contact import Contact, ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from domain.ports.leads_repository import LeadsRepositoryPort
from infrastructure.api.llm_client_factory import LLMClientFactory
from infrastructure.services.enrich_leads_agent.chains.decision_chain import (
    DecisionChain,
)
from infrastructure.services.enrich_leads_agent.chains.enrich_chain import EnrichChain
from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo
from infrastructure.services.enrich_leads_agent.models.contact_info import ContactInfo
from infrastructure.services.enrich_leads_agent.models.make_decision import (
    MakeDecisionResult,
)
from infrastructure.services.enrich_leads_agent.state import OverallEnrichLeadsState
from infrastructure.services.enrich_leads_agent.tools.duckduckgo_client import (
    DuckDuckGoClient,
)
from infrastructure.services.enrich_leads_agent.tools.web_search_client import (
    WebSearchClient,
)
from infrastructure.services.enrich_leads_agent.validators.contact_validator import (
    ContactValidator,
)



logger = logging.getLogger(__name__)


class EnrichLeadsNodes:
    """
    Nodes for the WebSearch agent.
    Supports streaming mode when leads_repository is provided.
    """

    def __init__(
        self,
        leads_repository: Optional[LeadsRepositoryPort] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the WebSearchNodes with required models and tools.

        Args:
            leads_repository: Optional repository for immediate contact persistence.
                             When provided, contacts are saved as they are extracted.
            progress_callback: Optional async callback for progress updates.
                              Called with a message string for each step.
        """
        self.resolver = caching_resolver(timeout=10)
        self.leads_repository = leads_repository
        self.progress_callback = progress_callback
        decision_model = LLMConfig().DECISION_MODEL  # type: ignore
        decision_llm_client = LLMClientFactory(
            model=decision_model, config=LLMConfig()  # type: ignore
        ).create_client()
        enrich_llm_client = LLMClientFactory(
            model=LLMConfig().ENRICH_MODEL, config=LLMConfig()  # type: ignore
        ).create_client()
        self.decision_chain = DecisionChain(decision_llm_client)
        self.enrich_chain = EnrichChain(enrich_llm_client)
        self.web_search_client = WebSearchClient(LLMConfig(), WebSearchConfig())
        self.duckduckgo_client = DuckDuckGoClient(DuckDuckGoConfig())
        self.contact_validator = ContactValidator()
        self.profile = Profile(
            job_title=None, location=None, bio=None, work_experience=[]
        )  # type: ignore
        self.leads = Leads(
            companies=CompanyEntity(companies=[]),
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )  # type: ignore

    async def _report_progress(self, message: str) -> None:
        """Report progress via callback if available."""
        if self.progress_callback:
            await self.progress_callback(message)

    def _parse_name(self, full_name: str) -> tuple[str, str]:
        """
        Parse a full name into first and last name components.

        Args:
            full_name: The full name to parse.

        Returns:
            tuple[str, str]: (first_name, last_name). If only one name part,
                            returns it as first_name with empty last_name.
        """
        if not full_name:
            return ("", "")

        parts = full_name.strip().split()
        if len(parts) == 1:
            return (parts[0], "")
        elif len(parts) == 2:
            return (parts[0], parts[1])
        else:
            # For names with more than 2 parts, assume first part is first name
            # and the rest is last name (e.g., "Jean Pierre Dupont" -> "Jean", "Pierre Dupont")
            return (parts[0], " ".join(parts[1:]))

    def first_step(
        self, state: OverallEnrichLeadsState
    ) -> OverallEnrichLeadsState:
        """
        The first step of the agent, initializing the state with input data.

        Returns:
            EnrichLeadsState: Initial state with input data.
        """
        state["step"] = ["Analysis of the lead's data."]
        self.profile = state["profile"]
        self.leads = state["leads"]
        return state

    def create_enrich_companies_tasks(
        self, state: OverallEnrichLeadsState
    ) -> dict:
        """
        Analyze the company data in the state.
        Returns:
            EnrichLeadsState: Initial state with input data.
        """
        state["step"] = ["Created enrichment tasks for each company."]
        leads: Leads = state["leads"]

        if not leads.companies or not leads.companies.companies:
            return {"companies_tasks": []}

        companies_tasks = [
            Send("make_company_decision", {"company": company})
            for company in leads.companies.companies
        ]

        return {"companies_tasks": companies_tasks}

    def create_enrich_contacts_tasks(
        self, state: OverallEnrichLeadsState
    ) -> dict:
        """
        Analyze the company data in the state.
        Returns:
            EnrichLeadsState: Initial state with input data.
        """
        state["step"] = ["Created enrichment tasks for contacts for each company."]
        leads: Leads = state["leads"]

        if not leads.companies or not leads.companies.companies:
            return {"contacts_tasks": []}

        contacts_tasks = [
            Send("enrich_contacts", {"company": company})
            for company in leads.companies.companies
        ]

        return {"contacts_tasks": contacts_tasks}

    async def _save_contact_immediately(self, contact: Contact) -> bool:
        """
        Save a contact to the database immediately if it does not already exist.

        Deduplication strategy:
        - If contact has email: check by email
        - If contact has no email: check by name + company_id

        Args:
            contact: The contact to potentially save.

        Returns:
            bool: True if contact was saved, False if skipped (duplicate).
        """
        if not self.leads_repository:
            return False

        try:
            # Check for duplicates based on available data
            if contact.email:
                exists = await self.leads_repository.contact_exists_by_email(contact.email)
                if exists:
                    logger.info(
                        f"Contact '{contact.name}' with email(s) {contact.email} already exists, skipping"
                    )
                    return False
            else:
                # No email - check by name and company to avoid duplicates
                exists = await self.leads_repository.contact_exists_by_name_and_company(
                    contact.name, contact.company_id
                )
                if exists:
                    logger.info(
                        f"Contact '{contact.name}' at company {contact.company_id} already exists, skipping"
                    )
                    return False

            saved_contact = await self.leads_repository.save_contact(contact)
            logger.info(f"Streamed contact '{contact.name}' with ID: {saved_contact.id}")
            return True
        except Exception as e:
            logger.error(f"Error saving contact '{contact.name}': {e}")
            return False

    async def _get_linkedin_urls_from_duckduckgo(
        self,
        contact_info: ContactInfo,
        company_name: str,
    ) -> list[str]:
        """
        Search for LinkedIn profile URLs using DuckDuckGo.

        Uses the contact's name and title with fallback strategy:
        1. First tries to search by person name if available
        2. Falls back to job title search if name search fails

        Args:
            contact_info: The contact information with name and title.
            company_name: The company name to narrow the search.

        Returns:
            List of LinkedIn profile URLs found.
        """
        try:
            result = await self.duckduckgo_client.search_with_fallback(
                person_name=contact_info.name,
                job_title=contact_info.title,
                company_name=company_name,
            )

            if result.success and result.urls:
                logger.info(
                    f"DuckDuckGo found {len(result.urls)} LinkedIn URLs "
                    f"for '{contact_info.name}' at '{company_name}'"
                )
                return result.urls

            logger.info(
                f"DuckDuckGo found no LinkedIn URLs for '{contact_info.name}' "
                f"at '{company_name}'"
            )
            return []

        except Exception as e:
            logger.error(
                f"Error searching LinkedIn URLs for '{contact_info.name}': {e}"
            )
            return []

    async def _enrich_contact_bio(
        self,
        contact_info: ContactInfo,
        company_name: str,
    ) -> tuple[str | None, str | None]:
        """
        Search and extract biography information for a contact.

        Args:
            contact_info: The contact information with name and title.
            company_name: The company name for context.

        Returns:
            tuple[str | None, str | None]: (short_description, full_bio).
                Both will be None if bio cannot be extracted.
        """
        first_name, last_name = self._parse_name(contact_info.name)
        if not first_name:
            logger.warning(
                f"Skipping bio search for contact with invalid name: "
                f"'{contact_info.name}'"
            )
            return None, None

        await self._report_progress(f"Searching bio: {contact_info.name}")
        bio_search_result = await self.web_search_client.search_contact_bio(
            first_name=first_name,
            last_name=last_name,
            position=contact_info.title or "",
            company=company_name,
        )

        if not bio_search_result.answer:
            await self._report_progress(
                f"No bio search results for {contact_info.name}"
            )
            return None, None

        await self._report_progress(f"Extracting bio for {contact_info.name}")
        contact_bio = await self.enrich_chain.extract_contact_bio(
            name=contact_info.name,
            position=contact_info.title or "",
            company=company_name,
            search_results=bio_search_result.answer,
        )

        if not contact_bio:
            await self._report_progress(f"No bio extracted for {contact_info.name}")
            return None, None

        await self._report_progress(f"Extracted bio for {contact_info.name}")
        # Truncate short_description to fit VARCHAR(255)
        short_description = (
            contact_bio.short_description[:255]
            if contact_bio.short_description
            else None
        )
        return short_description, contact_bio.full_bio

    async def enrich_contacts(
        self, state: OverallEnrichLeadsState
    ) -> OverallEnrichLeadsState:
        """
        Enrich the contacts data in the state using web search and DuckDuckGo.

        Uses a three-step approach:
        1. Perplexity web search for general contact info (names, emails, phones)
        2. DuckDuckGo HTML search for LinkedIn profile URLs
        3. Perplexity web search for contact biography (short_description, full_bio)

        When leads_repository is provided, contacts are saved immediately as they
        are extracted (streaming mode). When not provided, contacts are collected
        and returned in state (batch mode for backward compatibility).

        Returns state with:
            - enriched_contacts: List of extracted contacts
            - contacts_saved: Number of contacts saved to DB (streaming mode)
            - contacts_skipped: Number of contacts skipped due to dedup (streaming mode)
        """
        company: Company = state["company"]  # type: ignore

        state["step"] = [f"Enriched contact for company: {company.name}"]

        await self._report_progress(f"Extracting target job titles for {company.name}")
        job_titles = await self.enrich_chain.extract_interesting_job_titles_from_profile(
            self.profile
        )
        await self._report_progress(
            f"Found {len(job_titles)} job titles: {', '.join(job_titles[:3])}..."
        )

        contacts = []
        contacts_saved = 0
        contacts_skipped = 0

        # In-memory deduplication: track processed contacts within this run
        # Key: (lowercase_name, tuple of sorted emails) or (lowercase_name, company_id) if no email
        processed_contacts: set[tuple] = set()

        for job_title in job_titles:
            # Step 1: Use Perplexity web search for general contact info
            # (names, emails, phone numbers - no LinkedIn focus)
            await self._report_progress(
                f"Searching contacts: {job_title} at {company.name}"
            )
            web_search_result = await self.web_search_client.search_company_contacts(
                company_name=company.name or "",
                job_title=job_title,
            )

            # Extract contacts from the answer text (Perplexity returns info in answer, not sources)
            if web_search_result.answer:
                await self._report_progress(
                    f"Extracting contacts from search results for {job_title}"
                )
                contact_infos = await self.enrich_chain.extract_contacts_from_answer(
                    company.name or "", web_search_result.answer
                )
                await self._report_progress(
                    f"Found {len(contact_infos)} contacts for {job_title}"
                )

                for contact_info in contact_infos:
                    # === DEDUPLICATION CHECK (before expensive enrichment) ===
                    # Create dedup key based on name and email
                    contact_name_lower = (contact_info.name or "").lower().strip()
                    contact_emails = tuple(sorted(
                        [e.lower() for e in (contact_info.email or [])]
                    ))

                    if contact_emails:
                        dedup_key = (contact_name_lower, contact_emails)
                    else:
                        dedup_key = (contact_name_lower, company.id)

                    # Skip if already processed in this run
                    if dedup_key in processed_contacts:
                        await self._report_progress(
                            f"Skipping duplicate: {contact_info.name} (already processed)"
                        )
                        contacts_skipped += 1
                        continue

                    # Check database early (before expensive API calls)
                    if self.leads_repository:
                        if contact_info.email:
                            exists = await self.leads_repository.contact_exists_by_email(
                                contact_info.email
                            )
                        else:
                            exists = await self.leads_repository.contact_exists_by_name_and_company(
                                contact_info.name, company.id
                            )

                        if exists:
                            await self._report_progress(
                                f"Skipping: {contact_info.name} (already in database)"
                            )
                            processed_contacts.add(dedup_key)
                            contacts_skipped += 1
                            continue

                    # Mark as processed before enrichment
                    processed_contacts.add(dedup_key)

                    await self._report_progress(
                        f"Processing: {contact_info.name} ({contact_info.title})"
                    )

                    # Validate emails
                    valid_email = []
                    for mail in contact_info.email if contact_info.email else []:
                        try:
                            emailinfo = validate_email(
                                mail,
                                check_deliverability=True,
                                dns_resolver=self.resolver,
                            )
                            valid_email.append(emailinfo.email)
                        except EmailNotValidError as e:
                            logger.warning(f"Invalid email {mail}: {e}")

                    # Step 2: Use DuckDuckGo to find LinkedIn URLs
                    # This runs after Perplexity to get more reliable LinkedIn URLs
                    await self._report_progress(
                        f"Searching LinkedIn: {contact_info.name}"
                    )
                    linkedin_urls = await self._get_linkedin_urls_from_duckduckgo(
                        contact_info=contact_info,
                        company_name=company.name or "",
                    )

                    if linkedin_urls:
                        await self._report_progress(
                            f"Found LinkedIn: {linkedin_urls[0]}"
                        )
                    else:
                        await self._report_progress(
                            f"No LinkedIn found for {contact_info.name}"
                        )

                    # Merge LinkedIn URLs: DuckDuckGo results take priority,
                    # fall back to any URLs from Perplexity if DuckDuckGo found none
                    profile_urls = linkedin_urls or contact_info.profile_url or []
                    profile_url_str = ", ".join(profile_urls) if profile_urls else ""

                    # Step 3: Search for contact biography
                    short_description, full_bio = await self._enrich_contact_bio(
                        contact_info=contact_info,
                        company_name=company.name or "",
                    )

                    # Note: We don't assign job_id because in-memory jobs may not
                    # exist in the database yet. Contacts are still useful without
                    # a job association.
                    contact = Contact(
                        company_id=company.id,
                        job_id=None,
                        name=contact_info.name,
                        email=valid_email,
                        title=contact_info.title,
                        phone=contact_info.phone,
                        profile_url=profile_url_str,
                        short_description=short_description,
                        full_bio=full_bio,
                    )  # type: ignore

                    # Validate the contact and apply validation results
                    await self._report_progress(
                        f"Validating: {contact.name}"
                    )
                    validation_result = self.contact_validator.validate_contact(
                        contact=contact,
                        company=company,
                        search_answer=web_search_result.answer or "",
                        searched_job_title=job_title,
                    )
                    contact.confidence_score = validation_result.confidence_score
                    contact.validation_status = validation_result.validation_status.value
                    contact.validation_reasons = validation_result.validation_reasons

                    await self._report_progress(
                        f"Validated: {contact.name} - Score: {validation_result.confidence_score} "
                        f"({validation_result.validation_status.value})"
                    )

                    # Streaming mode: save immediately if repository is available
                    if self.leads_repository is not None:
                        was_saved = await self._save_contact_immediately(contact)
                        if was_saved:
                            contacts_saved += 1
                            await self._report_progress(
                                f"Saved: {contact.name} ({contacts_saved} saved, {contacts_skipped} skipped)"
                            )
                        else:
                            contacts_skipped += 1
                            await self._report_progress(
                                f"Skipped (duplicate): {contact.name}"
                            )

                    contacts.append(contact)

        state["enriched_contacts"] = contacts
        state["contacts_saved"] = contacts_saved
        state["contacts_skipped"] = contacts_skipped
        state["company"] = []

        return state
    
    async def make_company_decision(
        self, state: OverallEnrichLeadsState
    ) -> OverallEnrichLeadsState:
        """
        Make a decision based on the company data in the state.
        Returns:
            EnrichLeadsState: State with decision made.
        """
        company: Company = state["company"]  # type: ignore

        state["step"] = [f"Decision made for company: {company.name}"]

        await self._report_progress(f"Evaluating: {company.name}")
        decision: MakeDecisionResult = await self.decision_chain.decide_enrichment(
            company
        )

        if decision.result:
            await self._report_progress(f"Approved for enrichment: {company.name}")
            state["company"] = [company]
            return state
        await self._report_progress(f"Skipped (not relevant): {company.name}")
        state["company"] = []
        return state

    def create_enrich_company_tasks(self, state: OverallEnrichLeadsState) -> dict:
        """
        Prepare enrichment tasks for each company with a positive decision.

        Returns:
            dict: Dictionary containing the list of enrichment tasks.
        """
        companies = state["company"]

        state["step"] = ["Enrichment tasks for selected companies created."]

        enrich_tasks = [
            Send("enrich_company", {"company": company}) for company in companies
        ]

        return {"enrich_companies_tasks": enrich_tasks}

    async def enrich_company(
        self, state: OverallEnrichLeadsState
    ) -> OverallEnrichLeadsState:
        """
        Enrich the company data in the state using OpenRouter web search.

        OpenRouter web search provides both search results and synthesized content.
        """
        company: Company = state["company"]  # type: ignore

        state["step"] = [f"Enriched company: {company.name}"]

        # Use OpenRouter web search for company info
        # Rate limiting is handled by WebSearchClient's class-level semaphore
        await self._report_progress(f"Searching company info: {company.name}")
        web_search_result = await self.web_search_client.search_company_info(
            company_name=company.name or "",
        )

        # Get combined content from all sources
        pages = [web_search_result.get_combined_content()]

        await self._report_progress(f"Generating description: {company.name}")
        company_description: str = await self.enrich_chain.get_company_description(
            company.name or "", pages
        )

        company_description = re.sub(
            r"<think>.*?</think>", "", company_description, flags=re.DOTALL
        )
        company.description = company_description

        await self._report_progress(f"Extracting company details: {company.name}")
        other_info: CompanyInfo = (
            await self.enrich_chain.extract_other_info_from_description(pages)
        )

        # join for list fields
        company.industry = ", ".join(other_info.industry)
        company.location = ", ".join(other_info.location)
        company.size = other_info.size
        company.revenue = other_info.revenue
        company.compatibility = other_info.compatibility

        await self._report_progress(
            f"Enriched: {company.name} | Industry: {company.industry} | Size: {company.size}"
        )

        state["enriched_company"] = [company]

        state["company"] = []

        return state
    
    def aggregate(
        self, state: OverallEnrichLeadsState
    ) -> OverallEnrichLeadsState:
        """
        Aggregate enriched contacts into the leads data.

        Returns:
            OverallEnrichLeadsState: State with aggregated contacts.
        """
        state["step"] = ["Aggregated enriched data into leads."]
        if "enriched_contacts" in state:
            contacts = state["enriched_contacts"]
            leads: Leads = self.leads # type: ignore
            if not leads.contacts:
                leads.contacts = ContactEntity(contacts=[]) # type: ignore
            leads.contacts.contacts = contacts  # type: ignore

        if "enriched_company" in state:
            companies = state["enriched_company"]
            if not companies:
                leads.companies = CompanyEntity(companies=[]) # type: ignore
            leads: Leads = self.leads # type: ignore
            leads.companies.companies = companies  # type: ignore

        state["leads"] = leads
        return state
