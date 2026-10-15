"""Baseline: one LlmAgent with every tool."""

from google.adk.agents import LlmAgent

from helpdesk.agents.guards import log_refusals, trim_history
from helpdesk.llm import make_model
from helpdesk.prompts import single_agent_instruction
from helpdesk.tools import ALL_TOOLS


def build_single_agent(model: str | None = None) -> LlmAgent:
    return LlmAgent(
        name="academic_helpdesk",
        description="IIT Jodhpur academic helpdesk: regulations, curriculum, time table, instructor emails.",
        model=make_model(model),
        instruction=single_agent_instruction(),
        tools=ALL_TOOLS,
        before_model_callback=trim_history,
        after_model_callback=log_refusals,
    )
