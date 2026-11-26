"""Unit tests for Workforce Hub navy cards and honest badges."""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workforce.hub_page import agent_card_html
from workforce.registry import get_agent_by_id, get_all_agents, display_badge


NAVY_BACKGROUNDS = ("#0f1629", "#1a2238")
TITLE_COLOR = "#e2e8f0"
BODY_COLOR = "#94a3b8"


def test_card_uses_navy_theme_tokens():
    html = agent_card_html(get_agent_by_id("coach"), demo_mode=True)
    assert any(token in html for token in NAVY_BACKGROUNDS)
    assert TITLE_COLOR in html
    assert BODY_COLOR in html
    assert "background: white" not in html
    assert "#f9fafb" not in html
    assert "#6b7280" not in html  # old low-contrast body on white


def test_card_titles_set_explicit_color():
    html = agent_card_html(get_agent_by_id("developer"), demo_mode=False)
    assert "color: #e2e8f0" in html
    assert "Developer Assistant" in html


def test_model_agent_card_badge_depends_on_mode():
    coach = get_agent_by_id("coach")
    demo_html = agent_card_html(coach, demo_mode=True)
    real_html = agent_card_html(coach, demo_mode=False)
    assert "Demo" in demo_html
    assert "Real AI" not in demo_html
    assert "Real AI" in real_html
    assert "⚠️" in demo_html
    assert "✅" in real_html


def test_marketing_card_stays_demo_in_real_mode():
    html = agent_card_html(get_agent_by_id("marketing"), demo_mode=False)
    assert "Demo" in html
    assert "Real AI" not in html
    assert "template-based" in html.lower() or "template" in html.lower()


def test_card_html_never_exposes_secrets():
    for agent in get_all_agents():
        for demo_mode in (True, False, None):
            html = agent_card_html(agent, demo_mode=demo_mode)
            assert "OPENAI_API_KEY" not in html
            assert "OPENAI" not in html
            assert "sk-" not in html
            assert "api_key" not in html.lower()
            # The key value must never be interpolated into the card.
            from aihive_coach.config import config
            if config.OPENAI_API_KEY:
                assert config.OPENAI_API_KEY not in html


def test_default_card_badge_matches_display_badge():
    """With no key in the test env, cards should show Demo."""
    for agent in get_all_agents():
        html = agent_card_html(agent)
        assert display_badge(agent) in html
        if not agent.coming_soon:
            assert "Demo" in html
            assert "Real AI" not in html
