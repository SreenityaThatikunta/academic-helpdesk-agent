"""Entry point for the ADK dev UI: `adk web agent` (mode/model come from .env)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from helpdesk.agents import build_agent  # noqa: E402

root_agent = build_agent()
