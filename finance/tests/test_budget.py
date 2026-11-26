"""
Unit tests for pure-Python budget math
"""
import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from finance.models import Budget, BudgetCategory
from finance.budget import (
    compute_budget_summary,
    compare_50_30_20,
    build_default_categories,
    monthly_expense_total,
    expenses_by_category,
)
from finance.models import Expense
from datetime import date


def test_compute_budget_summary_totals():
    budget = Budget(
        user_id="u1",
        monthly_income=30000,
        currency="THB",
        categories=[
            BudgetCategory(name="Housing", amount=10000),
            BudgetCategory(name="Food", amount=5000),
            BudgetCategory(name="Savings", amount=3000),
        ],
    )
    summary = compute_budget_summary(budget)

    assert summary["monthly_income"] == 30000
    assert summary["total_expenses"] == 18000
    assert summary["remaining"] == 12000
    assert summary["currency"] == "THB"


def test_category_shares():
    budget = Budget(
        user_id="u1",
        monthly_income=10000,
        categories=[
            BudgetCategory(name="Housing", amount=5000),
            BudgetCategory(name="Food", amount=5000),
        ],
    )
    summary = compute_budget_summary(budget)
    assert abs(summary["category_shares"]["Housing"] - 0.5) < 1e-9
    assert abs(summary["category_shares"]["Food"] - 0.5) < 1e-9


def test_zero_expenses_shares():
    budget = Budget(user_id="u1", monthly_income=10000, categories=[
        BudgetCategory(name="Housing", amount=0),
    ])
    summary = compute_budget_summary(budget)
    assert summary["category_shares"]["Housing"] == 0.0
    assert summary["remaining"] == 10000


def test_compare_50_30_20():
    budget = Budget(
        user_id="u1",
        monthly_income=10000,
        categories=[
            BudgetCategory(name="Housing", amount=4000),
            BudgetCategory(name="Food", amount=1000),
            BudgetCategory(name="Entertainment", amount=2000),
            BudgetCategory(name="Savings", amount=2000),
        ],
    )
    comparison = compare_50_30_20(budget)
    assert len(comparison) == 3
    buckets = {r["bucket"] for r in comparison}
    assert "Needs (≈50%)" in buckets
    assert "Wants (≈30%)" in buckets
    assert "Savings (≈20%)" in buckets

    needs = next(r for r in comparison if "Needs" in r["bucket"])
    assert needs["your_amount"] == 5000  # Housing + Food
    assert needs["rule_of_thumb_pct"] == 50.0


def test_compare_50_30_20_zero_income():
    budget = Budget(user_id="u1", monthly_income=0, categories=[])
    assert compare_50_30_20(budget) == []


def test_build_default_categories():
    cats = build_default_categories({"Housing": 1000, "Food": 500})
    names = [c.name for c in cats]
    assert "Housing" in names
    assert "Food" in names
    assert "Other" in names
    housing = next(c for c in cats if c.name == "Housing")
    assert housing.amount == 1000


def test_monthly_expense_total():
    expenses = [
        Expense(user_id="u1", expense_date=date(2026, 3, 1), category="Food", amount=100),
        Expense(user_id="u1", expense_date=date(2026, 3, 15), category="Transport", amount=50),
        Expense(user_id="u1", expense_date=date(2026, 2, 1), category="Food", amount=999),
    ]
    assert monthly_expense_total(expenses, 2026, 3) == 150
    assert monthly_expense_total(expenses, 2026, 2) == 999


def test_expenses_by_category():
    expenses = [
        Expense(user_id="u1", expense_date=date(2026, 3, 1), category="Food", amount=100),
        Expense(user_id="u1", expense_date=date(2026, 3, 2), category="Food", amount=40),
        Expense(user_id="u1", expense_date=date(2026, 3, 3), category="Transport", amount=20),
    ]
    by_cat = expenses_by_category(expenses, 2026, 3)
    assert by_cat["Food"] == 140
    assert by_cat["Transport"] == 20


def test_default_currency_thb():
    budget = Budget(user_id="u1")
    assert budget.currency == "THB"
