from langchain_core.prompts import ChatPromptTemplate
from domain.entities.profile import Profile
from domain.services.prompt_loader import PromptLoader
from infrastructure.api.llm_generic_client import LLMGenericClient
from langchain_core.output_parsers import StrOutputParser
from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo
from infrastructure.services.enrich_leads_agent.models.contact_info import ContactInfo, ContactsList
import logging
import traceback
from infrastructure.services.enrich_leads_agent.models.contact_bio import ContactBio
from infrastructure.services.enrich_leads_agent.models.job_titles import JobTitles
from infrastructure.services.enrich_leads_agent.models.search_results_model import SearchResultModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnrichChain:
    """
    A chain that enriches company data using web page content while preserving existing information.
    """

    def __init__(self, llm_client: LLMGenericClient):
        """
        Initialize the EnrichChain with an LLM client.

        Args:
            llm_client: The LLM client to use for enriching company data.
        """

        # Store llm_client for later use
        self.llm_client = llm_client
        self.prompt_loader = PromptLoader()

    async def get_company_description(self, company: str, web_content: list[str]) -> str:
        """
        Use the LLM to generate a company description based on the web content.

        Args:
            company: The name of the company.
            web_content: The web page content about the company.

        Returns:
            str: The generated company description.
        """
        # Create the output parser for structured Company output
        prompt = self.prompt_loader.load_prompt("company_description")
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "user",
                (
                    prompt
                ),
            )
        ])
        self.chain = prompt_template | self.llm_client | StrOutputParser()
        try:
            web_content_str = ""
            if web_content:
                web_content_str = "\n".join(web_content)
            result = await self.chain.ainvoke({"company": company, "web_content": web_content_str})
            return result.strip()
        except Exception as e:
            logger.error(f"Error in get_company_description: {e}\n{traceback.format_exc()}")
            return ""

    async def extract_other_info_from_description(self, web_content: list[str]) -> CompanyInfo:
        """
        Use the LLM to extract all relevant company information from the description and fill the CompanyInfo object.

        Args:
            description (str): The company description text.

        Returns:
            CompanyInfo: The extracted company info, or default values if extraction fails.
        """
        prompt = self.prompt_loader.load_prompt("company_info")
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "user",
                (
                    prompt
                ),
            )
        ])
        chain = prompt_template | self.llm_client.with_structured_output(CompanyInfo)
        try:
            result = await chain.ainvoke({"web_content": web_content})
            return CompanyInfo.model_validate(result)
        except Exception as e:
            logger.error(f"Error in extract_other_info_from_description: {e}\n{traceback.format_exc()}")
            return CompanyInfo(industry=[], compatibility="0", location=[], size="0", revenue="0")

    async def extract_contact_from_web_search(self, company: str, web_search: SearchResultModel) -> ContactInfo | None:
        """
        Extract contacts data for a company from the provided web content.

        Args:
            company (str): The name of the company to extract contacts for.
            web_content (list[str]): The web page content about the company.

        Returns:
            list[dict]: A list of contacts found, each as a dictionary. Returns an empty list if no contacts are found or on error.
        """
        prompt = self.prompt_loader.load_prompt("contact_info")
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "user",
                (
                    prompt
                ),
            )
        ])
        chain = prompt_template | self.llm_client.with_structured_output(ContactInfo)
        try:
            result = await chain.ainvoke({"company": company, "title": web_search.title, "url": web_search.url, "snippet": web_search.snippet})
            return ContactInfo.model_validate(result)
        except Exception as e:
            logger.error(f"Error in extract_contact_from_web_content: {e}\n{traceback.format_exc()}")
            return None

    async def extract_contacts_from_answer(self, company: str, answer: str) -> list[ContactInfo]:
        """
        Extract multiple contacts from a search answer text (e.g., from Perplexity).

        Args:
            company (str): The name of the company.
            answer (str): The full answer text containing contact information.

        Returns:
            list[ContactInfo]: List of extracted contacts.
        """
        if not answer or not answer.strip():
            return []

        prompt = self.prompt_loader.load_prompt("contacts_from_answer")
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "user",
                (
                    prompt
                ),
            )
        ])
        chain = prompt_template | self.llm_client.with_structured_output(ContactsList)
        try:
            result = await chain.ainvoke({"company": company, "answer": answer})
            contacts_list = ContactsList.model_validate(result)
            logger.info(f"Extracted {len(contacts_list.contacts)} contacts from answer")
            return contacts_list.contacts
        except Exception as e:
            logger.error(f"Error in extract_contacts_from_answer: {e}\n{traceback.format_exc()}")
            return []

    async def extract_interesting_job_titles_from_profile(self, profile: Profile) -> list[str]:
        """
        Extract job titles of interesting prospects from the user profile using the LLM.

        Args:
            profile (Profile): The user profile data.

        Returns:
            list[str]: A list of job titles considered interesting prospects. Returns an empty list if none found or on error.
        """
        prompt = self.prompt_loader.load_prompt("job_titles")
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "user",
                (
                    prompt
                ),
            )
        ])
        chain = prompt_template | self.llm_client.with_structured_output(JobTitles)
        try:
            result = await chain.ainvoke({"profile": profile})
            result = JobTitles.model_validate(result)  # Validate the structure
            return result.job_titles
        except Exception as e:
            logger.error(f"Error in extract_interesting_job_titles_from_profile: {e}\n{traceback.format_exc()}")
            return []

    async def extract_contact_bio(
        self,
        name: str,
        position: str,
        company: str,
        search_results: str,
    ) -> ContactBio | None:
        """
        Extract contact biography from search results using the LLM.

        Args:
            name: Full name of the contact.
            position: Job title/position of the contact.
            company: Company where the contact works.
            search_results: The search results text containing bio information.

        Returns:
            ContactBio: The extracted biography, or None if extraction fails.
        """
        if not search_results or not search_results.strip():
            return None

        prompt = self.prompt_loader.load_prompt("contact_bio")
        prompt_template = ChatPromptTemplate.from_messages([("user", prompt)])
        chain = prompt_template | self.llm_client.with_structured_output(ContactBio)
        try:
            result = await chain.ainvoke({
                "name": name,
                "position": position,
                "company": company,
                "search_results": search_results,
            })
            contact_bio = ContactBio.model_validate(result)
            logger.info(
                f"Extracted bio for {name}: "
                f"{len(contact_bio.short_description)} chars short, "
                f"{len(contact_bio.full_bio)} chars full"
            )
            return contact_bio
        except Exception as e:
            logger.error(f"Error in extract_contact_bio: {e}\n{traceback.format_exc()}")
            return None
