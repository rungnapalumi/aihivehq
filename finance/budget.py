"""
Pure-Python budget calculations (no AI).
"""
from typing import Dict, List, Tuple
from finance.models import Budget, BudgetCategory


# Common rule-of-thumb percentages (educational reference only)
RULE_50_30_20 = {
    "Needs (≈50%)": 0.50,
    "Wants (≈30%)": 0.30,
    "Savings (≈20%)": 0.20,
}


def compute_budget_summary(budget: Budget) -> Dict:
    """
    Compute totals, remaining balance, and category shares.
    All math is pure Python — no AI.
    """
    total_expenses = budget.total_expenses()
    remaining = budget.remaining()
    shares = budget.category_shares()

    return {
        "monthly_income": budget.monthly_income,
        "total_expenses": total_expenses,
        "remaining": remaining,
        "currency": budget.currency,
        "category_shares": shares,
        "categories": [
            {"name": c.name, "amount": c.amount, "share": shares.get(c.name, 0.0)}
            for c in budget.categories
        ],
    }


def compare_50_30_20(budget: Budget) -> List[Dict]:
    """
    Compare budget categories against a common 50/30/20 rule of thumb.
    Clearly labelled as educational reference — not a recommendation.

    Mapping heuristic:
      Needs  = Housing + Food + Transport + Utilities + Healthcare
      Wants  = Entertainment + Other
      Savings = Savings
    """
    income = budget.monthly_income
    if income <= 0:
        return []

    needs_names = {"Housing", "Food", "Transport", "Utilities", "Healthcare"}
    wants_names = {"Entertainment", "Other"}
    savings_names = {"Savings"}

    amounts = {c.name: c.amount for c in budget.categories}
    needs = sum(amounts.get(n, 0.0) for n in needs_names)
    wants = sum(amounts.get(n, 0.0) for n in wants_names)
    savings = sum(amounts.get(n, 0.0) for n in savings_names)

    # Unmapped categories go into "Other"/wants for comparison display
    known = needs_names | wants_names | savings_names
    for name, amt in amounts.items():
        if name not in known:
            wants += amt

    return [
        {
            "bucket": "Needs (≈50%)",
            "rule_of_thumb_pct": 50.0,
            "rule_of_thumb_amount": income * 0.50,
            "your_amount": needs,
            "your_pct": (needs / income) * 100,
        },
        {
            "bucket": "Wants (≈30%)",
            "rule_of_thumb_pct": 30.0,
            "rule_of_thumb_amount": income * 0.30,
            "your_amount": wants,
            "your_pct": (wants / income) * 100,
        },
        {
            "bucket": "Savings (≈20%)",
            "rule_of_thumb_pct": 20.0,
            "rule_of_thumb_amount": income * 0.20,
            "your_amount": savings,
            "your_pct": (savings / income) * 100,
        },
    ]


def build_default_categories(amounts: Dict[str, float] = None) -> List[BudgetCategory]:
    """Build default category list, optionally with amounts."""
    from finance.models import DEFAULT_CATEGORIES

    amounts = amounts or {}
    return [
        BudgetCategory(name=name, amount=float(amounts.get(name, 0.0)))
        for name in DEFAULT_CATEGORIES
    ]


def monthly_expense_total(expenses: List, year: int, month: int) -> float:
    """Sum expense amounts for a given year/month."""
    total = 0.0
    for e in expenses:
        d = e.expense_date if hasattr(e, "expense_date") else e.get("expense_date")
        amt = e.amount if hasattr(e, "amount") else e.get("amount", 0)
        if d.year == year and d.month == month:
            total += amt
    return total


def expenses_by_category(expenses: List, year: int = None, month: int = None) -> Dict[str, float]:
    """Aggregate expense amounts by category, optionally filtered by month."""
    result: Dict[str, float] = {}
    for e in expenses:
        d = e.expense_date if hasattr(e, "expense_date") else e.get("expense_date")
        cat = e.category if hasattr(e, "category") else e.get("category")
        amt = e.amount if hasattr(e, "amount") else e.get("amount", 0)
        if year is not None and month is not None:
            if d.year != year or d.month != month:
                continue
        result[cat] = result.get(cat, 0.0) + amt
    return result
