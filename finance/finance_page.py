"""
AIHive Finance Assistant — Main Page
Budget builder, expense tracker, money coach Q&A, and CSV export
"""
import streamlit as st
import sys
import os
from datetime import date, datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config
from finance.database import finance_db
from finance.finance_ai import finance_ai, SESSION_COST_LIMIT_USD, MAX_QA_TURNS
from finance.models import (
    Budget,
    BudgetCategory,
    Expense,
    DEFAULT_CATEGORIES,
    SUPPORTED_CURRENCIES,
)
from finance.budget import (
    compute_budget_summary,
    compare_50_30_20,
    monthly_expense_total,
    expenses_by_category,
)
from finance.export import expenses_to_csv, budget_to_csv


def _init_finance_state():
    """Initialize finance-related session state."""
    if "finance_total_cost" not in st.session_state:
        st.session_state.finance_total_cost = 0.0
    if "finance_qa_turns" not in st.session_state:
        st.session_state.finance_qa_turns = 0
    if "finance_qa_history" not in st.session_state:
        st.session_state.finance_qa_history = []
    if "finance_tab" not in st.session_state:
        st.session_state.finance_tab = "Budget"


def _check_cost_guard() -> tuple:
    """Per-session cost / turn guard. Returns (allowed, message)."""
    if st.session_state.finance_qa_turns >= MAX_QA_TURNS:
        return (
            False,
            f"Session limit reached: {MAX_QA_TURNS} questions maximum. Refresh to start a new session.",
        )
    if st.session_state.finance_total_cost >= SESSION_COST_LIMIT_USD:
        return (
            False,
            f"Session cost limit reached (${SESSION_COST_LIMIT_USD:.2f}). Refresh to start a new session.",
        )
    return (True, "")


def show_finance_page():
    """Main entry point for the Finance Assistant page."""
    _init_finance_state()

    st.title("💰 AIHive Finance Assistant")

    if config.is_demo_mode():
        st.subheader("Personal budgeting and expense tracking (demo)")
        st.warning("⚠️ **Demo Mode** — Scripted responses (not AI-powered)")
    else:
        st.subheader("Personal budgeting and expense tracking")
        st.success("✅ Money Coach active — educational explanations via GPT-4o-mini")

    # Visible educational disclaimer
    st.info(
        "📚 **Educational only — not financial advice.** "
        "This tool helps you organise a personal budget and track expenses. "
        "It does not provide investment, tax, legal, credit, or product advice. "
        "For those topics, consult a licensed professional."
    )

    st.markdown("---")

    # Section navigation
    tabs = st.tabs(["📊 Budget Builder", "🧾 Expense Tracker", "💬 Money Coach", "📥 Export"])

    with tabs[0]:
        _show_budget_builder()
    with tabs[1]:
        _show_expense_tracker()
    with tabs[2]:
        _show_money_coach()
    with tabs[3]:
        _show_export()


def _show_budget_builder():
    """Budget builder: income, categories, totals, chart, optional 50/30/20."""
    st.markdown("### Build your monthly budget")
    st.caption("Enter your income and planned category amounts. All calculations are local (no AI).")

    user_id = st.session_state.user_id
    existing = finance_db.get_budget(user_id)

    default_income = existing.monthly_income if existing else 0.0
    default_currency = existing.currency if existing else "THB"
    existing_amounts = {}
    if existing:
        existing_amounts = {c.name: c.amount for c in existing.categories}

    col1, col2 = st.columns([2, 1])
    with col1:
        income = st.number_input(
            "Monthly income",
            min_value=0.0,
            value=float(default_income),
            step=100.0,
            key="finance_income",
        )
    with col2:
        currency_idx = (
            SUPPORTED_CURRENCIES.index(default_currency)
            if default_currency in SUPPORTED_CURRENCIES
            else 0
        )
        currency = st.selectbox(
            "Currency",
            options=SUPPORTED_CURRENCIES,
            index=currency_idx,
            key="finance_currency",
        )

    st.markdown("#### Expense categories")
    category_amounts = {}
    cols = st.columns(2)
    for i, name in enumerate(DEFAULT_CATEGORIES):
        with cols[i % 2]:
            category_amounts[name] = st.number_input(
                name,
                min_value=0.0,
                value=float(existing_amounts.get(name, 0.0)),
                step=50.0,
                key=f"finance_cat_{name}",
            )

    if st.button("💾 Save Budget", type="primary", key="save_budget_btn"):
        categories = [
            BudgetCategory(name=n, amount=category_amounts[n]) for n in DEFAULT_CATEGORIES
        ]
        budget = Budget(
            user_id=user_id,
            monthly_income=income,
            currency=currency,
            categories=categories,
        )
        if existing:
            budget.id = existing.id
        finance_db.save_budget(budget)
        st.success("Budget saved!")
        st.rerun()

    # Live preview from current form values
    preview = Budget(
        user_id=user_id,
        monthly_income=income,
        currency=currency,
        categories=[
            BudgetCategory(name=n, amount=category_amounts[n]) for n in DEFAULT_CATEGORIES
        ],
    )
    summary = compute_budget_summary(preview)

    st.markdown("---")
    st.markdown("### Budget summary")

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Income", f"{summary['monthly_income']:,.2f} {currency}")
    with m2:
        st.metric("Total expenses", f"{summary['total_expenses']:,.2f} {currency}")
    with m3:
        st.metric("Remaining", f"{summary['remaining']:,.2f} {currency}")

    # Category share chart
    chart_data = {
        c["name"]: c["amount"]
        for c in summary["categories"]
        if c["amount"] > 0
    }
    if chart_data:
        st.markdown("#### Category share")
        # Streamlit bar_chart (pandas is a Streamlit dependency)
        st.bar_chart(chart_data)
        for c in summary["categories"]:
            if c["amount"] > 0:
                st.caption(f"{c['name']}: {c['share']*100:.1f}% ({c['amount']:,.2f} {currency})")
    else:
        st.caption("Enter category amounts to see the share chart.")

    # Optional 50/30/20 comparison
    show_rule = st.checkbox(
        "Show 50/30/20 comparison (common rule of thumb — not a recommendation)",
        value=False,
        key="show_503020",
    )
    if show_rule and income > 0:
        st.markdown("#### 50/30/20 comparison")
        st.caption(
            "This is a **common rule of thumb** used for educational comparison only. "
            "It is **not a recommendation** for your situation."
        )
        comparison = compare_50_30_20(preview)
        for row in comparison:
            st.write(
                f"**{row['bucket']}** — "
                f"rule of thumb ≈ {row['rule_of_thumb_amount']:,.2f} {currency} | "
                f"yours: {row['your_amount']:,.2f} {currency} ({row['your_pct']:.1f}%)"
            )


def _show_expense_tracker():
    """Expense tracker: add / list / delete, monthly summary vs budget."""
    st.markdown("### Track your expenses")
    st.caption("Add expenses with date, category, amount, and an optional note. Data is stored per session user.")

    user_id = st.session_state.user_id
    budget = finance_db.get_budget(user_id)
    currency = budget.currency if budget else st.session_state.get("finance_currency", "THB")

    with st.form("add_expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            exp_date = st.date_input("Date", value=date.today())
            category = st.selectbox("Category", options=DEFAULT_CATEGORIES)
        with c2:
            amount = st.number_input("Amount", min_value=0.01, value=100.0, step=10.0)
            note = st.text_input("Note (optional)", placeholder="e.g. lunch, bus fare")
        submitted = st.form_submit_button("➕ Add Expense", type="primary", use_container_width=True)

    if submitted:
        expense = Expense(
            user_id=user_id,
            expense_date=exp_date,
            category=category,
            amount=amount,
            note=note or "",
            currency=currency,
        )
        finance_db.add_expense(expense)
        st.success(f"Added {amount:,.2f} {currency} — {category}")
        st.rerun()

    expenses = finance_db.list_expenses(user_id)

    # Monthly summary vs budget
    today = date.today()
    month_total = monthly_expense_total(expenses, today.year, today.month)
    st.markdown("### This month vs budget")
    sm1, sm2, sm3 = st.columns(3)
    with sm1:
        st.metric("Spent this month", f"{month_total:,.2f} {currency}")
    with sm2:
        planned = budget.total_expenses() if budget else 0.0
        st.metric("Budgeted expenses", f"{planned:,.2f} {currency}")
    with sm3:
        remaining = (planned - month_total) if budget else 0.0
        st.metric("Budget remaining", f"{remaining:,.2f} {currency}")

    by_cat = expenses_by_category(expenses, today.year, today.month)
    if by_cat:
        st.caption("This month by category: " + ", ".join(f"{k}: {v:,.2f}" for k, v in by_cat.items()))

    st.markdown("### Your expenses")
    if not expenses:
        st.info("No expenses yet. Add your first expense above.")
        return

    for exp in expenses:
        cols = st.columns([2, 2, 2, 3, 1])
        cols[0].write(exp.expense_date.isoformat())
        cols[1].write(exp.category)
        cols[2].write(f"{exp.amount:,.2f} {exp.currency}")
        cols[3].write(exp.note or "—")
        if cols[4].button("🗑️", key=f"del_exp_{exp.id}", help="Delete"):
            finance_db.delete_expense(exp.id, user_id)
            st.rerun()


def _show_money_coach():
    """Money coach Q&A with guardrails and cost guard."""
    st.markdown("### Money Coach Q&A")
    st.caption(
        "Ask about budgeting, expense tracking, and general saving habits. "
        "Investment, tax, legal, credit, and product questions are declined."
    )

    if config.is_demo_mode():
        st.info("**Demo mode – scripted, not AI.** Replies are educational templates.")

    # Show conversation
    for msg in st.session_state.finance_qa_history:
        avatar = "👤" if msg["role"] == "user" else "💰"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a budgeting or saving-habits question...")
    if question:
        allowed, limit_msg = _check_cost_guard()
        if not allowed:
            st.error(limit_msg)
            return

        st.session_state.finance_qa_history.append({"role": "user", "content": question})

        with st.spinner("Thinking..."):
            answer, cost_info = finance_ai.answer(
                question, st.session_state.finance_qa_history[:-1]
            )

        # Cost tracking (numbers only already logged inside finance_ai for real mode)
        if cost_info.get("cost_usd", 0) > 0:
            st.session_state.finance_total_cost += cost_info["cost_usd"]
        st.session_state.finance_qa_turns += 1

        st.session_state.finance_qa_history.append({"role": "assistant", "content": answer})
        st.rerun()

    if not config.is_demo_mode() and st.session_state.finance_total_cost > 0:
        st.caption(
            f"Session cost (est.): ${st.session_state.finance_total_cost:.4f} USD | "
            f"Questions: {st.session_state.finance_qa_turns}/{MAX_QA_TURNS}"
        )


def _show_export():
    """Export the user's own budget and expenses as CSV."""
    st.markdown("### Export your data")
    st.caption("Download CSV files of your budget and expenses. Only your own data is included.")

    user_id = st.session_state.user_id
    budget = finance_db.get_budget(user_id)
    expenses = finance_db.list_expenses(user_id)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    col1, col2 = st.columns(2)
    with col1:
        budget_csv = budget_to_csv(budget)
        st.download_button(
            "📥 Download Budget CSV",
            data=budget_csv,
            file_name=f"finance_budget_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        expenses_csv = expenses_to_csv(expenses)
        st.download_button(
            "📥 Download Expenses CSV",
            data=expenses_csv,
            file_name=f"finance_expenses_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.caption(f"{len(expenses)} expense(s) · budget {'saved' if budget else 'not set yet'}")
