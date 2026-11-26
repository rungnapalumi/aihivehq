"""
Coach mobile proof E2E (Playwright, demo mode, no API key).

Verifies:
1. Start Your First Session is fully visible at 375x667 without scrolling
2. Expanded action plan shows goal / key insight / next action
3. Privacy export section is reachable on mobile
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

STREAMLIT_PORT = 8504
BASE_URL = f"http://localhost:{STREAMLIT_PORT}"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = Path("/tmp/aihive_screenshots")


@pytest.fixture(scope="module")
def streamlit_app():
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}' || true", shell=True)
    time.sleep(1)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.pop("OPENAI_API_KEY", None)
    env["APP_ENV"] = "test"
    env["DATABASE_PATH"] = "/tmp/coach_mobile_e2e.db"

    app_path = REPO_ROOT / "aihive_coach" / "app.py"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            f"--server.port={STREAMLIT_PORT}",
            "--server.headless=true",
            "--server.fileWatcherType=none",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
        env=env,
    )
    time.sleep(10)
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}' || true", shell=True)
    if os.path.exists(env["DATABASE_PATH"]):
        os.unlink(env["DATABASE_PATH"])


def _open_sidebar(page):
    control = page.locator('[data-testid="stSidebarCollapsedControl"]')
    if control.count() > 0 and control.first.is_visible():
        control.first.click()
        time.sleep(1)
        return
    header_btn = page.locator('button[kind="header"]')
    if header_btn.count() > 0:
        header_btn.first.click()
        time.sleep(1)


def _click_sidebar(page, label: str):
    _open_sidebar(page)
    time.sleep(1)
    btn = page.locator(f"section[data-testid='stSidebar'] button:has-text('{label}')")
    btn.first.evaluate(
        """el => {
            const sidebar = el.closest('section[data-testid="stSidebar"]') || el.parentElement;
            if (sidebar) sidebar.scrollTop = el.offsetTop - 40;
            el.click();
        }"""
    )
    time.sleep(3)


def _reset_scroll(page):
    page.evaluate(
        """() => {
            document.querySelectorAll('*').forEach((el) => {
                try { el.scrollTop = 0; } catch (e) {}
            });
            window.scrollTo(0, 0);
        }"""
    )
    time.sleep(0.5)


def _assert_fully_in_viewport(page, locator):
    box = locator.first.bounding_box()
    assert box is not None, "Target element has no bounding box"
    height = page.viewport_size["height"]
    assert box["y"] >= 0, f"Element top above viewport: y={box['y']}"
    assert box["y"] + box["height"] <= height + 1, (
        f"Element bottom ({box['y'] + box['height']}) exceeds viewport {height}"
    )


def test_coach_mobile_landing_start_cta_above_fold(streamlit_app):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 375, "height": 667}, device_scale_factor=2)
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)
        _reset_scroll(page)

        open_coach = page.locator("button:has-text('Open AIHive Coach')")
        if open_coach.count() and open_coach.first.is_visible():
            open_coach.first.click()
        else:
            _click_sidebar(page, "AIHive Coach")
        time.sleep(4)

        start = page.locator("button:has-text('Start Your First Session')")
        expect(start.first).to_be_visible(timeout=15000)
        _reset_scroll(page)
        time.sleep(0.5)
        _assert_fully_in_viewport(page, start)

        path = SCREENSHOT_DIR / "coach_mobile_landing_start_cta.png"
        page.screenshot(path=str(path), full_page=False)
        assert path.exists() and path.stat().st_size > 1000
        browser.close()


def test_coach_mobile_action_plan_and_privacy(streamlit_app):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 375, "height": 667}, device_scale_factor=2)
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)

        open_coach = page.locator("button:has-text('Open AIHive Coach')")
        if open_coach.count() and open_coach.first.is_visible():
            open_coach.first.click()
        else:
            _click_sidebar(page, "AIHive Coach")
        time.sleep(3)

        page.locator("button:has-text('Start Your First Session')").first.click()
        time.sleep(3)
        page.get_by_role("button", name="Career & Leadership").first.click()
        time.sleep(3)

        chat = page.locator("[data-testid='stChatInput'] textarea")
        expect(chat.first).to_be_visible(timeout=15000)
        chat.first.fill("I want to become more confident in meetings")
        page.keyboard.press("Enter")
        time.sleep(6)

        page.get_by_role("button", name="Create Action Plan").first.click()
        time.sleep(4)
        page.get_by_role("button", name="Save Action Plan").first.click()
        time.sleep(4)

        # Quick nav → My Plans
        qnav = page.locator('[data-testid="stExpander"]').filter(has_text="Quick Navigation")
        if qnav.count():
            qnav.locator("summary").first.click()
            time.sleep(1)
        plans_btn = page.get_by_role("button", name="My Plans")
        if plans_btn.count() and plans_btn.first.is_visible():
            plans_btn.first.click()
        else:
            _click_sidebar(page, "My Action Plans")
        time.sleep(3)

        expect(page.get_by_text("My Goal").first).to_be_visible(timeout=15000)
        expect(page.get_by_text("My Key Insight").first).to_be_visible()
        expect(page.get_by_text("My Next Action").first).to_be_visible()

        page.get_by_text("My Goal").first.scroll_into_view_if_needed()
        page.set_viewport_size({"width": 375, "height": 900})
        time.sleep(0.5)
        page.get_by_text("My Goal").first.scroll_into_view_if_needed()

        plan_path = SCREENSHOT_DIR / "coach_mobile_action_plan_expanded.png"
        page.screenshot(path=str(plan_path), full_page=False)
        assert plan_path.exists() and plan_path.stat().st_size > 1000

        _click_sidebar(page, "Privacy & Data")
        expect(page.get_by_text("Download My Data").first).to_be_visible(timeout=15000)
        page.get_by_text("Download My Data").first.scroll_into_view_if_needed()
        expect(page.get_by_role("button", name="Download JSON").first).to_be_visible()
        expect(page.get_by_role("button", name="Download CSV").first).to_be_visible()

        privacy_path = SCREENSHOT_DIR / "coach_mobile_privacy_export.png"
        page.screenshot(path=str(privacy_path), full_page=False)
        assert privacy_path.exists() and privacy_path.stat().st_size > 1000

        browser.close()
