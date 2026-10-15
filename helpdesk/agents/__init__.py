"""Agent builders: single-agent baseline (Phase 4) and multi-agent version (Phase 5)."""

from helpdesk import config


def build_agent(mode: str | None = None, model: str | None = None):
    mode = mode or config.MODE
    if mode == "single":
        from helpdesk.agents.single_agent import build_single_agent

        return build_single_agent(model)
    if mode == "multi":
        from helpdesk.agents.multi_agent import build_multi_agent

        return build_multi_agent(model)
    raise ValueError(f"Unknown mode {mode!r} (use 'single' or 'multi')")
