"""
Database Management for AIHive Finance Assistant
SQLite tables for budgets and expenses with per-user isolation
"""
import json
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy import create_engine, Column, String, Text, Float, DateTime, Date
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config
from finance.models import Budget, BudgetCategory, Expense

Base = declarative_base()


class DBBudget(Base):
    """Database model for user budgets"""
    __tablename__ = "finance_budgets"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    monthly_income = Column(Float, nullable=False, default=0.0)
    currency = Column(String, nullable=False, default="THB")
    categories_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class DBExpense(Base):
    """Database model for expense entries"""
    __tablename__ = "finance_expenses"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    expense_date = Column(Date, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(Text, nullable=False, default="")
    currency = Column(String, nullable=False, default="THB")
    created_at = Column(DateTime, nullable=False)


class FinanceDatabase:
    """Database manager for finance data with privacy and isolation"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        return self.SessionLocal()

    # --- Budget CRUD ---

    def save_budget(self, budget: Budget) -> Budget:
        """Create or update a user's budget (one budget per user)."""
        db = self._get_session()
        try:
            existing = db.query(DBBudget).filter(DBBudget.user_id == budget.user_id).first()
            categories_json = json.dumps(
                [{"name": c.name, "amount": c.amount} for c in budget.categories]
            )
            budget.updated_at = datetime.now(timezone.utc)

            if existing:
                existing.monthly_income = budget.monthly_income
                existing.currency = budget.currency
                existing.categories_json = categories_json
                existing.updated_at = budget.updated_at
                budget.id = existing.id
            else:
                db_budget = DBBudget(
                    id=budget.id,
                    user_id=budget.user_id,
                    monthly_income=budget.monthly_income,
                    currency=budget.currency,
                    categories_json=categories_json,
                    created_at=budget.created_at,
                    updated_at=budget.updated_at,
                )
                db.add(db_budget)

            db.commit()
            return budget
        finally:
            db.close()

    def get_budget(self, user_id: str) -> Optional[Budget]:
        """Get a user's budget (user-scoped)."""
        db = self._get_session()
        try:
            db_budget = db.query(DBBudget).filter(DBBudget.user_id == user_id).first()
            if not db_budget:
                return None
            return self._db_budget_to_model(db_budget)
        finally:
            db.close()

    # --- Expense CRUD ---

    def add_expense(self, expense: Expense) -> Expense:
        """Add a new expense entry."""
        db = self._get_session()
        try:
            db_expense = DBExpense(
                id=expense.id,
                user_id=expense.user_id,
                expense_date=expense.expense_date,
                category=expense.category,
                amount=expense.amount,
                note=expense.note or "",
                currency=expense.currency,
                created_at=expense.created_at,
            )
            db.add(db_expense)
            db.commit()
            return expense
        finally:
            db.close()

    def list_expenses(self, user_id: str, limit: int = 200) -> List[Expense]:
        """List expenses for a user (newest first)."""
        db = self._get_session()
        try:
            rows = (
                db.query(DBExpense)
                .filter(DBExpense.user_id == user_id)
                .order_by(DBExpense.expense_date.desc(), DBExpense.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._db_expense_to_model(r) for r in rows]
        finally:
            db.close()

    def get_expense(self, expense_id: str, user_id: str) -> Optional[Expense]:
        """Get a single expense with user isolation."""
        db = self._get_session()
        try:
            row = (
                db.query(DBExpense)
                .filter(DBExpense.id == expense_id, DBExpense.user_id == user_id)
                .first()
            )
            if not row:
                return None
            return self._db_expense_to_model(row)
        finally:
            db.close()

    def delete_expense(self, expense_id: str, user_id: str) -> bool:
        """Delete an expense belonging to the user. Returns True if deleted."""
        db = self._get_session()
        try:
            row = (
                db.query(DBExpense)
                .filter(DBExpense.id == expense_id, DBExpense.user_id == user_id)
                .first()
            )
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()

    def delete_user_data(self, user_id: str) -> int:
        """Delete all finance data for a user — returns count deleted."""
        db = self._get_session()
        try:
            budgets = db.query(DBBudget).filter(DBBudget.user_id == user_id).all()
            expenses = db.query(DBExpense).filter(DBExpense.user_id == user_id).all()
            deleted = len(budgets) + len(expenses)
            for b in budgets:
                db.delete(b)
            for e in expenses:
                db.delete(e)
            db.commit()
            return deleted
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def _db_budget_to_model(self, db_budget: DBBudget) -> Budget:
        cats_data = json.loads(db_budget.categories_json or "[]")
        categories = [BudgetCategory(**c) for c in cats_data]
        return Budget(
            id=db_budget.id,
            user_id=db_budget.user_id,
            monthly_income=db_budget.monthly_income,
            currency=db_budget.currency,
            categories=categories,
            created_at=db_budget.created_at,
            updated_at=db_budget.updated_at,
        )

    def _db_expense_to_model(self, row: DBExpense) -> Expense:
        return Expense(
            id=row.id,
            user_id=row.user_id,
            expense_date=row.expense_date,
            category=row.category,
            amount=row.amount,
            note=row.note or "",
            currency=row.currency,
            created_at=row.created_at,
        )


# Global database instance
finance_db = FinanceDatabase()
