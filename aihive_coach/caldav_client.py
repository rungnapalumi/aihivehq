"""CalDAV helper for AIHive Coach session bookings.

Talks to Namecheap Private Email (official host: dav.privateemail.com).
Never logs, prints, or includes the calendar password in exceptions.
Callers only receive busy time ranges or a created event UID — never
other customers' names, emails, topics, or event summaries.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

BANGKOK = ZoneInfo("Asia/Bangkok")
DEFAULT_CALDAV_URL = "https://dav.privateemail.com/"
DEFAULT_CALDAV_USER = "rungnapa@aihivehq.com"

logger = logging.getLogger(__name__)

# Do not attach a handler that might echo secrets; just keep records filterable.
_PASSWORD_ENV_KEYS = ("AIHIVE_CALDAV_PASSWORD", "PRIVATEEMAIL_PASSWORD")


class CalendarSyncError(Exception):
    """Safe, password-free error when calendar access fails."""


def get_caldav_url() -> Optional[str]:
    url = (os.getenv("AIHIVE_CALDAV_URL") or DEFAULT_CALDAV_URL).strip()
    return url or None


def get_caldav_user() -> str:
    return (os.getenv("AIHIVE_CALDAV_USER") or DEFAULT_CALDAV_USER).strip() or DEFAULT_CALDAV_USER


def get_caldav_password() -> Optional[str]:
    """Read the password from the environment. Never cache it on a config object."""
    value = os.getenv("AIHIVE_CALDAV_PASSWORD")
    if value is None:
        return None
    value = value.strip()
    return value or None


def is_caldav_configured() -> bool:
    return bool(get_caldav_url() and get_caldav_password())


def redact_secrets(text: str) -> str:
    """Strip credentials from a string so it is safe to log or raise."""
    if text is None:
        return ""
    out = str(text)
    for key in _PASSWORD_ENV_KEYS:
        secret = os.getenv(key)
        if secret:
            out = out.replace(secret, "***")
            out = out.replace(secret.strip(), "***")
    out = re.sub(r"(://[^:/?#\s]+):([^@/?#\s]*)@", r"\1:***@", out)
    return out


def _safe_error_message(exc: BaseException, fallback: str) -> str:
    # Never chain the original exception: libraries may embed the URL with credentials.
    detail = redact_secrets(f"{type(exc).__name__}")
    return f"{fallback} ({detail})"


def _ics_escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def build_vevent(
    *,
    booking_id: str,
    slot_start: datetime,
    slot_end: datetime,
    customer_name: str,
    customer_email: str,
    topic: Optional[str] = None,
    summary: str = "AIHive Coach session",
) -> str:
    """Build a VEVENT. Customer email goes in DESCRIPTION only (no ATTENDEE, to avoid invites)."""
    start = slot_start.astimezone(BANGKOK)
    end = slot_end.astimezone(BANGKOK)
    now_utc = datetime.now(timezone.utc)
    lines = [
        f"Customer: {_ics_escape(customer_name)}",
        f"Email: {_ics_escape(customer_email)}",
    ]
    if topic and topic.strip():
        lines.append(f"Topic: {_ics_escape(topic.strip())}")
    description = "\\n".join(lines)
    uid = f"aihive-coach-{booking_id}@aihivehq.com"
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//AIHiveHQ//AIHive Coach//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now_utc.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTSTART;TZID=Asia/Bangkok:{start.strftime('%Y%m%dT%H%M%S')}\r\n"
        f"DTEND;TZID=Asia/Bangkok:{end.strftime('%Y%m%dT%H%M%S')}\r\n"
        f"SUMMARY:{_ics_escape(summary)}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def _as_aware(dt: datetime, default_tz=BANGKOK) -> datetime:
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day, tzinfo=default_tz)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=default_tz)
    return dt


def _intervals_from_freebusy_payload(payload: str) -> List[Tuple[datetime, datetime]]:
    """Parse FREEBUSY lines. Ignores summaries and attendees if present."""
    intervals: List[Tuple[datetime, datetime]] = []
    if not payload:
        return intervals
    for raw_line in payload.replace("\r\n", "\n").replace("\n ", "").splitlines():
        line = raw_line.strip()
        if not line.upper().startswith("FREEBUSY"):
            continue
        if ":" not in line:
            continue
        _, value = line.split(":", 1)
        for part in value.split(","):
            part = part.strip()
            if "/" not in part:
                continue
            a, b = part.split("/", 1)
            try:
                start = _parse_ics_datetime(a)
                if b.startswith("P") or b.startswith("p"):
                    # Duration form, uncommon; skip rather than guess wrong
                    continue
                end = _parse_ics_datetime(b)
            except ValueError:
                continue
            intervals.append((start, end))
    return intervals


def _parse_ics_datetime(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if "T" in value:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=BANGKOK)
    d = datetime.strptime(value, "%Y%m%d").date()
    return datetime(d.year, d.month, d.day, tzinfo=BANGKOK)


class CalDavCalendar:
    """Thin wrapper around the caldav library, with secret-safe errors."""

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_factory: Optional[Callable] = None,
    ):
        self._url = url if url is not None else get_caldav_url()
        self._username = username if username is not None else get_caldav_user()
        self._password = password if password is not None else get_caldav_password()
        self._client_factory = client_factory

    def _connect_calendar(self):
        if not self._url or not self._password:
            raise CalendarSyncError("Calendar is not configured")
        try:
            if self._client_factory is not None:
                client = self._client_factory(
                    url=self._url, username=self._username, password=self._password
                )
            else:
                import caldav

                client = caldav.DAVClient(
                    url=self._url, username=self._username, password=self._password
                )
            if hasattr(client, "principal"):
                principal = client.principal()
                calendars = list(principal.calendars() or [])
            elif hasattr(client, "calendars"):
                calendars = list(client.calendars() or [])
            else:
                raise CalendarSyncError("Could not list calendars")
        except CalendarSyncError:
            raise
        except Exception as exc:
            raise CalendarSyncError(
                _safe_error_message(exc, "Could not connect to the calendar")
            ) from None

        if not calendars:
            raise CalendarSyncError("No calendar collection was found on the account")

        preferred = None
        for cal in calendars:
            name = (getattr(cal, "name", None) or "").lower()
            if "personal" in name or name in {"calendar", "cal"}:
                preferred = cal
                break
        return preferred or calendars[0]

    def busy_intervals(self, start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
        """Return busy (start, end) ranges only — no event details."""
        start = _as_aware(start)
        end = _as_aware(end)
        calendar = self._connect_calendar()
        try:
            if hasattr(calendar, "freebusy_request"):
                fb = calendar.freebusy_request(start, end)
                payload = (
                    getattr(fb, "data", None)
                    or getattr(fb, "raw_data", None)
                    or getattr(fb, "wire_data", None)
                    or ""
                )
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="replace")
                intervals = _intervals_from_freebusy_payload(payload or "")
                if intervals or payload:
                    return intervals
        except CalendarSyncError:
            raise
        except Exception as exc:
            logger.info("freebusy_request failed; falling back to date search (%s)", type(exc).__name__)

        try:
            events = []
            if hasattr(calendar, "search"):
                try:
                    events = calendar.search(start=start, end=end, event=True, expand=True)
                except TypeError:
                    events = calendar.search(start=start, end=end)
            elif hasattr(calendar, "date_search"):
                events = calendar.date_search(start, end, expand=True)
            return _intervals_from_events(events or [])
        except Exception as exc:
            raise CalendarSyncError(
                _safe_error_message(exc, "Could not read calendar availability")
            ) from None

    def create_session_event(
        self,
        *,
        booking_id: str,
        slot_start: datetime,
        slot_end: datetime,
        customer_name: str,
        customer_email: str,
        topic: Optional[str] = None,
        summary: str = "AIHive Coach session",
    ) -> str:
        calendar = self._connect_calendar()
        ical = build_vevent(
            booking_id=booking_id,
            slot_start=slot_start,
            slot_end=slot_end,
            customer_name=customer_name,
            customer_email=customer_email,
            topic=topic,
            summary=summary,
        )
        try:
            event = None
            if hasattr(calendar, "add_event"):
                try:
                    event = calendar.add_event(ical)
                except TypeError:
                    event = calendar.add_event(ics=ical)
            elif hasattr(calendar, "save_event"):
                event = calendar.save_event(ical)
            else:
                raise CalendarSyncError("Calendar client cannot create events")
        except CalendarSyncError:
            raise
        except Exception as exc:
            raise CalendarSyncError(
                _safe_error_message(exc, "Could not add the booking to the calendar")
            ) from None

        uid = f"aihive-coach-{booking_id}@aihivehq.com"
        if event is not None:
            uid = getattr(event, "id", None) or getattr(event, "url", None) or uid
            uid = str(uid)
        return uid


def _intervals_from_events(events: Iterable) -> List[Tuple[datetime, datetime]]:
    intervals: List[Tuple[datetime, datetime]] = []
    for ev in events:
        start = end = None
        try:
            if hasattr(ev, "get_icalendar_component"):
                comp = ev.get_icalendar_component()
                dtstart = comp.get("dtstart") if comp is not None else None
                dtend = comp.get("dtend") if comp is not None else None
                duration = comp.get("duration") if comp is not None else None
                if dtstart is not None:
                    start = dtstart.dt
                if dtend is not None:
                    end = dtend.dt
                elif start is not None and duration is not None:
                    end = start + duration.dt
            if start is None and hasattr(ev, "get_dtend"):
                # Some versions only expose end; skip if start cannot be read.
                pass
        except Exception:
            continue
        if start is None:
            continue
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime(start.year, start.month, start.day, tzinfo=BANGKOK)
            if end is None or (isinstance(end, date) and not isinstance(end, datetime)):
                end = start + timedelta(days=1)
        start = _as_aware(start)
        if end is None:
            end = start + timedelta(minutes=30)
        elif isinstance(end, date) and not isinstance(end, datetime):
            end = datetime(end.year, end.month, end.day, tzinfo=BANGKOK)
        else:
            end = _as_aware(end)
        intervals.append((start, end))
    return intervals


def slot_overlaps_busy(slot_start: datetime, slot_end: datetime, busy: List[Tuple[datetime, datetime]]) -> bool:
    start = _as_aware(slot_start)
    end = _as_aware(slot_end)
    for busy_start, busy_end in busy:
        bs = _as_aware(busy_start)
        be = _as_aware(busy_end)
        if start < be and end > bs:
            return True
    return False
