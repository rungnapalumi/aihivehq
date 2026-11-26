"""
AIHive Developer Agent — Streamlit UI
Three features + session-only history. No SQLite writes.
"""
import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config
from developer.developer_ai import (
    DeveloperAI,
    CostGuardExceeded,
    DEFAULT_SESSION_COST_LIMIT_USD,
    DEMO_LABEL,
)
from developer.models import (
    CodeReviewResult,
    DebugResult,
    ArchitectureResult,
    HistoryEntry,
)

LANGUAGES = [
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "sql",
    "bash",
    "other",
]


def _get_ai() -> DeveloperAI:
    """Lazy AI instance kept off global import side-effects during tests."""
    if "developer_ai_instance" not in st.session_state:
        st.session_state.developer_ai_instance = DeveloperAI()
    return st.session_state.developer_ai_instance


def _ensure_session_state():
    if "developer_history" not in st.session_state:
        st.session_state.developer_history = []
    if "developer_session_cost_usd" not in st.session_state:
        st.session_state.developer_session_cost_usd = 0.0
    if "developer_last_result_md" not in st.session_state:
        st.session_state.developer_last_result_md = None


def _add_history(entry: HistoryEntry):
    st.session_state.developer_history.insert(0, entry)
    # Cap history length for a lean session
    st.session_state.developer_history = st.session_state.developer_history[:30]


def _format_review(result: CodeReviewResult) -> str:
    lines = [f"**Summary:** {result.summary}", ""]
    if result.is_demo:
        lines.append(f"*{DEMO_LABEL}*")
        lines.append("")
    if not result.issues:
        lines.append("No issues reported.")
        return "\n".join(lines)
    for i, issue in enumerate(result.issues, 1):
        lines.append(
            f"**{i}. [{issue.severity.upper()}] {issue.category}** — {issue.description}"
        )
        lines.append(f"Suggested fix: {issue.suggested_fix}")
        lines.append("")
    return "\n".join(lines)


def _format_debug(result: DebugResult) -> str:
    lines = []
    if result.is_demo:
        lines.append(f"*{DEMO_LABEL}*")
        lines.append("")
    lines.append(f"**Likely cause:** {result.likely_cause}")
    lines.append("")
    lines.append("**Steps to verify:**")
    for step in result.verification_steps:
        lines.append(f"- {step}")
    lines.append("")
    lines.append(f"**Suggested fix:** {result.suggested_fix}")
    return "\n".join(lines)


def _format_architecture(result: ArchitectureResult) -> str:
    lines = []
    if result.is_demo:
        lines.append(f"*{DEMO_LABEL}*")
        lines.append("")
    lines.append("**Suggested components:**")
    for c in result.components:
        lines.append(f"- {c}")
    lines.append("")
    lines.append(f"**Data approach:** {result.data_approach}")
    lines.append("")
    lines.append("**Hosting options** (none are required; costs are optional trade-offs):")
    for h in result.hosting_options:
        lines.append(f"- {h}")
    lines.append("")
    lines.append(f"**Trade-offs:** {result.trade_offs}")
    return "\n".join(lines)


def show_developer_page():
    """Main Developer Agent page."""
    _ensure_session_state()
    ai = _get_ai()

    st.title("🛠️ Developer Assistant")
    if config.is_demo_mode() or ai.is_demo:
        st.subheader("Code review, debugging, and architecture (demo)")
        st.warning(f"⚠️ **{DEMO_LABEL}**")
    else:
        st.subheader("Code review, debugging, and architecture guidance")
        st.success("✅ Real model active — gpt-4o-mini (server-side key)")

    st.caption(
        "History is session-only in this browser tab. Nothing is saved to the shared database. "
        f"Session estimated spend: ${st.session_state.developer_session_cost_usd:.6f} "
        f"/ ${DEFAULT_SESSION_COST_LIMIT_USD:.2f} limit"
    )

    tab_review, tab_debug, tab_arch, tab_history = st.tabs(
        ["Code Review", "Debugging Help", "Architecture Helper", "Session History"]
    )

    with tab_review:
        _show_code_review(ai)
    with tab_debug:
        _show_debugging(ai)
    with tab_arch:
        _show_architecture(ai)
    with tab_history:
        _show_history()

    if st.session_state.developer_last_result_md:
        st.markdown("---")
        st.markdown("## Latest result")
        st.markdown(st.session_state.developer_last_result_md)


def _show_code_review(ai: DeveloperAI):
    st.markdown("### Paste code for review")
    with st.form("developer_code_review"):
        language = st.selectbox("Language", LANGUAGES, index=0)
        code = st.text_area(
            "Code",
            height=220,
            placeholder="Paste the code you want reviewed…",
        )
        submitted = st.form_submit_button(
            "🔍 Review Code", type="primary", use_container_width=True
        )

    if submitted:
        if not code or not code.strip():
            st.error("Please paste some code to review.")
            return
        try:
            with st.spinner("Reviewing…"):
                result = ai.review_code(
                    code=code,
                    language=language,
                    session_cost_usd=st.session_state.developer_session_cost_usd,
                )
            st.session_state.developer_session_cost_usd += result.estimated_cost_usd
            md = _format_review(result)
            st.session_state.developer_last_result_md = md
            _add_history(
                HistoryEntry(
                    feature="code_review",
                    title=f"Code review ({language})",
                    result_markdown=md,
                    estimated_cost_usd=result.estimated_cost_usd,
                    is_demo=result.is_demo,
                )
            )
            st.success("Review complete.")
            st.markdown(md)
        except CostGuardExceeded as e:
            st.error(
                f"Session cost guard reached "
                f"(${e.session_cost:.6f} / ${e.limit:.2f}). Start a new browser session to continue."
            )


def _show_debugging(ai: DeveloperAI):
    st.markdown("### Paste an error and related code")
    with st.form("developer_debugging"):
        language = st.selectbox("Language", LANGUAGES, index=0, key="debug_lang")
        error_text = st.text_area(
            "Error / stack trace",
            height=140,
            placeholder="Paste the traceback or error message…",
        )
        code = st.text_area(
            "Related code",
            height=180,
            placeholder="Paste the code involved in the failure…",
        )
        submitted = st.form_submit_button(
            "🐛 Get Debugging Help", type="primary", use_container_width=True
        )

    if submitted:
        if not error_text or not error_text.strip():
            st.error("Please paste an error or stack trace.")
            return
        try:
            with st.spinner("Diagnosing…"):
                result = ai.debug_help(
                    error_text=error_text,
                    code=code or "",
                    language=language,
                    session_cost_usd=st.session_state.developer_session_cost_usd,
                )
            st.session_state.developer_session_cost_usd += result.estimated_cost_usd
            md = _format_debug(result)
            st.session_state.developer_last_result_md = md
            _add_history(
                HistoryEntry(
                    feature="debugging",
                    title=f"Debug ({language})",
                    result_markdown=md,
                    estimated_cost_usd=result.estimated_cost_usd,
                    is_demo=result.is_demo,
                )
            )
            st.success("Diagnosis ready.")
            st.markdown(md)
        except CostGuardExceeded as e:
            st.error(
                f"Session cost guard reached "
                f"(${e.session_cost:.6f} / ${e.limit:.2f}). Start a new browser session to continue."
            )


def _show_architecture(ai: DeveloperAI):
    st.markdown("### Describe the app you want to build")
    st.caption(
        "Suggestions stay simple. Paid hosting is never presented as required — "
        "cost implications are mentioned neutrally."
    )
    with st.form("developer_architecture"):
        requirements = st.text_area(
            "App idea / requirements",
            height=180,
            placeholder="e.g. A personal habit tracker with a simple web UI and local storage…",
        )
        submitted = st.form_submit_button(
            "🏗️ Suggest Architecture", type="primary", use_container_width=True
        )

    if submitted:
        if not requirements or not requirements.strip():
            st.error("Please describe your app idea or requirements.")
            return
        try:
            with st.spinner("Drafting architecture…"):
                result = ai.architecture_help(
                    requirements=requirements,
                    session_cost_usd=st.session_state.developer_session_cost_usd,
                )
            st.session_state.developer_session_cost_usd += result.estimated_cost_usd
            md = _format_architecture(result)
            st.session_state.developer_last_result_md = md
            _add_history(
                HistoryEntry(
                    feature="architecture",
                    title="Architecture suggestion",
                    result_markdown=md,
                    estimated_cost_usd=result.estimated_cost_usd,
                    is_demo=result.is_demo,
                )
            )
            st.success("Architecture draft ready.")
            st.markdown(md)
        except CostGuardExceeded as e:
            st.error(
                f"Session cost guard reached "
                f"(${e.session_cost:.6f} / ${e.limit:.2f}). Start a new browser session to continue."
            )


def _show_history():
    history = st.session_state.get("developer_history", [])
    if not history:
        st.info("No requests yet in this browser session.")
        return
    st.caption("Visible only in this session — cleared when the tab closes.")
    for entry in history:
        label = entry.title
        if entry.is_demo:
            label = f"{label} · demo"
        with st.expander(label, expanded=False):
            st.caption(
                f"{entry.created_at.isoformat(timespec='seconds')} · "
                f"est. ${entry.estimated_cost_usd:.6f}"
            )
            st.markdown(entry.result_markdown)
