"""
E2E smoke test for AIHive Finance Assistant using Playwright
"""
import pytest
import time
import os
from playwright.sync_api import sync_playwright, expect


def test_finance_page_smoke(streamlit_app, app_url):
    """
    Smoke test: Finance Assistant page loads with disclaimer,
    budget section, and demo labelling.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(app_url, timeout=30000)
        time.sleep(3)

        # Navigate via sidebar
        finance_btn = page.locator("button:has-text('💰 Finance Assistant')")
        expect(finance_btn).to_be_visible(timeout=15000)
        finance_btn.click()
        time.sleep(3)

        # Page title and educational disclaimer
        expect(page.locator("text=AIHive Finance Assistant")).to_be_visible(timeout=10000)
        content = page.content()
        assert "Educational only" in content or "not financial advice" in content.lower()
        assert "Budget Builder" in content or "budget" in content.lower()

        # Demo mode labelling (no API key in E2E)
        assert "Demo" in content

        # Screenshot for smoke evidence (to /tmp, not repo)
        page.screenshot(path="/tmp/finance_e2e_smoke.png", full_page=True)
        print("   ✓ Saved: /tmp/finance_e2e_smoke.png")

        page.close()
        browser.close()

    print("\n✅ Finance E2E smoke test completed successfully!")
