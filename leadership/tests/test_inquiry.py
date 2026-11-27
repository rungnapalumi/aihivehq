"""Tests for corporate inquiry validation and storage (leadership/inquiry.py)."""
import datetime as dt

import pytest

from leadership import inquiry

TODAY = dt.date(2026, 11, 27)


def valid(**over):
    data = {
        "full_name": "Somchai Test", "company": "Example Co", "email": "somchai@example.com", "phone": "+66 81 234 5678",
        "participants": "11–25", "duration": "Full day", "objectives": "Build strategic thinking in new managers.",
        "preferred_date": "2027-01-15", "additional": "", "website": "", "consent": True,
    }
    data.update(over)
    return data


def test_valid_payload_passes():
    clean, errors = inquiry.validate(valid(), today=TODAY)
    assert errors == {}
    assert clean["company"] == "Example Co" and clean["consent"] is True


@pytest.mark.parametrize("field,value", [
    ("full_name", ""), ("company", "x"), ("email", "not-an-email"), ("email", "a@b"), ("phone", "abc"),
    ("participants", "1000000"), ("duration", "Forever"), ("objectives", "short"),
    ("preferred_date", "2020-01-01"), ("preferred_date", "15/01/2027"), ("preferred_date", "2027-02-30"),
])
def test_invalid_fields_are_reported(field, value):
    _, errors = inquiry.validate(valid(**{field: value}), today=TODAY)
    assert field in errors


def test_consent_must_be_true_boolean():
    for v in (False, "true", 1, None):
        _, errors = inquiry.validate(valid(consent=v), today=TODAY)
        assert "consent" in errors


def test_phone_is_optional():
    _, errors = inquiry.validate(valid(phone=""), today=TODAY)
    assert errors == {}


def test_length_limits_and_control_characters():
    _, errors = inquiry.validate(valid(objectives="x" * 2001), today=TODAY)
    assert "objectives" in errors
    clean, errors = inquiry.validate(valid(full_name="Ann\x00\x07 Lee"), today=TODAY)
    assert errors == {} and clean["full_name"] == "Ann Lee"


def test_non_dict_payload_rejected():
    _, errors = inquiry.validate(["a"], today=TODAY)
    assert errors


def test_default_destination_and_env_override(monkeypatch):
    monkeypatch.delenv("LEADERSHIP_INQUIRY_TO", raising=False)
    assert inquiry.get_settings()["destination"] == "rungnapa@aihivehq.com"
    monkeypatch.setenv("LEADERSHIP_INQUIRY_TO", "programs@example.com")
    assert inquiry.get_settings()["destination"] == "programs@example.com"
    assert inquiry.get_settings()["email_enabled"] is False


def test_submission_is_stored_and_email_not_claimed(tmp_path):
    store = inquiry.InquiryStore(str(tmp_path / "inq.db"))
    status, body = inquiry.handle_submission(valid(), store, settings={"destination": "rungnapa@aihivehq.com", "db_path": "", "email_enabled": False}, today=TODAY)
    assert status == 201 and body["ok"] is True
    assert body["email_delivery"] == "not_enabled"
    row = store.get(body["reference"])
    assert row["email"] == "somchai@example.com" and row["destination"] == "rungnapa@aihivehq.com"
    assert row["email_status"] == "not_enabled" and row["consent_given_at"]
    assert store.count() == 1


def test_invalid_submission_not_stored(tmp_path):
    store = inquiry.InquiryStore(str(tmp_path / "inq.db"))
    status, body = inquiry.handle_submission(valid(email="bad"), store, today=TODAY)
    assert status == 400 and "email" in body["errors"]
    assert store.count() == 0


def test_honeypot_submission_not_stored(tmp_path):
    store = inquiry.InquiryStore(str(tmp_path / "inq.db"))
    status, body = inquiry.handle_submission(valid(website="http://spam.example"), store, today=TODAY)
    assert status == 201 and body["ok"]
    assert store.count() == 0
