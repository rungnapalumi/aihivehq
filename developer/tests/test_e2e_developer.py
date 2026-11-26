"""
Playwright E2E smoke test for AIHive Developer Agent.
Screenshots saved under /tmp (not committed).
"""
import time
import os
import pytest
from playwright.sync_api import expect

SCREENSHOT_DIR = "/tmp"


def test_developer_code_review_smoke(page, app_url, streamlit_app):
    """
    Smoke: open Developer Assistant, run a demo code review, assert demo label.
    """
    page.goto(app_url, timeout=30000)
    time.sleep(3)

    # Navigate via sidebar
    nav = page.locator("button:has-text('🛠️ Developer Assistant')")
    expect(nav).to_be_visible(timeout=15000)
    nav.click()
    time.sleep(2)

    expect(page.locator("h1:has-text('🛠️ Developer Assistant')")).to_be_visible(
        timeout=10000
    )

    # Demo banner must be present (E2E runs without a real key)
    page_text = page.content()
    assert "Demo mode" in page_text or "demo" in page_text.lower()
    assert "AI-powered" not in page.locator("text=Demo mode").first.inner_text().lower() \
        if page.locator("text=Demo mode").count() else True

    # Fill code review form (default tab)
    code_box = page.get_by_role("textbox", name="Code")
    expect(code_box).to_be_visible(timeout=10000)
    code_box.fill("x = eval(user_input)\npassword = 'secret'")

    review_btn = page.locator("button:has-text('🔍 Review Code')")
    expect(review_btn).to_be_visible()
    review_btn.click()
    time.sleep(4)

    # Result should mention demo labeling and a security finding
    content = page.content()
    assert "Review complete" in content or "Summary" in content or "security" in content.lower()
    assert "Demo mode" in content or "scripted" in content.lower()

    # Desktop screenshot artifact
    page.screenshot(
        path=os.path.join(SCREENSHOT_DIR, "developer_desktop_code_review.png"),
        full_page=True,
    )

    # Mobile viewport screenshot
    page.set_viewport_size({"width": 390, "height": 844})
    time.sleep(1)
    page.screenshot(
        path=os.path.join(SCREENSHOT_DIR, "developer_mobile_code_review.png"),
        full_page=True,
    )

    # Architecture tab smoke + third screenshot
    page.set_viewport_size({"width": 1440, "height": 900})
    arch_tab = page.get_by_role("tab", name="Architecture Helper")
    if arch_tab.count():
        arch_tab.click()
        time.sleep(1)
        req = page.get_by_role("textbox", name="App idea / requirements")
        if req.count():
            req.fill("A personal habit tracker with a simple web UI")
            page.locator("button:has-text('🏗️ Suggest Architecture')").click()
            time.sleep(3)
            page.screenshot(
                path=os.path.join(SCREENSHOT_DIR, "developer_desktop_architecture.png"),
                full_page=True,
            )
            arch_content = page.content()
            assert "component" in arch_content.lower() or "hosting" in arch_content.lower()
