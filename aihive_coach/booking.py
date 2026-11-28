"""Coach and Tutor session booking: trial (15 min) and paid (30 min) slots.

Both services share one calendar and one slot pool in the 19:00–21:00
Asia/Bangkok window. A time booked as Coach is busy for Tutor and vice versa.
A free 15-minute trial is allowed once per email per service.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from caldav_client import (
    CalDavCalendar,
    CalendarSyncError,
    is_caldav_configured,
    slot_overlaps_busy,
)
from models import CoachBooking, SlotUnavailableError
from payments import (
    HOLD_MINUTES,
    PaymentNotVerifiedError,
    PaymentsNotEnabledError,
    StripeCheckoutClient,
    get_public_return_url,
    get_session_price_thb,
    is_payments_enabled,
    is_price_placeholder,
    payment_is_verified,
)

BANGKOK = ZoneInfo("Asia/Bangkok")
PAID_SLOT_TIMES = ((19, 0), (19, 30), (20, 0), (20, 30))
TRIAL_SLOT_TIMES = (
    (19, 0),
    (19, 15),
    (19, 30),
    (19, 45),
    (20, 0),
    (20, 15),
    (20, 30),
    (20, 45),
)
# Back-compat alias used by earlier tests for paid 30-minute slots.
SLOT_TIMES = PAID_SLOT_TIMES
PAID_DURATION = timedelta(minutes=30)
TRIAL_DURATION = timedelta(minutes=15)
SLOT_DURATION = PAID_DURATION
BOOKING_HORIZON_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
WINDOW_START_HOUR, WINDOW_START_MINUTE = 19, 0
WINDOW_END_HOUR, WINDOW_END_MINUTE = 21, 0
SERVICE_TYPES = ("coach", "tutor")
SERVICE_LABELS = {"coach": "Coach", "tutor": "Tutor"}
SERVICE_LABELS_TH = {"coach": "โค้ช", "tutor": "ติวเตอร์"}


class TrialAlreadyUsedError(Exception):
    """This email has already used the free 15-minute trial."""


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_service_type(service_type: str) -> str:
    value = (service_type or "coach").strip().lower()
    if value not in SERVICE_TYPES:
        raise ValueError("Unknown booking service / ไม่พบบริการที่เลือก")
    return value


def service_label(service_type: str, lang: str = "en") -> str:
    key = normalize_service_type(service_type)
    if lang == "th":
        return SERVICE_LABELS_TH[key]
    return SERVICE_LABELS[key]


def trial_already_used_message(service_type: str = "coach") -> str:
    en = service_label(service_type, "en")
    th = service_label(service_type, "th")
    return (
        f"This email has already used the free 15-minute {en} trial. "
        "Please book a paid 30-minute session. "
        f"/ อีเมลนี้ใช้สิทธิ์ทดลอง 15 นาทีของ{th}ไปแล้ว กรุณาจองนัด 30 นาทีแบบชำระเงิน"
    )


def slot_key(slot_start: datetime) -> str:
    start = slot_start.astimezone(BANGKOK)
    return start.strftime("%Y-%m-%dT%H:%M+07:00")


def duration_for(kind: str) -> timedelta:
    return TRIAL_DURATION if kind == "trial" else PAID_DURATION


def slot_times_for(kind: str):
    return TRIAL_SLOT_TIMES if kind == "trial" else PAID_SLOT_TIMES


def is_canonical_slot(slot_start: datetime, kind: str = "paid") -> bool:
    start = slot_start.astimezone(BANGKOK)
    times = slot_times_for(kind)
    return (
        (start.hour, start.minute) in times
        and start.second == 0
        and start.microsecond == 0
    )


def generate_slots_for_date(
    day: date, now: Optional[datetime] = None, kind: str = "paid"
) -> List[datetime]:
    """Return bookable starts on ``day`` in Asia/Bangkok, hiding past slots."""
    now = now or datetime.now(BANGKOK)
    if now.tzinfo is None:
        now = now.replace(tzinfo=BANGKOK)
    else:
        now = now.astimezone(BANGKOK)
    slots: List[datetime] = []
    for hour, minute in slot_times_for(kind):
        start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=BANGKOK)
        end = start + duration_for(kind)
        window_end = datetime(day.year, day.month, day.day, WINDOW_END_HOUR, WINDOW_END_MINUTE, tzinfo=BANGKOK)
        if end > window_end:
            continue
        if start > now:
            slots.append(start)
    return slots


def booking_date_allowed(day: date, today: Optional[date] = None) -> bool:
    today = today or datetime.now(BANGKOK).date()
    return today <= day <= today + timedelta(days=BOOKING_HORIZON_DAYS)


def validate_booking_form(name: str, email: str, topic: Optional[str] = None) -> List[str]:
    errors: List[str] = []
    if not (name or "").strip():
        errors.append("Please enter your name / กรุณากรอกชื่อ")
    elif len(name.strip()) > 200:
        errors.append("Name is too long / ชื่อยาวเกินไป")
    if not (email or "").strip():
        errors.append("Please enter your email / กรุณากรอกอีเมล")
    elif not EMAIL_RE.match(email.strip()):
        errors.append("Please enter a valid email / กรุณากรอกอีเมลให้ถูกต้อง")
    elif len(email.strip()) > 254:
        errors.append("Email is too long / อีเมลยาวเกินไป")
    if topic and len(topic) > 500:
        errors.append("Topic is too long / หัวข้อยาวเกินไป")
    return errors


def _event_summary(kind: str, service_type: str = "coach") -> str:
    label = service_label(service_type, "en")
    if kind == "trial":
        return f"AIHive {label} trial (15 min)"
    return f"AIHive {label} session (30 min)"


@dataclass
class BookingResult:
    booking: CoachBooking
    calendar_synced: bool
    calendar_sync_pending: bool
    message_en: str
    message_th: str
    checkout_url: Optional[str] = None
    kind: str = "trial"
    payment_pending: bool = False


class BookingService:
    def __init__(self, db, calendar_client=None, calendar_factory=None, stripe_client=None):
        self.db = db
        self._calendar_client = calendar_client
        self._calendar_factory = calendar_factory
        self._stripe_client = stripe_client

    def _calendar(self):
        if self._calendar_client is not None:
            return self._calendar_client
        if not is_caldav_configured():
            return None
        if self._calendar_factory is not None:
            return self._calendar_factory()
        return CalDavCalendar()

    def _stripe(self):
        if self._stripe_client is not None:
            return self._stripe_client
        return StripeCheckoutClient()

    def occupied_intervals(self, day: date, now: Optional[datetime] = None):
        """Active (confirmed or unexpired hold) intervals only — no customer details."""
        self.db.release_expired_holds(now=now)
        day_start = datetime(day.year, day.month, day.day, tzinfo=BANGKOK)
        day_end = day_start + timedelta(days=1)
        return self.db.list_occupied_intervals(day_start, day_end, now=now)

    def booked_starts(self, day: date) -> List[datetime]:
        """Public availability: start times only, never customer details."""
        return [start for start, _end in self.occupied_intervals(day)]

    def available_slots(
        self,
        day: date,
        now: Optional[datetime] = None,
        include_calendar: bool = True,
        kind: str = "paid",
    ) -> tuple[List[datetime], Optional[str]]:
        """Return free slots of ``kind`` and an optional calendar-check warning."""
        now = now or datetime.now(BANGKOK)
        if now.tzinfo is None:
            now = now.replace(tzinfo=BANGKOK)
        else:
            now = now.astimezone(BANGKOK)
        if not booking_date_allowed(day, today=now.date()):
            return [], None
        slots = generate_slots_for_date(day, now=now, kind=kind)
        occupied = self.occupied_intervals(day, now=now)
        duration = duration_for(kind)
        slots = [s for s in slots if not slot_overlaps_busy(s, s + duration, occupied)]
        warning = None
        if include_calendar:
            calendar = self._calendar()
            if calendar is not None and slots:
                range_start = datetime(day.year, day.month, day.day, 19, 0, tzinfo=BANGKOK)
                range_end = datetime(day.year, day.month, day.day, 21, 0, tzinfo=BANGKOK)
                try:
                    busy = calendar.busy_intervals(range_start, range_end)
                    slots = [
                        s for s in slots if not slot_overlaps_busy(s, s + duration, busy)
                    ]
                except CalendarSyncError:
                    warning = (
                        "Could not check the live calendar just now. "
                        "Times already booked here are hidden. "
                        "/ ตอนนี้ยังตรวจปฏิทินสดไม่ได้ ช่วงที่ถูกจองในระบบแล้วจะไม่แสดง"
                    )
        return slots, warning

    def _validate_slot(self, slot_start: datetime, kind: str, now: datetime) -> datetime:
        start = slot_start.astimezone(BANGKOK)
        if not is_canonical_slot(start, kind=kind):
            raise ValueError("That time is not a bookable slot / เวลานี้ไม่อยู่ในช่วงที่จองได้")
        if not booking_date_allowed(start.date(), today=now.date()):
            raise ValueError("That date is outside the booking window / วันที่นี้อยู่นอกช่วงที่เปิดจอง")
        if start <= now:
            raise SlotUnavailableError("That time has already passed / ช่วงเวลานี้ผ่านไปแล้ว")
        end = start + duration_for(kind)
        window_end = datetime(start.year, start.month, start.day, 21, 0, tzinfo=BANGKOK)
        if end > window_end:
            raise ValueError("That time is outside 19:00–21:00 / เวลานี้อยู่นอกช่วง 19:00–21:00")
        occupied = self.occupied_intervals(start.date(), now=now)
        if slot_overlaps_busy(start, end, occupied):
            raise SlotUnavailableError("That time is no longer available / ช่วงเวลานี้ถูกจองแล้ว")
        return start

    def _calendar_conflicts(self, start: datetime, end: datetime) -> tuple[bool, bool]:
        """Return (conflict, check_failed)."""
        calendar = self._calendar()
        if calendar is None:
            return False, False
        try:
            busy = calendar.busy_intervals(start, end)
            if slot_overlaps_busy(start, end, busy):
                return True, False
            return False, False
        except CalendarSyncError:
            return False, True

    def _sync_to_calendar(self, booking: CoachBooking, check_failed: bool) -> tuple[bool, bool]:
        calendar = self._calendar()
        if calendar is None or check_failed:
            return False, True
        try:
            uid = calendar.create_session_event(
                booking_id=booking.id,
                slot_start=booking.slot_start,
                slot_end=booking.slot_end,
                customer_name=booking.customer_name,
                customer_email=booking.customer_email,
                topic=booking.topic,
                summary=_event_summary(booking.session_kind, booking.service_type),
            )
            self.db.update_booking_calendar_sync(booking.id, calendar_uid=str(uid), synced=True)
            booking.calendar_uid = str(uid)
            booking.calendar_synced = True
            return True, False
        except CalendarSyncError:
            self.db.update_booking_calendar_sync(booking.id, calendar_uid=None, synced=False)
            return False, True
        except TypeError:
            # Older client_factory mocks may not accept summary=
            try:
                uid = calendar.create_session_event(
                    booking_id=booking.id,
                    slot_start=booking.slot_start,
                    slot_end=booking.slot_end,
                    customer_name=booking.customer_name,
                    customer_email=booking.customer_email,
                    topic=booking.topic,
                )
                self.db.update_booking_calendar_sync(booking.id, calendar_uid=str(uid), synced=True)
                booking.calendar_uid = str(uid)
                booking.calendar_synced = True
                return True, False
            except CalendarSyncError:
                self.db.update_booking_calendar_sync(booking.id, calendar_uid=None, synced=False)
                return False, True

    def book_trial(
        self,
        *,
        name: str,
        email: str,
        topic: Optional[str],
        slot_start: datetime,
        now: Optional[datetime] = None,
        service_type: str = "coach",
    ) -> BookingResult:
        errors = validate_booking_form(name, email, topic)
        if errors:
            raise ValueError(errors[0])
        service_type = normalize_service_type(service_type)
        now = now or datetime.now(BANGKOK)
        if now.tzinfo is None:
            now = now.replace(tzinfo=BANGKOK)
        else:
            now = now.astimezone(BANGKOK)
        if self.db.email_has_used_trial(email, service_type):
            raise TrialAlreadyUsedError(trial_already_used_message(service_type))
        start = self._validate_slot(slot_start, "trial", now)
        end = start + TRIAL_DURATION
        conflict, check_failed = self._calendar_conflicts(start, end)
        if conflict:
            raise SlotUnavailableError("That time is no longer available / ช่วงเวลานี้ถูกจองแล้ว")

        booking = self.db.create_booking(
            customer_name=name.strip(),
            customer_email=email.strip(),
            topic=(topic.strip() if topic and topic.strip() else None),
            slot_start=start,
            slot_end=end,
            session_kind="trial",
            status="confirmed",
            service_type=service_type,
        )
        synced, pending = self._sync_to_calendar(booking, check_failed)
        role_en = service_label(service_type, "en").lower()
        role_th = service_label(service_type, "th")
        if synced:
            message_en = (
                f"Your free 15-minute trial is booked and was added to the {role_en}'s calendar. "
                f"Your details are visible only to the {role_en}."
            )
            message_th = (
                f"จองทดลองใช้ 15 นาทีเรียบร้อยแล้ว และได้บันทึกลงปฏิทินของ{role_th}แล้ว "
                f"ข้อมูลของคุณมีเพียง{role_th}ที่เห็น"
            )
        else:
            message_en = (
                "Your free 15-minute trial is booked and saved. Calendar sync is pending — "
                f"it has not been added to the {role_en}'s calendar yet."
            )
            message_th = (
                "จองทดลองใช้ 15 นาทีและบันทึกไว้แล้ว การซิงค์ปฏิทินยังค้างอยู่ "
                f"ยังไม่ได้เพิ่มนัดนี้ลงปฏิทินของ{role_th}"
            )
        return BookingResult(
            booking=booking,
            calendar_synced=synced,
            calendar_sync_pending=pending,
            message_en=message_en,
            message_th=message_th,
            kind="trial",
        )

    def start_paid_checkout(
        self,
        *,
        name: str,
        email: str,
        topic: Optional[str],
        slot_start: datetime,
        now: Optional[datetime] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        service_type: str = "coach",
    ) -> BookingResult:
        """Hold the slot and create a Stripe Checkout Session. Do not confirm yet."""
        errors = validate_booking_form(name, email, topic)
        if errors:
            raise ValueError(errors[0])
        if not is_payments_enabled() and self._stripe_client is None:
            # Injected test clients can run even if env has no key.
            # Production path: no key means we never pretend payment happened.
            try:
                from payments import require_usable_stripe_key

                require_usable_stripe_key()
            except Exception:
                raise PaymentsNotEnabledError(
                    "Payments are not yet enabled / ยังไม่เปิดรับชำระเงิน"
                )
        now = now or datetime.now(BANGKOK)
        if now.tzinfo is None:
            now = now.replace(tzinfo=BANGKOK)
        else:
            now = now.astimezone(BANGKOK)
        service_type = normalize_service_type(service_type)
        start = self._validate_slot(slot_start, "paid", now)
        end = start + PAID_DURATION
        conflict, check_failed = self._calendar_conflicts(start, end)
        if conflict:
            raise SlotUnavailableError("That time is no longer available / ช่วงเวลานี้ถูกจองแล้ว")

        hold_expires = now + timedelta(minutes=HOLD_MINUTES)
        booking = self.db.create_booking(
            customer_name=name.strip(),
            customer_email=email.strip(),
            topic=(topic.strip() if topic and topic.strip() else None),
            slot_start=start,
            slot_end=end,
            session_kind="paid",
            status="pending",
            hold_expires_at=hold_expires,
            service_type=service_type,
        )

        public = get_public_return_url()
        if not success_url or not cancel_url:
            if not public:
                self.db.release_hold(booking.id)
                raise PaymentsNotEnabledError(
                    "Payments are not yet enabled (return URL is not configured) / ยังไม่เปิดรับชำระเงิน"
                )
            success_url = (
                f"{public}/?booking_checkout=success"
                f"&session_id={{CHECKOUT_SESSION_ID}}&booking_id={booking.id}"
            )
            cancel_url = f"{public}/?booking_checkout=cancel&booking_id={booking.id}"

        try:
            session = self._stripe().create_session(
                booking_id=booking.id,
                customer_email=booking.customer_email,
                customer_name=booking.customer_name,
                success_url=success_url,
                cancel_url=cancel_url,
                price_thb=get_session_price_thb(),
                placeholder=is_price_placeholder(),
                service_type=service_type,
            )
        except Exception:
            self.db.release_hold(booking.id)
            raise

        if not session.url:
            self.db.release_hold(booking.id)
            raise PaymentsNotEnabledError("Payments are not yet enabled / ยังไม่เปิดรับชำระเงิน")

        self.db.update_booking_checkout(booking.id, stripe_checkout_session_id=session.id)
        booking.stripe_checkout_session_id = session.id
        booking.status = "pending"

        return BookingResult(
            booking=booking,
            calendar_synced=False,
            calendar_sync_pending=True,
            checkout_url=session.url,
            kind="paid",
            payment_pending=True,
            message_en=(
                f"This time is held for {HOLD_MINUTES} minutes while you pay. "
                "The session is not booked until payment is verified. "
                f"Amount: {get_session_price_thb():,} THB"
                + (" (placeholder — price not yet decided)." if is_price_placeholder() else ".")
            ),
            message_th=(
                f"เราจะกันช่วงเวลานี้ไว้ {HOLD_MINUTES} นาทีระหว่างที่คุณชำระเงิน "
                "จะยืนยันนัดเมื่อตรวจสอบการชำระเงินแล้วเท่านั้น "
                f"จำนวนเงิน THB {get_session_price_thb():,}"
                + (" (ราคาตัวอย่าง ยังไม่ได้กำหนดจริง)" if is_price_placeholder() else "")
            ),
        )

    def confirm_paid_from_checkout(
        self,
        session_id: str,
        booking_id: str,
        now: Optional[datetime] = None,
    ) -> BookingResult:
        """Confirm a paid booking only after Stripe Checkout is verified server-side."""
        now = now or datetime.now(BANGKOK)
        if now.tzinfo is None:
            now = now.replace(tzinfo=BANGKOK)
        else:
            now = now.astimezone(BANGKOK)
        self.db.release_expired_holds(now=now)
        booking = self.db.get_booking(booking_id)
        if booking is None:
            raise PaymentNotVerifiedError("We could not find that booking / ไม่พบการจองนี้")
        if booking.session_kind != "paid":
            raise PaymentNotVerifiedError("That booking is not a paid session")
        if booking.status == "confirmed":
            return BookingResult(
                booking=booking,
                calendar_synced=bool(booking.calendar_synced),
                calendar_sync_pending=not bool(booking.calendar_synced),
                kind="paid",
                message_en="This session is already confirmed.",
                message_th="นัดนี้ได้รับการยืนยันแล้ว",
            )
        if booking.status != "pending":
            raise PaymentNotVerifiedError(
                "This payment could not be matched to an open reservation / ไม่พบการจองที่รอชำระเงิน"
            )

        info = self._stripe().retrieve_session(session_id)
        stored_cs = booking.stripe_checkout_session_id
        if stored_cs and stored_cs != info.id:
            raise PaymentNotVerifiedError("Checkout Session does not match this booking")
        if not payment_is_verified(info, booking_id, get_session_price_thb()):
            raise PaymentNotVerifiedError(
                "Payment has not been verified yet / ยังตรวจสอบการชำระเงินไม่สำเร็จ"
            )

        # If the hold expired but the slot is still free, confirm. If taken, do not double-book.
        occupied = [
            interval
            for interval in self.db.list_occupied_intervals(
                booking.slot_start, booking.slot_end, now=now
            )
            if True
        ]
        # list_occupied includes this pending row; exclude self
        others = []
        # Use raw overlaps excluding this id
        others = self.db.list_occupied_intervals(
            booking.slot_start, booking.slot_end, now=now, exclude_booking_id=booking.id
        )
        if slot_overlaps_busy(booking.slot_start, booking.slot_end, others):
            raise SlotUnavailableError(
                "Payment was received but this time is no longer available. "
                "The coach will follow up. We have not created a second booking. "
                "/ ได้รับการชำระเงินแล้ว แต่ช่วงเวลานี้ไม่ว่างแล้ว โค้ชจะติดต่อกลับ "
                "ระบบจะไม่จองซ้ำ"
            )

        booking = self.db.confirm_paid_booking(
            booking.id,
            stripe_checkout_session_id=info.id,
            stripe_payment_intent_id=info.payment_intent,
        )
        conflict, check_failed = self._calendar_conflicts(booking.slot_start, booking.slot_end)
        if conflict:
            # Already confirmed locally; calendar may reject but we stay honest.
            check_failed = True
        synced, pending = self._sync_to_calendar(booking, check_failed or conflict)
        if synced:
            message_en = (
                "Payment verified. Your 30-minute session is booked and was added to the coach's calendar. "
                "Your details are visible only to the coach."
            )
            message_th = (
                "ตรวจสอบการชำระเงินแล้ว จองนัด 30 นาทีเรียบร้อย และได้บันทึกลงปฏิทินของโค้ชแล้ว "
                "ข้อมูลของคุณมีเพียงโค้ชที่เห็น"
            )
        else:
            message_en = (
                "Payment verified. Your 30-minute session is booked and saved. "
                "Calendar sync is pending — it has not been added to the coach's calendar yet."
            )
            message_th = (
                "ตรวจสอบการชำระเงินแล้ว จองนัด 30 นาทีและบันทึกไว้แล้ว "
                "การซิงค์ปฏิทินยังค้างอยู่ ยังไม่ได้เพิ่มนัดนี้ลงปฏิทินของโค้ช"
            )
        return BookingResult(
            booking=booking,
            calendar_synced=synced,
            calendar_sync_pending=pending,
            message_en=message_en,
            message_th=message_th,
            kind="paid",
        )

    def cancel_pending_hold(self, booking_id: Optional[str]) -> None:
        if not booking_id:
            return
        self.db.release_hold(booking_id)
