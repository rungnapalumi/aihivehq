"""
Unit tests for FinanceDatabase — expense CRUD and per-user isolation
"""
import pytest
import os
import tempfile
from datetime import date
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from finance.database import FinanceDatabase
from finance.models import Budget, BudgetCategory, Expense


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = FinanceDatabase(db_path=path)
    yield db
    os.unlink(path)


def test_save_and_get_budget(temp_db):
    budget = Budget(
        user_id="user1",
        monthly_income=25000,
        currency="THB",
        categories=[BudgetCategory(name="Housing", amount=8000)],
    )
    temp_db.save_budget(budget)
    retrieved = temp_db.get_budget("user1")
    assert retrieved is not None
    assert retrieved.monthly_income == 25000
    assert retrieved.currency == "THB"
    assert len(retrieved.categories) == 1
    assert retrieved.categories[0].name == "Housing"


def test_update_budget(temp_db):
    budget = Budget(user_id="user1", monthly_income=10000, currency="THB", categories=[])
    temp_db.save_budget(budget)
    budget.monthly_income = 20000
    budget.categories = [BudgetCategory(name="Food", amount=3000)]
    temp_db.save_budget(budget)
    retrieved = temp_db.get_budget("user1")
    assert retrieved.monthly_income == 20000
    assert retrieved.categories[0].amount == 3000


def test_budget_isolation(temp_db):
    temp_db.save_budget(Budget(user_id="user1", monthly_income=1000, categories=[]))
    temp_db.save_budget(Budget(user_id="user2", monthly_income=9999, categories=[]))
    assert temp_db.get_budget("user1").monthly_income == 1000
    assert temp_db.get_budget("user2").monthly_income == 9999
    assert temp_db.get_budget("user3") is None


def test_add_and_list_expenses(temp_db):
    e1 = Expense(
        user_id="user1",
        expense_date=date(2026, 3, 1),
        category="Food",
        amount=150,
        note="lunch",
        currency="THB",
    )
    e2 = Expense(
        user_id="user1",
        expense_date=date(2026, 3, 2),
        category="Transport",
        amount=40,
        currency="THB",
    )
    temp_db.add_expense(e1)
    temp_db.add_expense(e2)
    expenses = temp_db.list_expenses("user1")
    assert len(expenses) == 2
    # Newest date first
    assert expenses[0].expense_date == date(2026, 3, 2)


def test_delete_expense(temp_db):
    e = Expense(
        user_id="user1",
        expense_date=date(2026, 3, 1),
        category="Food",
        amount=100,
    )
    temp_db.add_expense(e)
    assert temp_db.delete_expense(e.id, "user1") is True
    assert temp_db.list_expenses("user1") == []
    assert temp_db.delete_expense(e.id, "user1") is False


def test_expense_per_user_isolation(temp_db):
    """Users cannot see or delete each other's expenses."""
    e = Expense(
        user_id="user1",
        expense_date=date(2026, 3, 1),
        category="Food",
        amount=100,
        note="private",
    )
    temp_db.add_expense(e)

    # user2 cannot list user1's expenses
    assert temp_db.list_expenses("user2") == []

    # user2 cannot get user1's expense by id
    assert temp_db.get_expense(e.id, "user2") is None

    # user2 cannot delete user1's expense
    assert temp_db.delete_expense(e.id, "user2") is False

    # user1 still has it
    assert temp_db.get_expense(e.id, "user1") is not None
    assert len(temp_db.list_expenses("user1")) == 1


def test_delete_user_data(temp_db):
    temp_db.save_budget(Budget(user_id="user1", monthly_income=1000, categories=[]))
    temp_db.add_expense(
        Expense(user_id="user1", expense_date=date(2026, 1, 1), category="Food", amount=10)
    )
    temp_db.add_expense(
        Expense(user_id="user2", expense_date=date(2026, 1, 1), category="Food", amount=20)
    )
    deleted = temp_db.delete_user_data("user1")
    assert deleted == 2  # 1 budget + 1 expense
    assert temp_db.get_budget("user1") is None
    assert temp_db.list_expenses("user1") == []
    assert len(temp_db.list_expenses("user2")) == 1
