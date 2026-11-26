"""E2E: Book a session / นัดหมาย page renders."""
from __future__ import annotations

import os
import sys
import time
import subprocess

import pytest
from playwright.sync_api import expect, sync_playwright

STREAMLIT_PORT = 8506
APP_URL = f"http://localhost:{STREAMLIT_PORT}"


@pytest.fixture(scope="module")
def streamlit_app():
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["DATABASE_PATH"] = "test_e2e_booking.db"
    env.pop("OPENAI_API_KEY", None)
    env.pop("AIHIVE_CALDAV_PASSWORD", None)
    env.pop("STRIPE_SECRET_KEY", None)
    env.pop("AIHIVE_PAYMENTS_LIVE", None)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env["PYTHONPATH"] = repo_root
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_path = os.path.join(app_dir, "app.py")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            app_path,
            "--server.port",
            str(STREAMLIT_PORT),
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(5)
    yield
    process.terminate()
    process.wait()
    if os.path.exists("test_e2e_booking.db"):
        os.unlink("test_e2e_booking.db")


@pytest.fixture
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


def _assert_password_not_on_page(page):
    for key in ("AIHIVE_CALDAV_PASSWORD", "PRIVATEEMAIL_PASSWORD"):
        secret = os.environ.get(key)
        if secret and secret in page.content():
            pytest.fail("Calendar password appeared on the booking page")


def test_booking_page_renders(streamlit_app, browser_context):
    page = browser_context.new_page()
    page.goto(APP_URL)
    time.sleep(3)
    expect(page.locator("section[data-testid='stSidebar']")).to_be_visible(timeout=10000)
    page.locator("section[data-testid='stSidebar'] button:has-text('นัดหมาย')").click()
    time.sleep(3)
    expect(page.locator("text=Book a session").first).to_be_visible()
    expect(page.locator("text=นัดหมาย").first).to_be_visible()
    expect(page.locator("text=Name / ชื่อ").first).to_be_visible()
    expect(page.locator("text=Email / อีเมล").first).to_be_visible()
    expect(page.locator("text=Topic (optional)").first).to_be_visible()
    expect(page.locator("text=Date / วันที่").first).to_be_visible()
    expect(page.locator("text=ทดลองใช้ฟรี").first).to_be_visible()
    expect(page.locator("button:has-text('จองทดลองใช้')").first).to_be_visible()
    # Unconfigured calendar must be described honestly, not as already synced.
    content = page.content()
    assert "calendar sync is pending" in content.lower() or "การซิงค์ปฏิทินยังค้างอยู่" in content
    assert "successfully synced to the calendar" not in content.lower()
    _assert_password_not_on_page(page)


def test_booking_page_shows_free_slots_not_other_customers(streamlit_app, browser_context):
    page = browser_context.new_page()
    page.goto(APP_URL)
    time.sleep(3)
    page.locator("section[data-testid='stSidebar'] button:has-text('นัดหมาย')").click()
    time.sleep(3)
    content = page.content()
    # A fresh test DB has no other customers; the page must not invent any.
    assert "ada-private@example.com" not in content
    assert "Confidential career plan" not in content
    # Times should appear for a day that still has slots (page defaults to today;
    # if after 21:00 Bangkok the copy explains there are no remaining times).
    has_slot = "19:00" in content or "19:30" in content or "20:00" in content or "20:30" in content
    has_empty_copy = "No remaining times" in content or "No free slots" in content or "ไม่มีช่วง" in content
    assert has_slot or has_empty_copy
    _assert_password_not_on_page(page)


def test_paid_session_shows_payments_not_enabled(streamlit_app, browser_context):
    """Paid path must not fake a confirmation when Stripe is not configured."""
    page = browser_context.new_page()
    page.goto(APP_URL)
    time.sleep(3)
    page.locator("section[data-testid='stSidebar'] button:has-text('นัดหมาย')").click()
    time.sleep(3)
    page.locator('[data-testid="stRadioOption"]:has-text("นัด 30 นาที")').click()
    time.sleep(3)
    content = page.content()
    assert "Payments are not yet enabled" in content or "ยังไม่เปิดรับชำระเงิน" in content
    assert "placeholder" in content.lower() or "ราคาตัวอย่าง" in content
    assert "Payment verified" not in content
    assert "ชำระแล้ว" not in content
    pay = page.locator("button:has-text('ชำระเงิน')")
    if pay.count():
        assert pay.first.is_disabled()
    _assert_password_not_on_page(page)
