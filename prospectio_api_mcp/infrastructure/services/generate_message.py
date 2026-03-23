import logging
import re
from config import LLMConfig
from domain.entities.contact import Contact
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage
from domain.ports.generate_message import GenerateMessagePort
from domain.services.prompt_loader import PromptLoader
from infrastructure.api.llm_client_factory import LLMClientFactory
from langchain.prompts import PromptTemplate
from infrastructure.dto.database.company import Company

logger = logging.getLogger(__name__)


def _parse_raw_message(text: str) -> ProspectMessage:
    """Parse raw LLM text output into a ProspectMessage when structured output fails."""
    lines = text.strip().split("\n")
    subject = ""
    message_lines = []
    found_subject = False

    for line in lines:
        stripped = line.strip()
        if not found_subject and stripped:
            cleaned = re.sub(r"^\*{0,2}(Objet|Subject)\s*:?\s*\*{0,2}\s*", "", stripped, flags=re.IGNORECASE)
            if cleaned != stripped:
                subject = cleaned.strip().strip("*").strip()
                found_subject = True
            elif not subject:
                subject = stripped.strip("*#").strip()
                found_subject = True
        elif found_subject:
            message_lines.append(line)

    message_body = "\n".join(message_lines).strip()
    if not message_body:
        message_body = text.strip()

    return ProspectMessage(subject=subject or "Message", message=message_body)


class GenerateMessageLLM(GenerateMessagePort):

    def __init__(self):
        model = LLMConfig().PROSPECTING_MODEL # type: ignore
        self.llm_client = LLMClientFactory(
            model=model,
            config=LLMConfig(), # type: ignore
        ).create_client()

    async def get_message(
        self, profile: Profile, contact: Contact, company: Company
    ) -> ProspectMessage:
        """
        Generate a prospecting message for a profile against a company description.

        Args:
            profile (Profile): The profile entity.
            contact (Contact): The contact entity to compare against.
            company (Company): The company entity to compare against.

        Returns:
            ProspectMessage: The generated prospecting message.
        """
        prompt = PromptLoader().load_prompt("prospecting_message")
        template = PromptTemplate(
            input_variables=[
                "profile",
                "contact",
                "company"
            ],
            template=prompt,
        )
        invoke_params = {
            "profile": profile,
            "contact": contact,
            "company": company,
        }

        # Try structured output first (tool calling)
        try:
            chain = template | self.llm_client.with_structured_output(ProspectMessage)
            result = await chain.ainvoke(invoke_params)
            return ProspectMessage.model_validate(result)
        except Exception as e:
            logger.warning(f"Structured output failed, falling back to text parsing: {e}")

        # Fallback: invoke without structured output and parse the raw text
        chain = template | self.llm_client
        result = await chain.ainvoke(invoke_params)
        raw_text = result.content if hasattr(result, "content") else str(result)
        return _parse_raw_message(raw_text)
