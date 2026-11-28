"""
Database Management for AIHive Coach
Uses SQLite for development with SQLAlchemy ORM
Implements user isolation and privacy
"""
import json
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy import create_engine, Column, String, Text, Boolean, Integer, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, relationship, Session, declarative_base
from config import config
from models import CoachingSession, ActionPlan, Message, APIUsageLog, CoachBooking, SlotUnavailableError

Base = declarative_base()


class DBSession(Base):
    """Database model for coaching sessions"""
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    messages_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    action_plan_id = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)


class DBActionPlan(Base):
    """Database model for action plans"""
    __tablename__ = "action_plans"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    
    goal = Column(Text, nullable=False)
    key_insight = Column(Text, nullable=False)
    next_action = Column(Text, nullable=False)
    target_date = Column(Date, nullable=True)  # Nullable per Round 6 requirement
    success_indicator = Column(Text, nullable=False)
    
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    is_completed = Column(Boolean, default=False)
    
    progress_notes_json = Column(Text, nullable=False, default="[]")
    last_reviewed_at = Column(DateTime, nullable=True)


class DBAPIUsageLog(Base):
    """Database model for API usage tracking"""
    __tablename__ = "api_usage_logs"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    estimated_cost_usd = Column(Float, nullable=False)



class DBCoachBooking(Base):
    """Persisted Coach or Tutor session booking (one shared table and slot pool).

    slot_key is unique among *active* rows because expired holds are deleted.
    A partial unique index enforces one free trial per email per service (coach/tutor).
    Coach and Tutor share the same calendar and evening window, so overlap is
    checked across both services in application code.
    """
    __tablename__ = "coach_bookings"
    __table_args__ = (
        UniqueConstraint("slot_key", name="uq_coach_bookings_slot_key"),
        Index(
            "uq_coach_bookings_trial_email_service",
            "customer_email_normalized",
            "service_type",
            unique=True,
            sqlite_where=text("session_kind = 'trial' AND status IN ('pending', 'confirmed')"),
        ),
    )

    id = Column(String, primary_key=True)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_email_normalized = Column(String, nullable=False, default="")
    topic = Column(Text, nullable=True)
    slot_key = Column(String, nullable=False)
    slot_start_utc = Column(DateTime, nullable=False)
    slot_end_utc = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    calendar_uid = Column(String, nullable=True)
    calendar_synced = Column(Boolean, default=False)
    service_type = Column(String, nullable=False, default="coach")
    session_kind = Column(String, nullable=False, default="paid")
    status = Column(String, nullable=False, default="confirmed")
    hold_expires_at = Column(DateTime, nullable=True)
    stripe_checkout_session_id = Column(String, nullable=True)
    stripe_payment_intent_id = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=30)


class Database:
    """Database manager with privacy and isolation"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self._ensure_booking_schema()
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def _get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()
    
    # Session Management
    
    def create_session(self, user_id: str, category: Optional[str] = None) -> CoachingSession:
        """Create a new coaching session"""
        session = CoachingSession(user_id=user_id, category=category)
        
        db_session = DBSession(
            id=session.id,
            user_id=session.user_id,
            category=session.category,
            messages_json=json.dumps([]),
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_completed=False
        )
        
        db = self._get_session()
        try:
            db.add(db_session)
            db.commit()
            return session
        finally:
            db.close()
    
    def get_session(self, session_id: str, user_id: str) -> Optional[CoachingSession]:
        """Get a session by ID (with user isolation)"""
        db = self._get_session()
        try:
            db_session = db.query(DBSession).filter(
                DBSession.id == session_id,
                DBSession.user_id == user_id
            ).first()
            
            if not db_session:
                return None
            
            return self._db_session_to_model(db_session)
        finally:
            db.close()
    
    def save_session(self, session: CoachingSession):
        """Update an existing session"""
        db = self._get_session()
        try:
            db_session = db.query(DBSession).filter(
                DBSession.id == session.id,
                DBSession.user_id == session.user_id
            ).first()
            
            if db_session:
                db_session.messages_json = json.dumps([msg.model_dump(mode='json') for msg in session.messages])
                db_session.updated_at = session.updated_at
                db_session.action_plan_id = session.action_plan_id
                db_session.is_completed = session.is_completed
                db.commit()
        finally:
            db.close()
    
    def list_sessions(self, user_id: str, limit: int = 50) -> List[CoachingSession]:
        """List sessions for a user"""
        db = self._get_session()
        try:
            db_sessions = db.query(DBSession).filter(
                DBSession.user_id == user_id
            ).order_by(DBSession.created_at.desc()).limit(limit).all()
            
            return [self._db_session_to_model(s) for s in db_sessions]
        finally:
            db.close()
    
    # Action Plan Management
    
    def create_action_plan(self, action_plan: ActionPlan) -> ActionPlan:
        """Create a new action plan"""
        db_plan = DBActionPlan(
            id=action_plan.id,
            user_id=action_plan.user_id,
            session_id=action_plan.session_id,
            goal=action_plan.goal,
            key_insight=action_plan.key_insight,
            next_action=action_plan.next_action,
            target_date=action_plan.target_date,
            success_indicator=action_plan.success_indicator,
            created_at=action_plan.created_at,
            updated_at=action_plan.updated_at,
            is_completed=action_plan.is_completed,
            progress_notes_json=json.dumps(action_plan.progress_notes)
        )
        
        db = self._get_session()
        try:
            db.add(db_plan)
            db.commit()
            return action_plan
        finally:
            db.close()
    
    def get_action_plan(self, plan_id: str, user_id: str) -> Optional[ActionPlan]:
        """Get an action plan by ID (with user isolation)"""
        db = self._get_session()
        try:
            db_plan = db.query(DBActionPlan).filter(
                DBActionPlan.id == plan_id,
                DBActionPlan.user_id == user_id
            ).first()
            
            if not db_plan:
                return None
            
            return self._db_plan_to_model(db_plan)
        finally:
            db.close()
    
    def update_action_plan(self, action_plan: ActionPlan):
        """Update an existing action plan"""
        db = self._get_session()
        try:
            db_plan = db.query(DBActionPlan).filter(
                DBActionPlan.id == action_plan.id,
                DBActionPlan.user_id == action_plan.user_id
            ).first()
            
            if db_plan:
                db_plan.goal = action_plan.goal
                db_plan.key_insight = action_plan.key_insight
                db_plan.next_action = action_plan.next_action
                db_plan.target_date = action_plan.target_date
                db_plan.success_indicator = action_plan.success_indicator
                db_plan.updated_at = action_plan.updated_at
                db_plan.is_completed = action_plan.is_completed
                db_plan.progress_notes_json = json.dumps(action_plan.progress_notes)
                db_plan.last_reviewed_at = action_plan.last_reviewed_at
                db.commit()
        finally:
            db.close()
    
    def list_action_plans(self, user_id: str, limit: int = 50) -> List[ActionPlan]:
        """List action plans for a user"""
        db = self._get_session()
        try:
            db_plans = db.query(DBActionPlan).filter(
                DBActionPlan.user_id == user_id
            ).order_by(DBActionPlan.created_at.desc()).limit(limit).all()
            
            return [self._db_plan_to_model(plan) for plan in db_plans]
        except Exception as e:
            raise e
    
    def delete_user_data(self, user_id: str, data_type: str = "all") -> int:
        """Delete user data - returns count deleted"""
        db = self._get_session()
        deleted = 0
        try:
            if data_type in ["all", "sessions"]:
                sessions = db.query(DBSession).filter(DBSession.user_id == user_id).all()
                deleted += len(sessions)
                for s in sessions:
                    db.delete(s)
            if data_type in ["all", "action_plans"]:
                plans = db.query(DBActionPlan).filter(DBActionPlan.user_id == user_id).all()
                deleted += len(plans)
                for p in plans:
                    db.delete(p)
            db.commit()
            return deleted
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def export_user_data_json(self, user_id: str) -> dict:
        """Export all user data as JSON (only for the specified user)"""
        from datetime import timezone
        db = self._get_session()
        try:
            sessions = db.query(DBSession).filter(DBSession.user_id == user_id).all()
            plans = db.query(DBActionPlan).filter(DBActionPlan.user_id == user_id).all()
            
            export_data = {
                "user_id": user_id,
                "export_date": datetime.now(timezone.utc).isoformat(),
                "sessions": [],
                "action_plans": []
            }
            
            for s in sessions:
                export_data["sessions"].append({
                    "id": s.id,
                    "category": s.category,
                    "messages": json.loads(s.messages_json),
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "action_plan_id": s.action_plan_id,
                    "is_completed": s.is_completed
                })
            
            for p in plans:
                export_data["action_plans"].append({
                    "id": p.id,
                    "session_id": p.session_id,
                    "goal": p.goal,
                    "key_insight": p.key_insight,
                    "next_action": p.next_action,
                    "target_date": p.target_date.isoformat() if p.target_date else None,
                    "success_indicator": p.success_indicator,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat(),
                    "is_completed": p.is_completed,
                    "progress_notes": json.loads(p.progress_notes_json),
                    "last_reviewed_at": p.last_reviewed_at.isoformat() if p.last_reviewed_at else None
                })
            
            return export_data
        finally:
            db.close()
    
    def export_user_data_csv(self, user_id: str) -> dict:
        """Export user data as CSV-ready data (simplified format)"""
        db = self._get_session()
        try:
            plans = db.query(DBActionPlan).filter(DBActionPlan.user_id == user_id).all()
            
            csv_data = {
                "action_plans": []
            }
            
            for p in plans:
                csv_data["action_plans"].append({
                    "Goal": p.goal,
                    "Key Insight": p.key_insight,
                    "Next Action": p.next_action,
                    "Target Date": p.target_date.isoformat() if p.target_date else "",
                    "Success Indicator": p.success_indicator,
                    "Status": "Completed" if p.is_completed else "In Progress",
                    "Created": p.created_at.strftime("%Y-%m-%d"),
                    "Updated": p.updated_at.strftime("%Y-%m-%d")
                })
            
            return csv_data
        finally:
            db.close()
    
    # API Usage Logging
    
    def log_api_usage(self, log: APIUsageLog):
        """Log API usage for cost tracking"""
        if not config.LOG_API_USAGE:
            return
        
        db_log = DBAPIUsageLog(
            id=log.id,
            session_id=log.session_id,
            timestamp=log.timestamp,
            model=log.model,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            total_tokens=log.total_tokens,
            estimated_cost_usd=log.estimated_cost_usd
        )
        
        db = self._get_session()
        try:
            db.add(db_log)
            db.commit()
        finally:
            db.close()
    
    def get_total_cost(self, days: int = 30) -> float:
        """Get total estimated cost for the last N days"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        db = self._get_session()
        try:
            total = db.query(DBAPIUsageLog).filter(
                DBAPIUsageLog.timestamp >= cutoff
            ).with_entities(
                db.func.sum(DBAPIUsageLog.estimated_cost_usd)
            ).scalar()
            
            return total or 0.0
        finally:
            db.close()
    

    # Coach session bookings

    def _ensure_booking_schema(self) -> None:
        """Add new columns/indexes to older SQLite files (create_all does not alter)."""
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(self.engine)
        if "coach_bookings" not in inspector.get_table_names():
            return
        existing = {col["name"] for col in inspector.get_columns("coach_bookings")}
        statements = []
        wanted = {
            "customer_email_normalized": "ALTER TABLE coach_bookings ADD COLUMN customer_email_normalized VARCHAR DEFAULT ''",
            "service_type": "ALTER TABLE coach_bookings ADD COLUMN service_type VARCHAR DEFAULT 'coach'",
            "session_kind": "ALTER TABLE coach_bookings ADD COLUMN session_kind VARCHAR DEFAULT 'paid'",
            "status": "ALTER TABLE coach_bookings ADD COLUMN status VARCHAR DEFAULT 'confirmed'",
            "hold_expires_at": "ALTER TABLE coach_bookings ADD COLUMN hold_expires_at DATETIME",
            "stripe_checkout_session_id": "ALTER TABLE coach_bookings ADD COLUMN stripe_checkout_session_id VARCHAR",
            "stripe_payment_intent_id": "ALTER TABLE coach_bookings ADD COLUMN stripe_payment_intent_id VARCHAR",
            "duration_minutes": "ALTER TABLE coach_bookings ADD COLUMN duration_minutes INTEGER DEFAULT 30",
        }
        for name, sql in wanted.items():
            if name not in existing:
                statements.append(sql)
        # Always migrate the trial-email unique index to include service_type
        # (Coach and Tutor each get one free trial per email).
        statements.append("DROP INDEX IF EXISTS uq_coach_bookings_trial_email")
        statements.append(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_coach_bookings_trial_email_service "
            "ON coach_bookings (customer_email_normalized, service_type) "
            "WHERE session_kind = 'trial' AND status IN ('pending', 'confirmed')"
        )
        if statements:
            with self.engine.begin() as conn:
                for sql in statements:
                    conn.exec_driver_sql(sql)
                # Backfill normalized emails if the column was just added.
                if "customer_email_normalized" not in existing:
                    conn.exec_driver_sql(
                        "UPDATE coach_bookings SET customer_email_normalized = lower(trim(customer_email)) "
                        "WHERE customer_email_normalized IS NULL OR customer_email_normalized = ''"
                    )
                if "service_type" not in existing:
                    conn.exec_driver_sql(
                        "UPDATE coach_bookings SET service_type = 'coach' "
                        "WHERE service_type IS NULL OR service_type = ''"
                    )

    def _as_naive_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def _as_bangkok(self, value: datetime) -> datetime:
        from zoneinfo import ZoneInfo
        bangkok = ZoneInfo("Asia/Bangkok")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(bangkok)

    def release_expired_holds(self, now: Optional[datetime] = None) -> int:
        """Delete expired pending paid holds so the slot can be booked again."""
        now = now or datetime.now(timezone.utc)
        now_utc = self._as_naive_utc(now)
        db = self._get_session()
        try:
            rows = (
                db.query(DBCoachBooking)
                .filter(
                    DBCoachBooking.status == "pending",
                    DBCoachBooking.hold_expires_at.isnot(None),
                    DBCoachBooking.hold_expires_at <= now_utc,
                )
                .all()
            )
            count = len(rows)
            for row in rows:
                db.delete(row)
            db.commit()
            return count
        finally:
            db.close()

    def release_hold(self, booking_id: str) -> None:
        """Drop a pending hold (cancel or failed checkout). Confirmed rows are left alone."""
        db = self._get_session()
        try:
            row = db.query(DBCoachBooking).filter(DBCoachBooking.id == booking_id).first()
            if row is not None and row.status == "pending":
                db.delete(row)
                db.commit()
        finally:
            db.close()

    def email_has_used_trial(self, email: str, service_type: str = "coach") -> bool:
        from booking import normalize_email, normalize_service_type

        self.release_expired_holds()
        key = normalize_email(email)
        if not key:
            return False
        service_type = normalize_service_type(service_type)
        db = self._get_session()
        try:
            row = (
                db.query(DBCoachBooking.id)
                .filter(
                    DBCoachBooking.session_kind == "trial",
                    DBCoachBooking.status.in_(("pending", "confirmed")),
                    DBCoachBooking.customer_email_normalized == key,
                    DBCoachBooking.service_type == service_type,
                )
                .first()
            )
            return row is not None
        finally:
            db.close()

    def list_occupied_intervals(
        self,
        range_start: datetime,
        range_end: datetime,
        now: Optional[datetime] = None,
        exclude_booking_id: Optional[str] = None,
    ):
        """Return (start, end) of confirmed bookings and unexpired holds. No customer details."""
        self.release_expired_holds(now=now)
        start_utc = self._as_naive_utc(range_start)
        end_utc = self._as_naive_utc(range_end)
        now_utc = self._as_naive_utc(now or datetime.now(timezone.utc))
        db = self._get_session()
        try:
            query = db.query(DBCoachBooking.slot_start_utc, DBCoachBooking.slot_end_utc, DBCoachBooking.id).filter(
                DBCoachBooking.slot_start_utc < end_utc,
                DBCoachBooking.slot_end_utc > start_utc,
                (
                    (DBCoachBooking.status == "confirmed")
                    | (
                        (DBCoachBooking.status == "pending")
                        & (
                            (DBCoachBooking.hold_expires_at.is_(None))
                            | (DBCoachBooking.hold_expires_at > now_utc)
                        )
                    )
                ),
            )
            if exclude_booking_id:
                query = query.filter(DBCoachBooking.id != exclude_booking_id)
            rows = query.all()
            intervals = []
            for start, end, _id in rows:
                intervals.append((self._as_bangkok(start), self._as_bangkok(end)))
            return intervals
        finally:
            db.close()

    def create_booking(
        self,
        customer_name: str,
        customer_email: str,
        topic: Optional[str],
        slot_start: datetime,
        slot_end: datetime,
        session_kind: str = "paid",
        status: str = "confirmed",
        hold_expires_at: Optional[datetime] = None,
        stripe_checkout_session_id: Optional[str] = None,
        service_type: str = "coach",
    ) -> CoachBooking:
        """Save a booking. Raises SlotUnavailableError or TrialAlreadyUsedError."""
        from booking import (
            TrialAlreadyUsedError,
            normalize_email,
            normalize_service_type,
            slot_key as make_slot_key,
            trial_already_used_message,
        )
        from caldav_client import slot_overlaps_busy

        self.release_expired_holds()
        key = make_slot_key(slot_start)
        start_utc = self._as_naive_utc(slot_start)
        end_utc = self._as_naive_utc(slot_end)
        email_key = normalize_email(customer_email)
        service_type = normalize_service_type(service_type)
        duration_minutes = int((slot_end - slot_start).total_seconds() // 60)
        booking = CoachBooking(
            customer_name=customer_name,
            customer_email=customer_email,
            topic=topic,
            slot_key=key,
            slot_start=slot_start,
            slot_end=slot_end,
            service_type=service_type,
            session_kind=session_kind,
            status=status,
            hold_expires_at=hold_expires_at,
            stripe_checkout_session_id=stripe_checkout_session_id,
            duration_minutes=duration_minutes,
        )
        db = self._get_session()
        try:
            if session_kind == "trial" and status in {"pending", "confirmed"}:
                existing_trial = (
                    db.query(DBCoachBooking.id)
                    .filter(
                        DBCoachBooking.session_kind == "trial",
                        DBCoachBooking.status.in_(("pending", "confirmed")),
                        DBCoachBooking.customer_email_normalized == email_key,
                        DBCoachBooking.service_type == service_type,
                    )
                    .first()
                )
                if existing_trial:
                    raise TrialAlreadyUsedError(trial_already_used_message(service_type))
            # Overlap with any active booking (15- and 30-minute slots share the window)
            now_utc = self._as_naive_utc(datetime.now(timezone.utc))
            active = (
                db.query(DBCoachBooking.slot_start_utc, DBCoachBooking.slot_end_utc)
                .filter(
                    DBCoachBooking.slot_start_utc < end_utc,
                    DBCoachBooking.slot_end_utc > start_utc,
                    (
                        (DBCoachBooking.status == "confirmed")
                        | (
                            (DBCoachBooking.status == "pending")
                            & (
                                (DBCoachBooking.hold_expires_at.is_(None))
                                | (DBCoachBooking.hold_expires_at > now_utc)
                            )
                        )
                    ),
                )
                .all()
            )
            intervals = [(self._as_bangkok(a), self._as_bangkok(b)) for a, b in active]
            if slot_overlaps_busy(slot_start, slot_end, intervals):
                raise SlotUnavailableError("That time is no longer available / ช่วงเวลานี้ถูกจองแล้ว")

            existing = db.query(DBCoachBooking.id).filter(DBCoachBooking.slot_key == key).first()
            if existing:
                raise SlotUnavailableError("That time is no longer available / ช่วงเวลานี้ถูกจองแล้ว")
            row = DBCoachBooking(
                id=booking.id,
                customer_name=booking.customer_name,
                customer_email=booking.customer_email,
                customer_email_normalized=email_key,
                topic=booking.topic,
                slot_key=booking.slot_key,
                slot_start_utc=start_utc,
                slot_end_utc=end_utc,
                created_at=booking.created_at.replace(tzinfo=None) if booking.created_at.tzinfo else booking.created_at,
                calendar_uid=None,
                calendar_synced=False,
                service_type=service_type,
                session_kind=session_kind,
                status=status,
                hold_expires_at=self._as_naive_utc(hold_expires_at) if hold_expires_at else None,
                stripe_checkout_session_id=stripe_checkout_session_id,
                duration_minutes=duration_minutes,
            )
            db.add(row)
            db.commit()
            return booking
        except IntegrityError:
            db.rollback()
            # Distinguish trial-email uniqueness from slot uniqueness when possible.
            if session_kind == "trial" and self.email_has_used_trial(customer_email, service_type):
                raise TrialAlreadyUsedError(trial_already_used_message(service_type)) from None
            raise SlotUnavailableError("That time is no longer available / ช่วงเวลานี้ถูกจองแล้ว") from None
        finally:
            db.close()

    def list_booked_slot_starts(self, range_start: datetime, range_end: datetime):
        """Return occupied slot starts in range. No customer details."""
        return [start for start, _end in self.list_occupied_intervals(range_start, range_end)]

    def update_booking_calendar_sync(self, booking_id: str, calendar_uid: Optional[str], synced: bool) -> None:
        db = self._get_session()
        try:
            row = db.query(DBCoachBooking).filter(DBCoachBooking.id == booking_id).first()
            if row is None:
                return
            row.calendar_uid = calendar_uid
            row.calendar_synced = synced
            db.commit()
        finally:
            db.close()

    def update_booking_checkout(self, booking_id: str, stripe_checkout_session_id: str) -> None:
        db = self._get_session()
        try:
            row = db.query(DBCoachBooking).filter(DBCoachBooking.id == booking_id).first()
            if row is None:
                return
            row.stripe_checkout_session_id = stripe_checkout_session_id
            db.commit()
        finally:
            db.close()

    def confirm_paid_booking(
        self,
        booking_id: str,
        stripe_checkout_session_id: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> CoachBooking:
        db = self._get_session()
        try:
            row = db.query(DBCoachBooking).filter(DBCoachBooking.id == booking_id).first()
            if row is None:
                raise ValueError("booking not found")
            row.status = "confirmed"
            row.hold_expires_at = None
            if stripe_checkout_session_id:
                row.stripe_checkout_session_id = stripe_checkout_session_id
            if stripe_payment_intent_id:
                row.stripe_payment_intent_id = stripe_payment_intent_id
            db.commit()
            db.refresh(row)
            return self._db_booking_to_model(row)
        finally:
            db.close()

    def get_booking(self, booking_id: str) -> Optional[CoachBooking]:
        db = self._get_session()
        try:
            row = db.query(DBCoachBooking).filter(DBCoachBooking.id == booking_id).first()
            if row is None:
                return None
            return self._db_booking_to_model(row)
        finally:
            db.close()

    # Helper methods
    
    def _db_session_to_model(self, db_session: DBSession) -> CoachingSession:
        """Convert DB session to Pydantic model"""
        messages_data = json.loads(db_session.messages_json)
        messages = [Message(**msg) for msg in messages_data]
        
        return CoachingSession(
            id=db_session.id,
            user_id=db_session.user_id,
            category=db_session.category,
            messages=messages,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            action_plan_id=db_session.action_plan_id,
            is_completed=db_session.is_completed
        )
    
    def _db_plan_to_model(self, db_plan: DBActionPlan) -> ActionPlan:
        """Convert DB action plan to Pydantic model"""
        progress_notes = json.loads(db_plan.progress_notes_json)
        
        return ActionPlan(
            id=db_plan.id,
            user_id=db_plan.user_id,
            session_id=db_plan.session_id,
            goal=db_plan.goal,
            key_insight=db_plan.key_insight,
            next_action=db_plan.next_action,
            target_date=db_plan.target_date,
            success_indicator=db_plan.success_indicator,
            created_at=db_plan.created_at,
            updated_at=db_plan.updated_at,
            is_completed=db_plan.is_completed,
            progress_notes=progress_notes,
            last_reviewed_at=db_plan.last_reviewed_at
        )


    def _db_booking_to_model(self, row: DBCoachBooking) -> CoachBooking:
        from booking import slot_key as make_slot_key

        start = self._as_bangkok(row.slot_start_utc)
        end = self._as_bangkok(row.slot_end_utc)
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        hold = row.hold_expires_at
        if hold is not None and hold.tzinfo is None:
            hold = hold.replace(tzinfo=timezone.utc)
        return CoachBooking(
            id=row.id,
            customer_name=row.customer_name,
            customer_email=row.customer_email,
            topic=row.topic,
            slot_key=row.slot_key or make_slot_key(start),
            slot_start=start,
            slot_end=end,
            created_at=created,
            calendar_uid=row.calendar_uid,
            calendar_synced=bool(row.calendar_synced),
            service_type=getattr(row, "service_type", None) or "coach",
            session_kind=row.session_kind or "paid",
            status=row.status or "confirmed",
            hold_expires_at=hold,
            stripe_checkout_session_id=row.stripe_checkout_session_id,
            stripe_payment_intent_id=row.stripe_payment_intent_id,
            duration_minutes=row.duration_minutes or int((end - start).total_seconds() // 60),
        )


# Global database instance
db = Database()
