"""
Unit tests for the agent registry
"""
import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workforce.registry import (
    get_all_agents,
    get_agent_by_id,
    get_enabled_agents,
    display_badge,
    Agent
)


def test_get_all_agents():
    """Test getting all agents"""
    agents = get_all_agents()

    assert len(agents) >= 5, "Should have at least 5 agents"
    assert all(isinstance(agent, Agent) for agent in agents), "All items should be Agent instances"


def test_agent_structure():
    """Test agent structure has required fields"""
    agents = get_all_agents()

    for agent in agents:
        assert hasattr(agent, 'id'), "Agent must have id"
        assert hasattr(agent, 'name'), "Agent must have name"
        assert hasattr(agent, 'role'), "Agent must have role"
        assert hasattr(agent, 'enabled'), "Agent must have enabled"
        assert hasattr(agent, 'uses_model'), "Agent must declare whether it uses the model"
        assert hasattr(agent, 'coming_soon'), "Agent must have coming_soon"
        assert isinstance(agent.enabled, bool), "enabled must be boolean"
        assert isinstance(agent.uses_model, bool), "uses_model must be boolean"
        assert display_badge(agent, demo_mode=True) in {"Demo", "Coming soon"}
        assert display_badge(agent, demo_mode=False) in {"Demo", "Real AI", "Coming soon"}


def test_get_agent_by_id():
    """Test getting agent by ID"""
    # Test valid IDs
    coach = get_agent_by_id("coach")
    assert coach is not None, "Coach agent should exist"
    assert coach.id == "coach"
    assert coach.name == "AIHive Coach"

    tutor = get_agent_by_id("tutor")
    assert tutor is not None, "Tutor agent should exist"
    assert tutor.id == "tutor"
    assert tutor.name == "AIHive Tutor"

    # Test invalid ID
    invalid = get_agent_by_id("nonexistent")
    assert invalid is None, "Should return None for invalid ID"


def test_get_enabled_agents():
    """Test getting only enabled agents"""
    enabled_agents = get_enabled_agents()

    # All enabled agents should have enabled=True
    assert all(agent.enabled for agent in enabled_agents), "All returned agents should be enabled"

    # Coach and Tutor should be enabled
    enabled_ids = [agent.id for agent in enabled_agents]
    assert "coach" in enabled_ids, "Coach should be enabled"
    assert "tutor" in enabled_ids, "Tutor should be enabled"


def test_coach_agent_details():
    """Test Coach agent specific details"""
    coach = get_agent_by_id("coach")

    assert coach.uses_model is True, "Coach should be model-backed"
    assert coach.enabled is True, "Coach should be enabled"
    assert coach.coming_soon is False
    assert coach.navigation_target == "AIHive Coach", "Coach should have correct navigation target"
    assert display_badge(coach, demo_mode=True) == "Demo"
    assert display_badge(coach, demo_mode=False) == "Real AI"


def test_tutor_agent_details():
    """Test Tutor agent specific details"""
    tutor = get_agent_by_id("tutor")

    assert tutor.uses_model is True, "Tutor should be model-backed"
    assert tutor.enabled is True, "Tutor should be enabled"
    assert tutor.navigation_target == "Start Learning", "Tutor should have correct navigation target"
    assert display_badge(tutor, demo_mode=True) == "Demo"
    assert display_badge(tutor, demo_mode=False) == "Real AI"


def test_finance_agent_details():
    """Test Finance agent is linked to the Finance Assistant page"""
    finance = get_agent_by_id("finance")

    assert finance is not None, "Finance agent should exist"
    assert finance.uses_model is True, "Finance Money Coach is model-backed"
    assert finance.enabled is True, "Finance should be enabled"
    assert finance.navigation_target == "Finance Assistant", \
        "Finance should navigate to Finance Assistant"
    assert "education" in finance.role.lower() or "budgeting" in finance.role.lower()
    assert display_badge(finance, demo_mode=True) == "Demo"
    assert display_badge(finance, demo_mode=False) == "Real AI"


def test_coming_soon_agents():
    """Test coming soon agents are disabled"""
    all_agents = get_all_agents()

    coming_soon_agents = [agent for agent in all_agents if agent.coming_soon]

    # All coming soon agents should be disabled
    assert all(not agent.enabled for agent in coming_soon_agents), \
        "All coming-soon agents should be disabled"
    for agent in coming_soon_agents:
        assert display_badge(agent, demo_mode=False) == "Coming soon"
        assert display_badge(agent, demo_mode=True) == "Coming soon"

    finance = get_agent_by_id("finance")
    assert finance is not None, "Finance agent should exist"
    # Verify finance disclaimer in role
    assert "education" in finance.role.lower() or "budgeting" in finance.role.lower(), \
        "Finance agent should mention education/budgeting"


def test_developer_agent_details():
    """Test Developer agent is linked into the app"""
    developer = get_agent_by_id("developer")
    assert developer is not None, "Developer agent should exist"
    assert developer.uses_model is True
    assert developer.enabled is True
    assert developer.navigation_target == "Developer Assistant"
    assert display_badge(developer, demo_mode=True) == "Demo"
    assert display_badge(developer, demo_mode=False) == "Real AI"


def test_marketing_is_template_based_and_stays_demo():
    """Marketing is template-based and must not be labeled AI-powered."""
    marketing = get_agent_by_id("marketing")
    assert marketing is not None
    assert marketing.uses_model is False
    assert marketing.enabled is True
    assert "template" in marketing.role.lower()
    assert display_badge(marketing, demo_mode=True) == "Demo"
    assert display_badge(marketing, demo_mode=False) == "Demo"


def test_display_badge_defaults_to_demo_without_key():
    """Suite runs without OPENAI_API_KEY; model agents should show Demo."""
    for agent in get_all_agents():
        if agent.coming_soon:
            assert display_badge(agent) == "Coming soon"
        else:
            assert display_badge(agent) == "Demo"


def test_display_badge_real_mode_is_honest():
    """When real mode is active, only model-backed agents show Real AI."""
    for agent in get_all_agents():
        badge = display_badge(agent, demo_mode=False)
        if agent.coming_soon:
            assert badge == "Coming soon"
        elif agent.uses_model:
            assert badge == "Real AI"
        else:
            assert badge == "Demo"


def test_display_badge_uses_config_is_demo_mode(monkeypatch):
    """Badge detection should follow config.is_demo_mode(), same as Real AI Active."""
    coach = get_agent_by_id("coach")
    marketing = get_agent_by_id("marketing")

    monkeypatch.setattr("aihive_coach.config.Config.is_demo_mode", classmethod(lambda cls: False))
    assert display_badge(coach) == "Real AI"
    assert display_badge(marketing) == "Demo"

    monkeypatch.setattr("aihive_coach.config.Config.is_demo_mode", classmethod(lambda cls: True))
    assert display_badge(coach) == "Demo"
    assert display_badge(marketing) == "Demo"


def test_agent_uniqueness():
    """Test all agent IDs are unique"""
    agents = get_all_agents()
    ids = [agent.id for agent in agents]

    assert len(ids) == len(set(ids)), "All agent IDs should be unique"


def test_registry_is_single_source():
    """Test registry is single source of truth"""
    # This test verifies the registry module exports a single AGENTS list
    from workforce import registry

    assert hasattr(registry, 'AGENTS'), "Registry should have AGENTS list"
    assert isinstance(registry.AGENTS, list), "AGENTS should be a list"
    assert len(registry.AGENTS) >= 5, "AGENTS should have at least 5 entries"
    # Badge is computed via display_badge, not a hardcoded status field
    assert "status" not in Agent.__dataclass_fields__
    assert "uses_model" in Agent.__dataclass_fields__
