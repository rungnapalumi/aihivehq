"""
AIHive AI Workforce Hub
Main landing page for all AIHive agents
"""
import streamlit as st
import sys
import os
from datetime import datetime
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workforce.registry import get_all_agents, get_enabled_agents, display_badge, Agent
from workforce.database import workforce_db
from aihive_coach.config import config


# Navy theme tokens aligned with aihivehq.com / coach styles.css
_CARD_BG = "#0f1629"
_CARD_BG_RAISED = "#1a2238"
_CARD_BORDER = "rgba(255, 255, 255, 0.08)"
_TITLE = "#e2e8f0"
_BODY = "#94a3b8"
_HEADING = "#f8fafc"


def show_workforce_hub():
    """Display the AI Workforce hub landing page"""

    # Hero section
    st.markdown("<div style='text-align: center; padding: 1rem 0;'>", unsafe_allow_html=True)
    st.title("🏢 AIHive Workforce")

    # Mode-aware subtitle
    if config.is_demo_mode():
        st.subheader("Your AIHive team (Demo)")
    else:
        st.subheader("Your team of AI-powered assistants")

    st.markdown("</div>", unsafe_allow_html=True)

    # Demo mode warning
    if config.is_demo_mode():
        st.warning("""
        ⚠️ **Demo Mode**

        This is a demonstration with scripted responses.
        """)

    st.markdown("---")

    # Agent cards
    if config.is_demo_mode():
        st.markdown("## Your Team")
    else:
        st.markdown("## Your AI Team")

    agents = get_all_agents()

    # Display agents in a grid (2 columns)
    for i in range(0, len(agents), 2):
        col1, col2 = st.columns(2)

        with col1:
            if i < len(agents):
                _render_agent_card(agents[i])

        with col2:
            if i + 1 < len(agents):
                _render_agent_card(agents[i + 1])

    st.markdown("---")

    # Recent activity section
    st.markdown("## 📊 My Recent Activity")

    user_id = st.session_state.get("user_id", "")

    if not user_id:
        st.info("No activity yet. Start a conversation with an agent above!")
    else:
        recent_activities = workforce_db.get_recent_activity(user_id, limit=5)

        if not recent_activities:
            st.info("No activity yet. Start a conversation with an agent above!")
        else:
            for activity in recent_activities:
                _render_activity_item(activity)

    # Footer
    st.markdown("---")
    st.caption("© 2026 AIHiveHQ | Built with Streamlit + SQLite")


def agent_card_html(agent: Agent, *, demo_mode: Optional[bool] = None) -> str:
    """Return navy-themed card HTML for an agent. Does not include any secret values."""
    badge = display_badge(agent, demo_mode=demo_mode)

    if badge == "Real AI":
        status_color = "#10b981"
        status_bg = "rgba(16, 185, 129, 0.15)"
        status_border = "rgba(16, 185, 129, 0.3)"
        status_emoji = "✅"
    elif badge == "Coming soon":
        status_color = "#94a3b8"
        status_bg = "rgba(148, 163, 184, 0.15)"
        status_border = "rgba(148, 163, 184, 0.3)"
        status_emoji = "⏳"
    else:
        # Demo / scripted
        status_color = "#f59e0b"
        status_bg = "rgba(245, 158, 11, 0.15)"
        status_border = "rgba(245, 158, 11, 0.3)"
        status_emoji = "⚠️"

    # Escape text used in HTML to avoid breaking markup; names/roles are ours.
    name = (
        str(agent.name)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    role = (
        str(agent.role)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return f"""
    <div style='
        background: linear-gradient(180deg, {_CARD_BG_RAISED} 0%, {_CARD_BG} 100%);
        border: 1px solid {_CARD_BORDER};
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        height: 100%;
    '>
        <h3 style='margin: 0 0 0.5rem 0; color: {_TITLE}; font-size: 1.15rem; font-weight: 600; line-height: 1.3;'>{name}</h3>
        <p style='color: {_BODY}; margin: 0 0 1rem 0; font-size: 0.95rem; line-height: 1.55;'>{role}</p>
        <div style='
            display: inline-block;
            background: {status_bg};
            color: {status_color};
            border: 1px solid {status_border};
            padding: 0.25rem 0.75rem;
            border-radius: 0.375rem;
            font-size: 0.8rem;
            font-weight: 600;
        '>
            {status_emoji} {badge}
        </div>
    </div>
    """


def _render_agent_card(agent):
    """Render a single agent card"""
    st.markdown(agent_card_html(agent), unsafe_allow_html=True)

    # Action button — type="primary" keeps the theme gradient from styles.css
    if agent.enabled:
        if st.button(
            f"🚀 Open {agent.name}",
            key=f"open_{agent.id}",
            use_container_width=True,
            type="primary"
        ):
            st.session_state.navigation = agent.navigation_target
            st.rerun()
    else:
        st.button(
            f"⏳ Coming Soon",
            key=f"disabled_{agent.id}",
            use_container_width=True,
            disabled=True
        )


def _render_activity_item(activity):
    """Render a single activity item"""
    # Format timestamp
    try:
        dt = datetime.fromisoformat(activity["timestamp"].replace("Z", "+00:00"))
        time_str = dt.strftime("%b %d, %Y at %I:%M %p")
    except Exception:
        time_str = activity["timestamp"]

    title = (
        str(activity["title"])
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    agent_name = (
        str(activity["agent_name"])
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    time_safe = (
        str(time_str)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    st.markdown(f"""
    <div style='
        background: {_CARD_BG_RAISED};
        border: 1px solid {_CARD_BORDER};
        border-left: 3px solid #2563eb;
        padding: 1rem;
        margin-bottom: 0.5rem;
        border-radius: 8px;
    '>
        <div style='display: flex; justify-content: space-between; align-items: start;'>
            <div>
                <strong style='color: {_TITLE};'>{agent_name}</strong>
                <p style='margin: 0.25rem 0 0 0; color: {_TITLE};'>{title}</p>
                <p style='margin: 0.25rem 0 0 0; color: {_BODY}; font-size: 0.85rem;'>{time_safe}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
