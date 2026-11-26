"""
Unit tests for CSV export of budget and expenses
"""
import sys
import os
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from finance.models import Budget, BudgetCategory, Expense
from finance.export import expenses_to_csv, budget_to_csv


def test_expenses_to_csv():
    expenses = [
        Expense(
            user_id="u1",
            expense_date=date(2026, 3, 1),
            category="Food",
            amount=120.5,
            note="lunch",
            currency="THB",
            id="exp-1",
        )
    ]
    csv_text = expenses_to_csv(expenses)
    assert "date,category,amount,currency,note,id" in csv_text
    assert "2026-03-01" in csv_text
    assert "Food" in csv_text
    assert "120.50" in csv_text
    assert "lunch" in csv_text
    assert "exp-1" in csv_text


def test_expenses_to_csv_empty():
    csv_text = expenses_to_csv([])
    lines = csv_text.strip().split("\n")
    assert len(lines) == 1  # header only


def test_budget_to_csv():
    budget = Budget(
        user_id="u1",
        monthly_income=30000,
        currency="THB",
        categories=[
            BudgetCategory(name="Housing", amount=10000),
            BudgetCategory(name="Food", amount=5000),
        ],
    )
    csv_text = budget_to_csv(budget)
    assert "monthly_income" in csv_text
    assert "30000.00" in csv_text
    assert "THB" in csv_text
    assert "Housing" in csv_text
    assert "Food" in csv_text
    assert "remaining" in csv_text


def test_budget_to_csv_none():
    csv_text = budget_to_csv(None)
    assert "monthly_income" in csv_text
    assert "THB" in csv_text
