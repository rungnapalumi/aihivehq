"""
Assert honest marketplace badges on the public static homepage.

Badges must match workforce/registry.py reality:
- uses_model=True agents -> Available (with Try it when the live app URL is linked)
- uses_model=False (Marketing) -> Demo + scripted-examples note
- AI Workforce stays Future Vision
"""
from pathlib import Path

import pytest

SITE_DIR = Path(__file__).parent
INDEX = SITE_DIR / "index.html"


@pytest.fixture(scope="module")
def index_html() -> str:
    return INDEX.read_text(encoding="utf-8")


def _card_block(html: str, title: str) -> str:
    """Return the HTML substring for one agent card by title."""
    marker = f'<h3 class="agent-title">{title}</h3>'
    start = html.find(marker)
    assert start != -1, f"Missing agent card: {title}"
    # Walk backward to the opening agent-card div
    card_start = html.rfind('<div class="agent-card">', 0, start)
    assert card_start != -1
    card_end = html.find('<div class="agent-card">', start)
    if card_end == -1:
        card_end = html.find("</section>", start)
    return html[card_start:card_end]


def test_hero_preview_shows_available(index_html: str):
    assert "agent-preview-status" in index_html
    # Hero decorative card mirrors Coach (model-backed)
    preview = index_html.split('class="agent-preview-status"', 1)[1][:400]
    assert "Available" in preview
    assert ">Demo<" not in preview


@pytest.mark.parametrize(
    "title,badge_class,badge_text",
    [
        ("AIHive Coach", "badge-available", "Available"),
        ("AIHive Tutor", "badge-available", "Available"),
        ("Finance Agent", "badge-available", "Available"),
        ("Developer Agent", "badge-available", "Available"),
        ("Marketing Agent", "badge-demo", "Demo"),
        ("AI Workforce", "badge-future", "Future Vision"),
    ],
)
def test_marketplace_badge(index_html: str, title: str, badge_class: str, badge_text: str):
    card = _card_block(index_html, title)
    assert f'class="badge {badge_class}"' in card
    assert f">{badge_text}</span>" in card


def test_available_agents_have_try_it_links(index_html: str):
    live = "https://aihive-coach.onrender.com"
    for title in ("AIHive Coach", "AIHive Tutor", "Finance Agent", "Developer Agent"):
        card = _card_block(index_html, title)
        assert live in card
        assert ">Try it</a>" in card


def test_marketing_is_demo_with_scripted_note(index_html: str):
    card = _card_block(index_html, "Marketing Agent")
    assert 'class="badge badge-demo"' in card
    assert ">Demo</span>" in card
    assert "scripted examples" in card.lower()
    assert "AI-powered" not in card


def test_no_coming_soon_for_live_agents(index_html: str):
    for title in (
        "AIHive Coach",
        "AIHive Tutor",
        "Finance Agent",
        "Developer Agent",
        "Marketing Agent",
    ):
        card = _card_block(index_html, title)
        assert "badge-soon" not in card
        assert ">Coming Soon<" not in card


def test_workforce_stays_future_vision(index_html: str):
    card = _card_block(index_html, "AI Workforce")
    assert "Future Vision" in card
    assert "Try it" not in card
