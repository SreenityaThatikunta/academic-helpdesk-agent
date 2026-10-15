"""Multi-agent version: a routing orchestrator plus policy / schedule / email specialists.

The orchestrator hands a request over with ADK's transfer_to_agent (generated automatically
from `sub_agents` and each agent's `description`). Specialists cannot transfer: when they can,
ADK appends generic transfer instructions to their system prompt that override their own rules
for 8B models (see PROGRESS_LOG Phase 5). As a result every new student message goes back to
the orchestrator to be routed. Mixed requests go to the specialist that can do all of it (the
email and schedule agents can also search the documents).
"""

from google.adk.agents import LlmAgent

from helpdesk import prompts
from helpdesk.agents.guards import (
    drop_transfer_noise,
    log_refusals,
    route_empty_router_reply,
    standardize_router_refusal,
    trim_history,
)
from helpdesk.llm import make_model
from helpdesk.tools import (
    draft_email,
    get_instructor_email,
    get_slot,
    list_courses,
    log_unanswered_question,
    lookup_course,
    search_documents,
)
from helpdesk.tools.retrieval import search_documents_all


def build_multi_agent(model: str | None = None) -> LlmAgent:
    llm = make_model(model)

    def specialist(name: str, instruction: str, tools: list) -> LlmAgent:
        return LlmAgent(
            name=name,
            description=prompts.AGENT_AREAS[name],
            model=llm,
            instruction=instruction,
            tools=[*tools, log_unanswered_question],
            before_model_callback=[trim_history, drop_transfer_noise],
            after_model_callback=log_refusals,
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )

    policy = specialist("policy_agent", prompts.policy_instruction(), [search_documents])
    schedule = specialist("schedule_agent", prompts.schedule_instruction(),
                          [get_slot, lookup_course, list_courses, search_documents_all])
    # search_documents lets the email agent quote the make-up / I-grade rule in a request
    email = specialist("email_agent", prompts.email_instruction(),
                       [get_instructor_email, lookup_course, draft_email, search_documents_all])

    return LlmAgent(
        name="helpdesk_orchestrator",
        description="Routes IIT Jodhpur academic helpdesk requests to the right specialist.",
        model=llm,
        instruction=prompts.orchestrator_instruction(),
        tools=[log_unanswered_question],
        sub_agents=[policy, schedule, email],
        before_model_callback=trim_history,
        after_model_callback=[route_empty_router_reply, log_refusals, standardize_router_refusal],
    )
