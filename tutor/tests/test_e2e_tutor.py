"""
E2E test for AIHive Tutor using Playwright (demo mode, no API key).
Captures mobile proof screenshots to /tmp (never into the repo).
"""
import pytest
import subprocess
import time
import os
import sys
from playwright.sync_api import sync_playwright, expect

STREAMLIT_PORT = 8503
BASE_URL = f"http://localhost:{STREAMLIT_PORT}"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENSHOT_DIR = "/tmp/aihive_screenshots"


@pytest.fixture(scope="module")
def streamlit_app():
    """Start Streamlit app for testing in demo mode (no API key)."""
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}' || true", shell=True)
    time.sleep(1)

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    app_path = os.path.join(REPO_ROOT, "aihive_coach", "app.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT
    env.pop("OPENAI_API_KEY", None)
    env["APP_ENV"] = "test"
    env["DATABASE_PATH"] = os.path.join("/tmp", "tutor_e2e_test.db")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            app_path,
            f"--server.port={STREAMLIT_PORT}",
            "--server.headless=true",
            "--server.fileWatcherType=none",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
        env=env,
    )

    print(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    time.sleep(10)

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}' || true", shell=True)
    db_path = env.get("DATABASE_PATH")
    if db_path and os.path.exists(db_path):
        os.unlink(db_path)


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


def test_complete_tutor_flow_with_screenshots(streamlit_app):
    """
    E2E: demo tutor flow with one incorrect + one correct answer.
    Mobile (390px) summary must show non-zero correct/incorrect counts and practice questions.
    """
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Desktop topic picker
        print("\n1. Capturing desktop topic picker...")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)

        open_tutor = page.locator("button:has-text('Open AIHive Tutor')")
        if open_tutor.count() > 0 and open_tutor.first.is_visible():
            open_tutor.first.click()
        else:
            page.locator("section[data-testid='stSidebar'] button:has-text('Start Learning')").first.click()
        time.sleep(2)

        expect(page.get_by_text("What do you want to learn today?")).to_be_visible()
        screenshot_path = os.path.join(SCREENSHOT_DIR, "tutor_desktop_topic_picker.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"   ✓ Saved: {screenshot_path}")
        page.close()

        # Lesson + summary on mobile 390px
        print("\n2. Starting mobile lesson flow (390px)...")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)

        open_tutor = page.locator("button:has-text('Open AIHive Tutor')")
        if open_tutor.count() > 0 and open_tutor.first.is_visible():
            open_tutor.first.click()
        else:
            _open_sidebar(page)
            page.locator("section[data-testid='stSidebar'] button:has-text('Start Learning')").first.click(
                force=True
            )
        time.sleep(2)

        page.get_by_text("🌱 Photosynthesis").click()
        time.sleep(1)
        page.get_by_role("button", name="🚀 Start Learning").click()
        time.sleep(5)

        expect(page.locator(".stChatMessage").first).to_be_visible(timeout=10000)

        print("\n3. Wrong answer...")
        chat_input = page.get_by_placeholder("Type your answer here...")
        expect(chat_input).to_be_visible(timeout=5000)
        chat_input.fill("I don't know")
        chat_input.press("Enter")
        time.sleep(5)

        mid_path = os.path.join(SCREENSHOT_DIR, "tutor_mobile_mid_lesson.png")
        page.screenshot(path=mid_path, full_page=False)
        print(f"   ✓ Saved: {mid_path}")

        print("\n4. Correct answer...")
        chat_input = page.get_by_placeholder("Type your answer here...")
        chat_input.fill(
            "Plants use sunlight, water, and carbon dioxide to make food through photosynthesis."
        )
        chat_input.press("Enter")
        time.sleep(5)

        print("\n5. Ending lesson...")
        page.get_by_role("button", name="✅ End Lesson").click()
        time.sleep(5)

        expect(page.get_by_text("Lesson Complete!")).to_be_visible(timeout=10000)
        main = page.locator('[data-testid="stMainBlockContainer"]')
        expect(main.get_by_text("Questions Correct", exact=True)).to_be_visible()
        expect(main.get_by_text("Questions Incorrect", exact=True)).to_be_visible()
        expect(main.get_by_text("Practice Questions for Review")).to_be_visible()

        body = main.inner_text()
        assert "Questions Correct" in body
        assert "Questions Incorrect" in body
        assert "Practice Questions for Review" in body

        # Metric values: after one wrong + one right, both should show 1
        metrics = page.locator("[data-testid='stMetricValue']")
        metric_values = [metrics.nth(i).inner_text().strip() for i in range(min(metrics.count(), 3))]
        print(f"   Metric values: {metric_values}")
        assert metric_values.count("1") >= 2, (
            f"Expected correct=1 and incorrect=1, got metric values {metric_values}"
        )

        results = main.get_by_text("Your Results").first
        results.scroll_into_view_if_needed()
        time.sleep(0.5)
        page.set_viewport_size({"width": 390, "height": 1000})
        results.scroll_into_view_if_needed()
        time.sleep(0.5)

        summary_path = os.path.join(SCREENSHOT_DIR, "tutor_mobile_summary.png")
        page.screenshot(path=summary_path, full_page=False)
        print(f"   ✓ Saved: {summary_path}")

        page.close()
        browser.close()

    print("\n✅ Tutor E2E completed (demo mode, no API key)")
