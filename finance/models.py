"""
Data Models for AIHive Finance Assistant
Budgets, expenses, and coach Q&A messages
"""
from datetime import datetime, date, timezone
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4


DEFAULT_CATEGORIES = [
    "Housing",
    "Food",
    "Transport",
    "Utilities",
    "Healthcare",
    "Entertainment",
    "Savings",
    "Other",
]

SUPPORTED_CURRENCIES = ["THB", "USD", "EUR", "GBP", "JPY", "SGD"]


class BudgetCategory(BaseModel):
    """A single expense category in a monthly budget"""
    name: str
    amount: float = 0.0


class Budget(BaseModel):
    """A user's monthly budget plan"""
    model_config = ConfigDict(ser_json_timedelta="iso8601")

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    monthly_income: float = 0.0
    currency: str = "THB"
    categories: List[BudgetCategory] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def total_expenses(self) -> float:
        return sum(c.amount for c in self.categories)

    def remaining(self) -> float:
        return self.monthly_income - self.total_expenses()

    def category_shares(self) -> Dict[str, float]:
        """Return category name -> share of total expenses (0-1)."""
        total = self.total_expenses()
        if total <= 0:
            return {c.name: 0.0 for c in self.categories}
        return {c.name: c.amount / total for c in self.categories}


class Expense(BaseModel):
    """A single expense entry"""
    model_config = ConfigDict(ser_json_timedelta="iso8601")

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    expense_date: date
    category: str
    amount: float
    note: str = ""
    currency: str = "THB"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CoachMessage(BaseModel):
    """A message in the money coach Q&A"""
    role: str  # user | assistant
    content: str
    is_demo: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
