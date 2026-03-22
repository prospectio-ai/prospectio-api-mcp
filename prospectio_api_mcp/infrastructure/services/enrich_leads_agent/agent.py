from langgraph.graph import END, START, StateGraph
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from domain.ports.enrich_leads import EnrichLeadsPort
from domain.ports.task_manager import TaskManagerPort
from infrastructure.services.enrich_leads_agent.nodes import EnrichLeadsNodes
from infrastructure.services.enrich_leads_agent.state import OverallEnrichLeadsState


class EnrichLeadsAgent(EnrichLeadsPort):
    """
    An agent that enriches leads using various data sources.
    """

    def __init__(self, task_manager: TaskManagerPort):
        """
        Initialize the AgentWebSearch with required models and tools.

        Args:
            agent_params (AgentParams): Parameters for agent configuration.
        """
        self.EnrichLeadsNodes = EnrichLeadsNodes()
        self.task_manager = task_manager

    def build_graph(self) -> StateGraph:
        """
        Build the agent's state graph pipeline.

        Returns:
            StateGraph: The constructed state graph.
        """
        builder = StateGraph(OverallEnrichLeadsState)

        # Add nodes to the graph
        builder.add_node("first_step", self.EnrichLeadsNodes.first_step)
        builder.add_node(
            "create_enrich_companies_tasks",
            self.EnrichLeadsNodes.create_enrich_companies_tasks,
        )
        builder.add_node(
            "create_enrich_contacts_tasks", self.EnrichLeadsNodes.create_enrich_contacts_tasks
        )
        builder.add_node(
            "enrich_contacts", self.EnrichLeadsNodes.enrich_contacts
        )
        builder.add_node(
            "make_company_decision", self.EnrichLeadsNodes.make_company_decision
        )
        builder.add_node(
            "create_enrich_company_tasks",
            self.EnrichLeadsNodes.create_enrich_company_tasks,
        )
        builder.add_node("enrich_company", self.EnrichLeadsNodes.enrich_company)
        builder.add_node(
            "aggregate", self.EnrichLeadsNodes.aggregate
        )

        # Define the graph structure
        builder.add_edge(START, "first_step")
        builder.add_edge("first_step", "create_enrich_companies_tasks")
        builder.add_edge("first_step", "create_enrich_contacts_tasks")

        builder.add_conditional_edges(
            "create_enrich_companies_tasks",
            lambda state: state["companies_tasks"],
            ["make_company_decision"],
        )

        builder.add_conditional_edges(
            "create_enrich_contacts_tasks",
            lambda state: state["contacts_tasks"],
            ["enrich_contacts"],
        )

        builder.add_edge("make_company_decision", "create_enrich_company_tasks")

        builder.add_conditional_edges(
            "create_enrich_company_tasks",
            lambda state: state["enrich_companies_tasks"],
            ["enrich_company"],
        )

        builder.add_edge("enrich_contacts", "aggregate")

        builder.add_edge("enrich_company", "aggregate")

        builder.add_edge("aggregate", END)


        return builder

    async def execute(self, leads: Leads, profile: Profile, task_uuid: str) -> Leads:
        """
        Compile and return the agent's state graph.

        Returns:
            StateGraph: The compiled agent graph.
        """
        agent = self.build_graph().compile()
        stream = agent.astream(input={"leads": leads, "profile": profile}, stream_mode="updates")
        async for chunk in stream:
            for value in chunk.values():
                step = value.get("step") if isinstance(value, dict) else None
                if step is not None:
                    await self.task_manager.update_task(
                        task_uuid,
                        f"Enrichment step: {step}",
                        "in_progress"
                    )
                aggregate = (
                    value.get("aggregate")
                    if isinstance(value, dict)
                    else None
                )
                if aggregate is not None:
                    enriched_companies = aggregate.get("enriched_companies")
                    enriched_contacts = aggregate.get("enriched_contacts")
                    if enriched_companies is not None:
                        leads.companies.companies = enriched_companies  # type: ignore
                    if enriched_contacts is not None:
                        leads.contacts.contacts = enriched_contacts # type: ignore                       
        return leads
