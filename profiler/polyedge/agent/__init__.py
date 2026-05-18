"""Agent orchestration boundary.

The agent owns the growth loop: inspect readiness, find missing data, schedule
next commands, update candidate factors, write reports, and promote or decay
validated strategy inputs.
"""

from okprofiler.agent import AgentConfig, run_agent

__all__ = ["AgentConfig", "run_agent"]
