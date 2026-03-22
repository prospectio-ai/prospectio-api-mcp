import asyncio
import logging
from langgraph.types import Send
from config import LLMConfig
from domain.entities.company import Company, CompanyEntity
from domain.entities.contact import Contact, ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from infrastructure.api.llm_client_factory import LLMClientFactory
from infrastructure.services.enrich_leads_agent.chains.decision_chain import (
    DecisionChain,
)
from infrastructure.services.enrich_leads_agent.chains.enrich_chain import EnrichChain
from infrastructure.services.enrich_leads_agent.models.contact_info import ContactInfo
from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo
from infrastructure.services.enrich_leads_agent.models.make_decision import (
    MakeDecisionResult,
)
from infrastructure.services.enrich_leads_agent.state import OverallEnrichLeadsState
from infrastructure.services.enrich_leads_agent.tools.duck_duck_go_client import (
    DuckDuckGoClient,
)
import re
import urllib.parse
from email_validator import validate_email, caching_resolver, EmailNotValidError



logger = logging.getLogger(__name__)


class EnrichLeadsNodes:
    """
    Nodes for the WebSearch agent.
    """

    def __init__(self):
        """
        Initialize the WebSearchNodes with required models and tools.

        Args:
            agent_params (AgentParams): Parameters for agent configuration.
        """
        self.resolver = caching_resolver(timeout=10)
        concurrent_calls = LLMConfig().CONCURRENT_CALLS # type: ignore
        self.semaphore = asyncio.Semaphore(concurrent_calls)
        decision_model = LLMConfig().DECISION_MODEL # type: ignore
        decision_llm_client = LLMClientFactory(
            model=decision_model, config=LLMConfig() # type: ignore
        ).create_client()
        enrich_llm_client = LLMClientFactory(
            model=LLMConfig().ENRICH_MODEL, config=LLMConfig() # type: ignore
        ).create_client()
        self.decision_chain = DecisionChain(decision_llm_client)
        self.enrich_chain = EnrichChain(enrich_llm_client)
        self.profile = Profile(
            job_title=None, location=None, bio=None, work_experience=[]
        ) # type: ignore
        self.leads = Leads(companies=CompanyEntity(companies=[]), contacts=ContactEntity(contacts=[]), jobs=JobEntity(jobs=[])) # type: ignore

    async def first_step(
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

    async def create_enrich_companies_tasks(
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

    async def create_enrich_contacts_tasks(
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

    async def enrich_contacts(
        self, state: OverallEnrichLeadsState
    ) -> OverallEnrichLeadsState:
        """
        Enrich the contacts data in the state.
        """
        company: Company = state["company"] # type: ignore

        state["step"] = [f"Enriched contact for company: {company.name}"]

        job_titles = await self.enrich_chain.extract_interesting_job_titles_from_profile(self.profile)
        search_results = []
        contacts = []
        
        for job_title in job_titles:
            search_results = await DuckDuckGoClient().search(
                f"{company.name} {job_title} site:fr.linkedin.com", 10
            )

            for result in search_results:
                if "/in" in result.url and urllib.parse.urlparse(result.url).path not in ("", "/"):
                    contact_info: ContactInfo = await self.enrich_chain.extract_contact_from_web_search(
                        company.name or '', result
                    ) # type: ignore
                    valid_email = []
                    for mail in contact_info.email if contact_info.email else []:
                        try:
                            emailinfo = validate_email(mail, 
                                                        check_deliverability=True,
                                                        dns_resolver=self.resolver)
                            valid_email.append(emailinfo.email)
                        except EmailNotValidError as e:
                            logger.warning(f"Invalid email {mail}: {e}")
                    for job in self.leads.jobs.jobs: # type: ignore
                        if company.id == job.company_id:
                            contact = Contact(
                                company_id=company.id,
                                job_id=job.id,
                                name=contact_info.name,
                                email=valid_email,
                                title=contact_info.title,
                                phone=contact_info.phone,
                                profile_url=", ".join(contact_info.profile_url)
                            ) # type: ignore
                    contacts.append(contact)

        state["enriched_contacts"] = contacts

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

        decision: MakeDecisionResult = await self.decision_chain.decide_enrichment(
            company
        )

        if decision.result:
            state["company"] = [company]
            return state
        state["company"] = []
        return state

    async def create_enrich_company_tasks(self, state: OverallEnrichLeadsState) -> dict:
        """
        Prépare les tâches d'enrichissement pour chaque entreprise ayant une décision positive.

        Returns:
            dict: Dictionnaire contenant la liste des tâches d'enrichissement.
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
        Enrich the company data in the state.
        """
        company: Company = state["company"]  # type: ignore

        state["step"] = [f"Enriched company: {company.name}"]

        pages = []

        search_results = await DuckDuckGoClient().search(
            f"{company.name} site:pappers.fr", 2
        )
        search_results += await DuckDuckGoClient().search(
            f"{company.name} site:societe.com", 2
        )
        search_results += await DuckDuckGoClient().search(
            f"{company.name} site:annuaire-entreprises.data.gouv.fr", 2
        )

        for result in search_results:
            if urllib.parse.urlparse(result.url).path not in ("", "/"):
                pages.append(result.url)

        company_description: (
            str
        ) = await self.enrich_chain.get_company_description(
            company.name or '', pages
        )

        company_description: str = re.sub(
            r"<think>.*?</think>", "", company_description, flags=re.DOTALL
        )
        company.description = company_description

        other_info: CompanyInfo = await self.enrich_chain.extract_other_info_from_description(pages)

        # join for list fields
        company.industry = ', '.join(other_info.industry)
        company.location = ', '.join(other_info.location)
        company.size = other_info.size
        company.revenue = other_info.revenue
        company.compatibility = other_info.compatibility
        
        state["enriched_company"] = [company]

        state["company"] = []

        return state
    
    async def aggregate(
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
