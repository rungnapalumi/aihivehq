"""Tests for Coach session booking: slots, double-booking, CalDAV mocks, privacy."""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from booking import (
    BOOKING_HORIZON_DAYS,
    BookingService,
    TrialAlreadyUsedError,
    booking_date_allowed,
    generate_slots_for_date,
    is_canonical_slot,
    slot_key,
    validate_booking_form,
)
from payments import (
    DEFAULT_PLACEHOLDER_PRICE_THB,
    HOLD_MINUTES,
    CheckoutSessionInfo,
    LiveStripeKeyRefused,
    PaymentNotVerifiedError,
    PaymentsNotEnabledError,
    amount_to_stripe_units,
    get_session_price_thb,
    is_payments_enabled,
    is_price_placeholder,
    payment_is_verified,
    price_label_en,
    redact_payment_secrets,
    require_usable_stripe_key,
)
from caldav_client import (
    CalendarSyncError,
    build_vevent,
    is_caldav_configured,
    redact_secrets,
    slot_overlaps_busy,
)
from config import Config, config
from database import Database
from models import SlotUnavailableError


BANGKOK = ZoneInfo("Asia/Bangkok")
UTC = ZoneInfo("UTC")
SECRET = "unit-test-only-secret-xyz"


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path=path)
    yield db
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def future_slot():
    """A canonical slot safely in the booking window (tomorrow 19:00 Bangkok)."""
    tomorrow = datetime.now(BANGKOK).date() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, 19, 0, tzinfo=BANGKOK)


class TestSlotGeneration:
    def test_four_slots_in_bangkok_tz(self):
        day = date(2026, 12, 1)
        now = datetime(2026, 12, 1, 8, 0, tzinfo=BANGKOK)
        slots = generate_slots_for_date(day, now=now)
        assert [s.strftime("%H:%M") for s in slots] == ["19:00", "19:30", "20:00", "20:30"]
        for slot in slots:
            assert slot.tzinfo is not None
            assert slot.astimezone(BANGKOK).tzinfo.key == "Asia/Bangkok"
            assert is_canonical_slot(slot)
            assert (slot + timedelta(minutes=30)).strftime("%H:%M") in {"19:30", "20:00", "20:30", "21:00"}

    def test_past_slots_hidden_same_evening(self):
        now = datetime(2026, 12, 1, 19, 15, tzinfo=BANGKOK)
        slots = generate_slots_for_date(date(2026, 12, 1), now=now)
        assert [s.strftime("%H:%M") for s in slots] == ["19:30", "20:00", "20:30"]

    def test_slot_at_exact_start_is_hidden(self):
        now = datetime(2026, 12, 1, 19, 0, tzinfo=BANGKOK)
        slots = generate_slots_for_date(date(2026, 12, 1), now=now)
        assert [s.strftime("%H:%M") for s in slots] == ["19:30", "20:00", "20:30"]

    def test_after_last_slot_returns_empty(self):
        now = datetime(2026, 12, 1, 21, 0, tzinfo=BANGKOK)
        assert generate_slots_for_date(date(2026, 12, 1), now=now) == []

    def test_utc_evening_is_next_calendar_day_in_bangkok(self):
        # 17:30 UTC on 27 Nov = 00:30 on 28 Nov in Bangkok (UTC+7)
        now = datetime(2026, 11, 27, 17, 30, tzinfo=UTC)
        assert generate_slots_for_date(date(2026, 11, 27), now=now) == []
        slots = generate_slots_for_date(date(2026, 11, 28), now=now)
        assert [s.strftime("%H:%M") for s in slots] == ["19:00", "19:30", "20:00", "20:30"]
        assert all(s.date() == date(2026, 11, 28) for s in slots)

    def test_horizon_includes_today_and_plus_30(self):
        today = date(2026, 11, 27)
        assert booking_date_allowed(today, today=today)
        assert booking_date_allowed(today + timedelta(days=BOOKING_HORIZON_DAYS), today=today)
        assert not booking_date_allowed(today + timedelta(days=BOOKING_HORIZON_DAYS + 1), today=today)
        assert not booking_date_allowed(today - timedelta(days=1), today=today)

    def test_slot_key_is_bangkok_offset(self):
        start = datetime(2026, 12, 1, 19, 0, tzinfo=BANGKOK)
        assert slot_key(start) == "2026-12-01T19:00+07:00"
        # same instant in UTC still maps to the Bangkok key
        assert slot_key(start.astimezone(UTC)) == "2026-12-01T19:00+07:00"


class TestDoubleBooking:
    def test_second_booking_same_slot_is_rejected(self, test_db, future_slot):
        test_db.create_booking(
            customer_name="Ada",
            customer_email="ada@example.com",
            topic="Career",
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=30),
        )
        with pytest.raises(SlotUnavailableError):
            test_db.create_booking(
                customer_name="Bea",
                customer_email="bea@example.com",
                topic="Growth",
                slot_start=future_slot,
                slot_end=future_slot + timedelta(minutes=30),
            )

    def test_unique_constraint_at_database_layer(self, test_db, future_slot):
        from database import DBCoachBooking
        from sqlalchemy.exc import IntegrityError

        test_db.create_booking(
            customer_name="Ada",
            customer_email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=30),
        )
        session = test_db._get_session()
        try:
            session.add(
                DBCoachBooking(
                    id="duplicate-row",
                    customer_name="Bea",
                    customer_email="bea@example.com",
                    customer_email_normalized="bea@example.com",
                    topic="secret topic",
                    slot_key=slot_key(future_slot),
                    slot_start_utc=future_slot.astimezone(UTC).replace(tzinfo=None),
                    slot_end_utc=(future_slot + timedelta(minutes=30)).astimezone(UTC).replace(tzinfo=None),
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    calendar_synced=False,
                    session_kind="paid",
                    status="confirmed",
                    duration_minutes=30,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
        finally:
            session.rollback()
            session.close()

    def test_available_slots_hide_booked_times(self, test_db, future_slot):
        service = BookingService(test_db, calendar_client=None)
        day = future_slot.date()
        before, _ = service.available_slots(day, now=datetime(day.year, day.month, day.day, 8, 0, tzinfo=BANGKOK), include_calendar=False)
        assert future_slot in before
        test_db.create_booking(
            customer_name="Ada",
            customer_email="ada@example.com",
            topic="Private topic",
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=30),
        )
        after, _ = service.available_slots(day, now=datetime(day.year, day.month, day.day, 8, 0, tzinfo=BANGKOK), include_calendar=False)
        assert future_slot not in after
        assert len(after) == len(before) - 1

    def test_other_slots_on_same_day_remain_open(self, test_db, future_slot):
        later = future_slot.replace(hour=20, minute=0)
        test_db.create_booking(
            customer_name="Ada",
            customer_email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=30),
        )
        service = BookingService(test_db)
        slots, _ = service.available_slots(
            future_slot.date(),
            now=datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK),
            include_calendar=False,
        )
        assert later in slots


class TestPrivacy:
    def test_list_booked_slot_starts_returns_only_datetimes(self, test_db, future_slot):
        test_db.create_booking(
            customer_name="Ada Lovelace",
            customer_email="ada-private@example.com",
            topic="Confidential career plan",
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=30),
        )
        starts = test_db.list_booked_slot_starts(
            future_slot.replace(hour=0, minute=0),
            future_slot.replace(hour=0, minute=0) + timedelta(days=1),
        )
        assert len(starts) == 1
        assert isinstance(starts[0], datetime)
        assert slot_key(starts[0]) == slot_key(future_slot)
        blob = repr(starts)
        assert "Ada" not in blob
        assert "ada-private@example.com" not in blob
        assert "Confidential" not in blob

    def test_form_validation(self):
        assert validate_booking_form("", "ada@example.com")
        assert validate_booking_form("Ada", "not-an-email")
        assert validate_booking_form("Ada", "ada@example.com") == []
        assert validate_booking_form("Ada", "ada@example.com", "x" * 501)


class FakeCalendar:
    def __init__(self, busy=None, fail_busy=False, fail_create=False):
        self.busy = list(busy or [])
        self.created = []
        self.fail_busy = fail_busy
        self.fail_create = fail_create

    def busy_intervals(self, start, end):
        if self.fail_busy:
            raise CalendarSyncError("Could not read calendar availability (AuthError)")
        return list(self.busy)

    def create_session_event(self, **kwargs):
        if self.fail_create:
            raise CalendarSyncError("Could not add the booking to the calendar (Error)")
        self.created.append(kwargs)
        return f"uid-{kwargs['booking_id']}"


class TestCalDavMocked:
    def test_build_vevent_puts_email_in_description_not_attendee(self, future_slot):
        ical = build_vevent(
            booking_id="abc123",
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=30),
            customer_name="Ada Lovelace",
            customer_email="ada@example.com",
            topic="Career plan",
        )
        assert "SUMMARY:AIHive Coach session" in ical
        assert "Email: ada@example.com" in ical
        assert "Customer: Ada Lovelace" in ical
        assert "Topic: Career plan" in ical
        assert "ATTENDEE" not in ical
        assert "METHOD:REQUEST" not in ical
        assert "ORGANIZER" not in ical
        assert "TZID=Asia/Bangkok" in ical
        assert future_slot.strftime("%Y%m%dT190000") in ical
        assert (future_slot + timedelta(minutes=30)).strftime("%Y%m%dT193000") in ical

    def test_busy_slot_is_hidden_when_calendar_reports_busy(self, test_db, future_slot):
        cal = FakeCalendar(busy=[(future_slot, future_slot + timedelta(minutes=30))])
        service = BookingService(test_db, calendar_client=cal)
        slots, warning = service.available_slots(
            future_slot.date(),
            now=datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK),
        )
        assert warning is None
        assert future_slot not in slots
        assert future_slot.replace(hour=19, minute=30) in slots

    def test_book_creates_calendar_event_when_configured(self, test_db, future_slot):
        cal = FakeCalendar()
        service = BookingService(test_db, calendar_client=cal)
        result = service.book_trial(
            name="Ada",
            email="ada@example.com",
            topic="Goals",
            slot_start=future_slot,
        )
        assert result.calendar_synced is True
        assert result.calendar_sync_pending is False
        assert "pending" not in result.message_en.lower()
        assert len(cal.created) == 1
        assert cal.created[0]["customer_email"] == "ada@example.com"
        assert cal.created[0]["topic"] == "Goals"
        saved = test_db.get_booking(result.booking.id)
        assert saved.calendar_synced is True

    def test_book_saves_locally_and_says_pending_when_not_configured(self, test_db, future_slot, monkeypatch):
        monkeypatch.delenv("AIHIVE_CALDAV_PASSWORD", raising=False)
        service = BookingService(test_db, calendar_client=None)
        result = service.book_trial(
            name="Ada",
            email="ada@example.com",
            topic=None,
            slot_start=future_slot,
        )
        assert result.calendar_synced is False
        assert result.calendar_sync_pending is True
        assert "calendar sync is pending" in result.message_en.lower()
        assert "ค้างอยู่" in result.message_th
        # Do not claim it was added to the calendar
        assert "was added to the coach" not in result.message_en.lower()

    def test_book_stays_pending_if_create_event_fails(self, test_db, future_slot):
        cal = FakeCalendar(fail_create=True)
        service = BookingService(test_db, calendar_client=cal)
        result = service.book_trial(
            name="Ada",
            email="ada@example.com",
            topic=None,
            slot_start=future_slot,
        )
        assert test_db.get_booking(result.booking.id) is not None
        assert result.calendar_synced is False
        assert result.calendar_sync_pending is True
        assert "pending" in result.message_en.lower()

    def test_book_rejects_slot_busy_on_calendar(self, test_db, future_slot):
        cal = FakeCalendar(busy=[(future_slot, future_slot + timedelta(minutes=30))])
        service = BookingService(test_db, calendar_client=cal)
        with pytest.raises(SlotUnavailableError):
            service.book_trial(name="Ada", email="ada@example.com", topic=None, slot_start=future_slot)

    def test_overlaps_helper(self, future_slot):
        mid = future_slot + timedelta(minutes=15)
        assert slot_overlaps_busy(future_slot, future_slot + timedelta(minutes=30), [(mid, mid + timedelta(minutes=30))])
        later = future_slot + timedelta(hours=2)
        assert not slot_overlaps_busy(future_slot, future_slot + timedelta(minutes=30), [(later, later + timedelta(minutes=30))])


class TestPasswordLeakage:
    def test_redact_secrets_strips_password_and_url_userinfo(self, monkeypatch):
        monkeypatch.setenv("AIHIVE_CALDAV_PASSWORD", SECRET)
        text = f"AuthorizationError at 'https://user:{SECRET}@dav.privateemail.com/', reason no"
        cleaned = redact_secrets(text)
        assert SECRET not in cleaned
        assert ":***@" in cleaned

    def test_config_object_does_not_store_password(self, monkeypatch):
        monkeypatch.setenv("AIHIVE_CALDAV_PASSWORD", SECRET)
        assert SECRET not in repr(config)
        assert SECRET not in repr(config.__dict__)
        assert SECRET not in repr(vars(Config))
        settings = Config.caldav_settings()
        assert SECRET not in repr(settings)
        assert "password" not in settings
        assert "PASSWORD" not in str(settings)

    def test_is_configured_reads_env_but_does_not_expose_password(self, monkeypatch):
        monkeypatch.setenv("AIHIVE_CALDAV_PASSWORD", SECRET)
        monkeypatch.setenv("AIHIVE_CALDAV_URL", "https://dav.privateemail.com/")
        assert is_caldav_configured() is True
        assert Config.is_caldav_configured() is True

    def test_exception_messages_do_not_include_password(self, monkeypatch):
        monkeypatch.setenv("AIHIVE_CALDAV_PASSWORD", SECRET)
        monkeypatch.setenv("PRIVATEEMAIL_PASSWORD", SECRET)

        class Boom(Exception):
            def __str__(self):
                return f"failed https://rungnapa@aihivehq.com:{SECRET}@dav.privateemail.com/"

        from caldav_client import _safe_error_message

        msg = _safe_error_message(Boom(), "Could not connect to the calendar")
        assert SECRET not in msg
        assert "Could not connect to the calendar" in msg

    def test_logger_does_not_emit_password(self, monkeypatch, caplog):
        monkeypatch.setenv("AIHIVE_CALDAV_PASSWORD", SECRET)
        with caplog.at_level(logging.DEBUG, logger="caldav_client"):
            logging.getLogger("caldav_client").info("configured=%s", is_caldav_configured())
            logging.getLogger("caldav_client").debug(redact_secrets(f"pw={SECRET}"))
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert SECRET not in combined


class TestTrialSlots:
    def test_eight_fifteen_minute_slots_fit_window(self):
        day = date(2026, 12, 1)
        now = datetime(2026, 12, 1, 8, 0, tzinfo=BANGKOK)
        slots = generate_slots_for_date(day, now=now, kind="trial")
        assert [s.strftime("%H:%M") for s in slots] == [
            "19:00", "19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45",
        ]
        for slot in slots:
            assert is_canonical_slot(slot, kind="trial")
            assert (slot + timedelta(minutes=15)) <= datetime(2026, 12, 1, 21, 0, tzinfo=BANGKOK)

    def test_trial_past_slots_hidden(self):
        now = datetime(2026, 12, 1, 19, 20, tzinfo=BANGKOK)
        slots = generate_slots_for_date(date(2026, 12, 1), now=now, kind="trial")
        assert [s.strftime("%H:%M") for s in slots] == ["19:30", "19:45", "20:00", "20:15", "20:30", "20:45"]


class TestTrialOncePerEmail:
    def test_second_trial_same_email_is_rejected(self, test_db, future_slot):
        service = BookingService(test_db)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        service.book_trial(
            name="Ada",
            email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            now=now,
        )
        later = future_slot.replace(hour=20, minute=0)
        with pytest.raises(TrialAlreadyUsedError):
            service.book_trial(
                name="Ada",
                email="ADA@example.com",  # case-insensitive
                topic=None,
                slot_start=later,
                now=now,
            )

    def test_different_email_can_still_book_trial(self, test_db, future_slot):
        service = BookingService(test_db)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        service.book_trial(name="Ada", email="ada@example.com", topic=None, slot_start=future_slot, now=now)
        later = future_slot.replace(hour=20, minute=0)
        result = service.book_trial(name="Bea", email="bea@example.com", topic=None, slot_start=later, now=now)
        assert result.kind == "trial"
        assert result.booking.customer_email == "bea@example.com"

    def test_sqlite_rejects_second_trial_email(self, test_db, future_slot):
        test_db.create_booking(
            customer_name="Ada",
            customer_email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            slot_end=future_slot + timedelta(minutes=15),
            session_kind="trial",
            status="confirmed",
        )
        later = future_slot.replace(hour=20, minute=0)
        with pytest.raises(TrialAlreadyUsedError):
            test_db.create_booking(
                customer_name="Ada",
                customer_email="ada@example.com",
                topic=None,
                slot_start=later,
                slot_end=later + timedelta(minutes=15),
                session_kind="trial",
                status="confirmed",
            )


class TestSlotOverlapAcrossKinds:
    def test_trial_at_1915_hides_paid_1900(self, test_db, future_slot):
        trial_start = future_slot.replace(minute=15)
        test_db.create_booking(
            customer_name="Ada",
            customer_email="ada@example.com",
            topic="secret",
            slot_start=trial_start,
            slot_end=trial_start + timedelta(minutes=15),
            session_kind="trial",
            status="confirmed",
        )
        service = BookingService(test_db)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        paid, _ = service.available_slots(future_slot.date(), now=now, kind="paid", include_calendar=False)
        assert future_slot not in paid
        assert future_slot.replace(hour=19, minute=30) in paid
        trials, _ = service.available_slots(future_slot.date(), now=now, kind="trial", include_calendar=False)
        assert trial_start not in trials
        # 19:00–19:15 does not overlap 19:15–19:30, so the earlier trial slot stays free.
        assert future_slot in trials


class FakeStripe:
    def __init__(self, paid=True, url="https://checkout.stripe.com/c/pay/cs_test_fake"):
        self.paid = paid
        self.url = url
        self.created = []
        self.sessions = {}

    def create_session(self, **kwargs):
        sid = f"cs_test_fake_{len(self.created)+1}"
        info = CheckoutSessionInfo(
            id=sid,
            url=self.url,
            payment_status="unpaid",
            status="open",
            metadata={"booking_id": kwargs["booking_id"]},
            amount_total=amount_to_stripe_units(kwargs["price_thb"]),
            currency="thb",
        )
        self.sessions[sid] = {"info": info, "kwargs": kwargs}
        self.created.append(kwargs)
        return info

    def retrieve_session(self, session_id):
        stored = self.sessions[session_id]
        info = stored["info"]
        if self.paid:
            return CheckoutSessionInfo(
                id=info.id,
                url=info.url,
                payment_status="paid",
                status="complete",
                metadata=info.metadata,
                amount_total=info.amount_total,
                currency=info.currency,
                payment_intent="pi_test_fake",
            )
        return info


class TestPaidCheckout:
    def test_paid_without_stripe_is_not_confirmed(self, test_db, future_slot, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("AIHIVE_PAYMENTS_LIVE", raising=False)
        service = BookingService(test_db)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        with pytest.raises(PaymentsNotEnabledError):
            service.start_paid_checkout(
                name="Ada",
                email="ada@example.com",
                topic=None,
                slot_start=future_slot,
                now=now,
            )
        starts = test_db.list_booked_slot_starts(
            future_slot.replace(hour=0, minute=0),
            future_slot.replace(hour=0, minute=0) + timedelta(days=1),
        )
        assert starts == []

    def test_hold_then_confirm_after_verified_payment(self, test_db, future_slot):
        stripe = FakeStripe(paid=True)
        cal = FakeCalendar()
        service = BookingService(test_db, calendar_client=cal, stripe_client=stripe)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        pending = service.start_paid_checkout(
            name="Ada",
            email="ada@example.com",
            topic="Goals",
            slot_start=future_slot,
            now=now,
            success_url="http://localhost/success?session_id={CHECKOUT_SESSION_ID}&booking_id=x",
            cancel_url="http://localhost/cancel",
        )
        assert pending.payment_pending is True
        assert pending.calendar_synced is False
        assert pending.booking.status == "pending"
        assert pending.checkout_url.startswith("https://checkout.stripe.com/")
        assert len(cal.created) == 0  # calendar only after payment
        # Slot is held
        paid_slots, _ = service.available_slots(future_slot.date(), now=now, kind="paid", include_calendar=False)
        assert future_slot not in paid_slots

        result = service.confirm_paid_from_checkout(
            pending.booking.stripe_checkout_session_id,
            pending.booking.id,
            now=now,
        )
        assert result.booking.status == "confirmed"
        assert result.calendar_synced is True
        assert len(cal.created) == 1
        assert "Payment verified" in result.message_en

    def test_unpaid_checkout_is_not_confirmed(self, test_db, future_slot):
        stripe = FakeStripe(paid=False)
        service = BookingService(test_db, stripe_client=stripe)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        pending = service.start_paid_checkout(
            name="Ada",
            email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            now=now,
            success_url="http://localhost/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost/cancel",
        )
        with pytest.raises(PaymentNotVerifiedError):
            service.confirm_paid_from_checkout(
                pending.booking.stripe_checkout_session_id,
                pending.booking.id,
                now=now,
            )
        saved = test_db.get_booking(pending.booking.id)
        assert saved.status == "pending"
        assert saved.calendar_synced is False

    def test_expired_hold_is_released(self, test_db, future_slot):
        stripe = FakeStripe(paid=False)
        service = BookingService(test_db, stripe_client=stripe)
        start_time = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        pending = service.start_paid_checkout(
            name="Ada",
            email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            now=start_time,
            success_url="http://localhost/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost/cancel",
        )
        later = start_time + timedelta(minutes=HOLD_MINUTES + 1)
        released = test_db.release_expired_holds(now=later)
        assert released == 1
        assert test_db.get_booking(pending.booking.id) is None
        slots, _ = service.available_slots(future_slot.date(), now=start_time, kind="paid", include_calendar=False)
        assert future_slot in slots

    def test_query_param_alone_does_not_confirm(self, test_db, future_slot):
        """Payment confirmation must come from a verified Checkout Session, not a return URL."""
        stripe = FakeStripe(paid=False)
        service = BookingService(test_db, stripe_client=stripe)
        now = datetime(future_slot.year, future_slot.month, future_slot.day, 8, 0, tzinfo=BANGKOK)
        pending = service.start_paid_checkout(
            name="Ada",
            email="ada@example.com",
            topic=None,
            slot_start=future_slot,
            now=now,
            success_url="http://localhost/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost/cancel",
        )
        with pytest.raises(PaymentNotVerifiedError):
            service.confirm_paid_from_checkout("cs_test_fake_1", pending.booking.id, now=now)
        assert test_db.get_booking(pending.booking.id).status == "pending"


class TestStripeKeySafety:
    def test_live_key_refused_without_flag(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_this_is_not_a_real_key_value")
        monkeypatch.delenv("AIHIVE_PAYMENTS_LIVE", raising=False)
        assert is_payments_enabled() is False
        with pytest.raises(LiveStripeKeyRefused):
            require_usable_stripe_key()

    def test_test_key_enables_payments(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_this_is_not_a_real_key_value")
        monkeypatch.delenv("AIHIVE_PAYMENTS_LIVE", raising=False)
        assert is_payments_enabled() is True
        assert require_usable_stripe_key().startswith("sk_test_")

    def test_secret_not_stored_on_config(self, monkeypatch):
        secret = "sk_test_unit_secret_should_not_leak"
        monkeypatch.setenv("STRIPE_SECRET_KEY", secret)
        assert secret not in repr(config)
        assert secret not in repr(config.__dict__)
        cleaned = redact_payment_secrets(f"using {secret} now")
        assert secret not in cleaned
        assert "sk_test_" not in cleaned
        assert "***" in cleaned

    def test_placeholder_price_is_labeled(self, monkeypatch):
        monkeypatch.delenv("AIHIVE_SESSION_PRICE_THB", raising=False)
        assert is_price_placeholder() is True
        assert get_session_price_thb() == DEFAULT_PLACEHOLDER_PRICE_THB
        assert "placeholder" in price_label_en().lower()
        assert "not yet decided" in price_label_en().lower()
