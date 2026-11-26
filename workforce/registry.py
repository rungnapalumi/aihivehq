"""
AIHive Agent Registry
Single source of truth for all AIHive agents
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Agent:
    """Represents an AIHive agent"""
    id: str
    name: str
    role: str  # One-line description
    enabled: bool
    navigation_target: str = None  # Streamlit navigation page name
    # True when the agent can call the real model in non-demo mode.
    # False for scripted/template agents that must never be labeled AI-powered.
    uses_model: bool = True
    coming_soon: bool = False


# Agent Registry - Add new agents here
AGENTS: List[Agent] = [
    Agent(
        id="coach",
        name="AIHive Coach",
        role="Think clearly. Act confidently. Grow daily.",
        enabled=True,
        navigation_target="AIHive Coach",
        uses_model=True,
    ),
    Agent(
        id="tutor",
        name="AIHive Tutor",
        role="Learn step-by-step with adaptive feedback.",
        enabled=True,
        navigation_target="Start Learning",
        uses_model=True,
    ),
    Agent(
        id="marketing",
        name="Marketing Agent",
        role="Marketing strategist that analyzes campaigns, optimizes content, and provides template-based marketing briefs.",
        enabled=True,
        navigation_target="Marketing Agent",
        uses_model=False,
    ),
    Agent(
        id="developer",
        name="Developer Assistant",
        role="Code review, debugging, and architecture guidance.",
        enabled=True,
        navigation_target="Developer Assistant",
        uses_model=True,
    ),
    Agent(
        id="finance",
        name="Finance Assistant",
        role="Personal budgeting and expense tracking (education only).",
        enabled=True,
        navigation_target="Finance Assistant",
        uses_model=True,
    ),
]


def get_all_agents() -> List[Agent]:
    """Get all registered agents"""
    return AGENTS


def get_agent_by_id(agent_id: str) -> Agent:
    """Get agent by ID"""
    for agent in AGENTS:
        if agent.id == agent_id:
            return agent
    return None


def get_enabled_agents() -> List[Agent]:
    """Get only enabled agents"""
    return [agent for agent in AGENTS if agent.enabled]


def _is_demo_mode() -> bool:
    """Same detection the app uses for the 'Real AI Active' sidebar label."""
    from aihive_coach.config import config
    return config.is_demo_mode()


def display_badge(agent: Agent, *, demo_mode: Optional[bool] = None) -> str:
    """Return the honest badge label for an agent.

    Coming-soon agents stay 'Coming soon'. Template/scripted agents stay
    'Demo' even when a server-side API key is configured. Model-backed
    agents show 'Real AI' only when the app is not in demo mode (the same
    check used for 'Real AI Active'). The API key is never read or returned.
    """
    if agent.coming_soon:
        return "Coming soon"
    if not agent.uses_model:
        return "Demo"
    if demo_mode is None:
        demo_mode = _is_demo_mode()
    return "Demo" if demo_mode else "Real AI"
