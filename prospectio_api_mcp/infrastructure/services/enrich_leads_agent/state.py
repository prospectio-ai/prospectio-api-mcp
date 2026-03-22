import profile
from typing import TypedDict
from domain.entities import company
from domain.entities.leads import Leads
from domain.entities.company import Company
from typing import Annotated
import operator

from domain.entities.profile import Profile


class OverallEnrichLeadsState(TypedDict):
    """Type definition for the Enrich Leads Agent state."""

    step: Annotated[list, operator.add]
    leads: Leads
    profile: Profile
    company: Annotated[list, operator.add]
    enriched_company: Annotated[list, operator.add]
    enriched_contacts: Annotated[list, operator.add]
    companies_tasks: list[dict]
    enrich_companies_tasks: list[dict]
    contacts_tasks: list[dict]
    # Streaming mode counters (from enrich_contacts node)
    contacts_saved: int
    contacts_skipped: int
