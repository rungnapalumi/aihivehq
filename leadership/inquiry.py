"""AIHive Leadership — corporate program inquiry: validation, storage, notification.

Design notes
------------
* Standard library only (sqlite3, re, datetime) so the preview service needs no extra
  dependencies.
* The destination address is configurable via ``LEADERSHIP_INQUIRY_TO`` and defaults to the
  intended business contact ``rungnapa@aihivehq.com``.
* Email delivery is NOT implemented or enabled in this phase. Submissions are stored in
  SQLite and every response says so via ``email_delivery: "not_enabled"``. Do not claim
  email delivery works until a sending path has been configured and tested.
* No IP addresses or user agents are stored. Logs never contain personal data.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import secrets
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_DESTINATION = "rungnapa@aihivehq.com"
DEFAULT_DB_PATH = "/tmp/aihive_leadership/inquiries.db"

PARTICIPANT_OPTIONS = ("1–10", "11–25", "26–50", "51–100", "100+")
DURATION_OPTIONS = ("Half day", "Full day", "Two days", "Multi-week program", "Not sure yet")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
PHONE_RE = re.compile(r"^[0-9+()\-.\s]{6,40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LIMITS = {
    "full_name": 120,
    "company": 160,
    "email": 200,
    "phone": 40,
    "objectives": 2000,
    "additional": 2000,
}


def get_settings() -> Dict[str, Any]:
    """Runtime settings (read on each call so tests can override env vars)."""
    return {
        "destination": os.environ.get("LEADERSHIP_INQUIRY_TO", "").strip() or DEFAULT_DESTINATION,
        "db_path": os.environ.get("LEADERSHIP_DB_PATH", "").strip() or DEFAULT_DB_PATH,
        # Reserved for a future, tested sending path. Nothing sends email in this phase.
        "email_enabled": False,
    }


def _text(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    # Strip control characters except newline/tab.
    value = "".join(ch for ch in value if ch in "\n\t" or ord(ch) >= 32)
    return value.strip()


def validate(payload: Any, today: Optional[_dt.date] = None) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Validate a raw inquiry payload. Returns (clean_data, errors)."""
    errors: Dict[str, str] = {}
    if not isinstance(payload, dict):
        return {}, {"_form": "Invalid request body."}
    today = today or _dt.datetime.now(_dt.timezone.utc).date()

    clean = {k: _text(payload, k) for k in (
        "full_name", "company", "email", "phone", "participants", "duration",
        "objectives", "preferred_date", "additional", "website",
    )}

    for key, limit in LIMITS.items():
        if len(clean[key]) > limit:
            errors[key] = f"Must be at most {limit} characters."

    if len(clean["full_name"]) < 2:
        errors["full_name"] = "Please enter your full name."
    if len(clean["company"]) < 2:
        errors["company"] = "Please enter your company or organization."
    if not EMAIL_RE.match(clean["email"]):
        errors["email"] = "Please enter a valid work email."
    if clean["phone"] and not PHONE_RE.match(clean["phone"]):
        errors["phone"] = "Please enter a valid phone number or leave it empty."
    if clean["participants"] not in PARTICIPANT_OPTIONS:
        errors["participants"] = "Please select an estimate."
    if clean["duration"] not in DURATION_OPTIONS:
        errors["duration"] = "Please select a duration."
    if len(clean["objectives"]) < 10:
        errors["objectives"] = "Please describe your objectives (at least 10 characters)."

    date_ok = False
    if DATE_RE.match(clean["preferred_date"]):
        try:
            d = _dt.date.fromisoformat(clean["preferred_date"])
            # One day of tolerance for visitors in time zones ahead of UTC.
            date_ok = d >= today - _dt.timedelta(days=1) and d <= today + _dt.timedelta(days=3 * 365)
        except ValueError:
            date_ok = False
    if not date_ok:
        errors["preferred_date"] = "Please choose a date that is not in the past."

    if payload.get("consent") is not True:
        errors["consent"] = "Consent is required so we can respond to your inquiry."

    clean["consent"] = payload.get("consent") is True
    return clean, errors


def is_spam(clean: Dict[str, Any]) -> bool:
    """Honeypot: real visitors never fill the hidden 'website' field."""
    return bool(clean.get("website"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS leadership_inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    full_name TEXT NOT NULL,
    company TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    participants TEXT NOT NULL,
    duration TEXT NOT NULL,
    objectives TEXT NOT NULL,
    preferred_date TEXT NOT NULL,
    additional TEXT,
    consent_given_at TEXT NOT NULL,
    destination TEXT NOT NULL,
    email_status TEXT NOT NULL
);
"""


class InquiryStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def save(self, clean: Dict[str, Any], destination: str, email_status: str) -> str:
        reference = "LDR-" + secrets.token_hex(4).upper()
        now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO leadership_inquiries (reference, created_at, full_name, company, email, phone,"
                " participants, duration, objectives, preferred_date, additional, consent_given_at,"
                " destination, email_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (reference, now, clean["full_name"], clean["company"], clean["email"], clean["phone"],
                 clean["participants"], clean["duration"], clean["objectives"], clean["preferred_date"],
                 clean["additional"], now, destination, email_status),
            )
        return reference

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM leadership_inquiries").fetchone()[0]

    def get(self, reference: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM leadership_inquiries WHERE reference = ?", (reference,)).fetchone()
            return dict(row) if row else None


def notify(clean: Dict[str, Any], destination: str, settings: Dict[str, Any]) -> str:
    """Email notification hook. Not enabled in this phase: always returns 'not_enabled'."""
    return "not_enabled"


def handle_submission(payload: Any, store: InquiryStore, settings: Optional[Dict[str, Any]] = None,
                      today: Optional[_dt.date] = None) -> Tuple[int, Dict[str, Any]]:
    """Validate, store and (eventually) notify. Returns (http_status, json_body)."""
    settings = settings or get_settings()
    clean, errors = validate(payload, today=today)
    if errors:
        return 400, {"ok": False, "errors": errors}
    if is_spam(clean):
        # Look successful to bots, but store nothing.
        return 201, {"ok": True, "reference": "LDR-" + secrets.token_hex(4).upper(), "email_delivery": "not_enabled"}
    status = notify(clean, settings["destination"], settings)
    reference = store.save(clean, settings["destination"], status)
    return 201, {"ok": True, "reference": reference, "email_delivery": status}
