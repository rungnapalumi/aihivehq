"""
CSV export for the user's own budget and expense data.
"""
import csv
import io
from typing import List, Optional
from finance.models import Budget, Expense


def expenses_to_csv(expenses: List[Expense]) -> str:
    """Export expenses to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "category", "amount", "currency", "note", "id"])
    for e in expenses:
        writer.writerow([
            e.expense_date.isoformat(),
            e.category,
            f"{e.amount:.2f}",
            e.currency,
            e.note or "",
            e.id,
        ])
    return buf.getvalue()


def budget_to_csv(budget: Optional[Budget]) -> str:
    """Export budget to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field", "value"])
    if budget is None:
        writer.writerow(["monthly_income", "0"])
        writer.writerow(["currency", "THB"])
        return buf.getvalue()

    writer.writerow(["monthly_income", f"{budget.monthly_income:.2f}"])
    writer.writerow(["currency", budget.currency])
    writer.writerow(["total_expenses", f"{budget.total_expenses():.2f}"])
    writer.writerow(["remaining", f"{budget.remaining():.2f}"])
    writer.writerow([])
    writer.writerow(["category", "amount", "share_pct"])
    shares = budget.category_shares()
    for c in budget.categories:
        share_pct = shares.get(c.name, 0.0) * 100
        writer.writerow([c.name, f"{c.amount:.2f}", f"{share_pct:.1f}"])
    return buf.getvalue()
