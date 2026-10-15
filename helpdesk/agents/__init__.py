"""Agent builders: single-agent baseline (Phase 4) and multi-agent version (Phase 5)."""

from helpdesk import config


def build_agent(mode: str | None = None, model: str | None = None):
    mode = mode or config.MODE
    if mode == "single":
        from helpdesk.agents.single_agent import build_single_agent

        return build_single_agent(model)
    raise ValueError(f"Unknown mode {mode!r} (multi-agent mode arrives in Phase 5)")
