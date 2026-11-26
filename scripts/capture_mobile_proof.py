#!/usr/bin/env python3
"""
Reusable mobile screenshot capture for AIHive Coach + Tutor proof artifacts.

Runs against a local Streamlit app in demo mode (no OpenAI API key required).
Writes PNGs to an output directory (default: /tmp/aihive_screenshots) — never into git.

Usage:
  # Terminal A
  unset OPENAI_API_KEY
  PYTHONPATH=. streamlit run aihive_coach/app.py --server.port=8501 --server.headless=true

  # Terminal B
  PYTHONPATH=. python scripts/capture_mobile_proof.py --base-url http://localhost:8501 \\
      --out /tmp/aihive_screenshots

Artifacts produced:
  coach_mobile_landing_start_cta.png   — 375x667 viewport; Start button above the fold
  coach_mobile_action_plan_expanded.png — expanded plan with goal / insight / next action
  coach_mobile_privacy_export.png      — Privacy "Download My Data" section
  tutor_mobile_session_summary.png     — 390px-wide summary with counts + practice questions
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, expect


def wait_app(page: Page, seconds: float = 2.0) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def open_sidebar(page: Page) -> None:
    """Open Streamlit's collapsed sidebar on mobile viewports."""
    control = page.locator('[data-testid="stSidebarCollapsedControl"]')
    if control.count() > 0 and control.first.is_visible():
        control.first.click()
        wait_app(page, 1)
        return
    header_btn = page.locator('button[kind="header"]')
    if header_btn.count() > 0:
        header_btn.first.click()
        wait_app(page, 1)


def js_click(locator) -> None:
    """Click via DOM — Streamlit sidebar buttons are often outside the mobile viewport."""
    locator.first.evaluate("el => el.click()")


def click_sidebar_button(page: Page, label: str) -> None:
    open_sidebar(page)
    wait_app(page, 1)
    btn = page.locator(f"section[data-testid='stSidebar'] button:has-text('{label}')")
    if btn.count() == 0:
        btn = page.locator(f"button:has-text('{label}')")
    # Scroll sidebar itself if needed, then JS-click (avoids Playwright viewport checks)
    btn.first.evaluate(
        """el => {
            const sidebar = el.closest('section[data-testid="stSidebar"]') || el.parentElement;
            if (sidebar) sidebar.scrollTop = el.offsetTop - 40;
            el.click();
        }"""
    )
    wait_app(page, 3)


def scroll_main(page: Page, y: int = 0) -> None:
    page.evaluate(
        """(y) => {
            document.querySelectorAll('*').forEach((el) => {
                try { el.scrollTop = y; } catch (e) {}
            });
            window.scrollTo(0, y);
            if (document.scrollingElement) document.scrollingElement.scrollTop = y;
        }""",
        y,
    )
    wait_app(page, 0.5)


def scroll_locator_into_view(page: Page, locator) -> None:
    locator.first.scroll_into_view_if_needed()
    wait_app(page, 0.5)


def assert_in_viewport(page: Page, locator) -> None:
    box = locator.first.bounding_box()
    assert box is not None, "Target element has no bounding box"
    viewport = page.viewport_size or {"width": 0, "height": 0}
    assert box["y"] >= 0, f"Element top is above viewport: y={box['y']}"
    assert box["y"] + box["height"] <= viewport["height"] + 1, (
        f"Element bottom ({box['y'] + box['height']}) exceeds viewport height {viewport['height']}"
    )


def capture_coach_landing(page: Page, out: Path) -> Path:
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(page.url.split("?")[0], wait_until="domcontentloaded")
    wait_app(page, 4)
    scroll_main(page, 0)

    # Prefer on-page hub launch (no sidebar required)
    open_coach = page.locator("button:has-text('Open AIHive Coach')")
    if open_coach.count() > 0 and open_coach.first.is_visible():
        open_coach.first.click()
        wait_app(page, 4)
    else:
        click_sidebar_button(page, "AIHive Coach")

    start_btn = page.locator("button:has-text('Start Your First Session')")
    expect(start_btn.first).to_be_visible(timeout=15000)
    scroll_main(page, 0)
    wait_app(page, 1)
    # If Streamlit left us scrolled, pull the CTA to the top of the viewport
    start_btn.first.evaluate("el => el.scrollIntoView({block: 'start', inline: 'nearest'})")
    wait_app(page, 0.5)
    scroll_main(page, 0)
    wait_app(page, 0.5)
    assert_in_viewport(page, start_btn)

    path = out / "coach_mobile_landing_start_cta.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def capture_coach_action_plan(page: Page, out: Path) -> Path:
    page.set_viewport_size({"width": 375, "height": 667})

    # Start session from landing CTA if present, else sidebar
    start_btn = page.get_by_role("button", name="Start Your First Session")
    if start_btn.count() > 0 and start_btn.first.is_visible():
        start_btn.first.click()
        wait_app(page, 3)
    else:
        click_sidebar_button(page, "Start Coaching")

    # Category selection
    category = page.get_by_role("button", name="Career & Leadership")
    if category.count() == 0:
        category = page.get_by_role("button", name="Personal Growth")
    expect(category.first).to_be_visible(timeout=15000)
    category.first.click()
    wait_app(page, 3)

    chat = page.locator("[data-testid='stChatInput'] textarea")
    expect(chat.first).to_be_visible(timeout=15000)
    chat.first.fill("I want to become more confident speaking up in meetings")
    page.keyboard.press("Enter")
    wait_app(page, 6)

    create = page.get_by_role("button", name="Create Action Plan")
    expect(create.first).to_be_visible(timeout=15000)
    create.first.click()
    wait_app(page, 4)

    save = page.get_by_role("button", name="Save Action Plan")
    expect(save.first).to_be_visible(timeout=15000)
    save.first.click()
    wait_app(page, 4)

    # Navigate to plans via quick nav (reliable on mobile) or sidebar
    expander = page.locator('[data-testid="stExpander"]').filter(has_text="Quick Navigation")
    if expander.count() > 0:
        summary = expander.locator("summary").first
        if summary.count():
            js_click(summary)
            wait_app(page, 1)
    plans_quick = page.locator("button:has-text('My Plans')")
    if plans_quick.count() > 0:
        js_click(plans_quick)
        wait_app(page, 3)
    else:
        click_sidebar_button(page, "My Action Plans")

    # Prefer main content (sidebar also contains "My Action Plans" text, often hidden on mobile)
    main = page.locator('[data-testid="stMainBlockContainer"]')
    expect(main.get_by_text("My Action Plans").first).to_be_visible(timeout=15000)

    # Newest plan starts expanded; ensure fields are in view
    for label in ["My Goal", "My Key Insight", "My Next Action"]:
        expect(main.get_by_text(label, exact=False).first).to_be_visible(timeout=10000)

    goal = main.get_by_text("My Goal", exact=False).first
    scroll_locator_into_view(page, goal)

    # Use a taller capture height so expanded fields are readable in-frame
    page.set_viewport_size({"width": 375, "height": 900})
    wait_app(page, 0.5)
    scroll_locator_into_view(page, goal)

    path = out / "coach_mobile_action_plan_expanded.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def capture_coach_privacy(page: Page, out: Path) -> Path:
    page.set_viewport_size({"width": 375, "height": 900})
    click_sidebar_button(page, "Privacy & Data")
    main = page.locator('[data-testid="stMainBlockContainer"]')
    expect(main.get_by_text("Download My Data").first).to_be_visible(timeout=15000)

    export_heading = main.get_by_text("Download My Data").first
    export_heading.evaluate("el => el.scrollIntoView({block: 'start'})")
    wait_app(page, 0.5)
    expect(page.locator("button:has-text('Download JSON')").first).to_be_visible()
    expect(page.locator("button:has-text('Download CSV')").first).to_be_visible()

    path = out / "coach_mobile_privacy_export.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def capture_tutor_summary(page: Page, out: Path) -> Path:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(page.url.split("?")[0], wait_until="domcontentloaded")
    wait_app(page, 3)

    open_tutor = page.locator("button:has-text('Open AIHive Tutor')")
    if open_tutor.count() > 0 and open_tutor.first.is_visible():
        open_tutor.first.click()
        wait_app(page, 3)
    else:
        click_sidebar_button(page, "Start Learning")

    expect(page.get_by_text("What do you want to learn today?").first).to_be_visible(timeout=15000)
    page.locator("button:has-text('Photosynthesis')").first.click()
    wait_app(page, 1)
    # Primary CTA in main content (sidebar also has "Start Learning")
    page.locator('[data-testid="stMainBlockContainer"] button:has-text("Start Learning")').first.click()
    wait_app(page, 5)

    chat = page.get_by_placeholder("Type your answer here...")
    expect(chat).to_be_visible(timeout=15000)

    # Incorrect then correct so both counts are non-zero
    chat.fill("I don't know")
    chat.press("Enter")
    wait_app(page, 5)

    chat = page.get_by_placeholder("Type your answer here...")
    chat.fill("Plants use sunlight, water, and carbon dioxide to make food through photosynthesis.")
    chat.press("Enter")
    wait_app(page, 5)

    page.locator("button:has-text('End Lesson')").first.click()
    wait_app(page, 5)

    expect(page.get_by_text("Lesson Complete!").first).to_be_visible(timeout=15000)
    expect(page.get_by_text("Questions Correct").first).to_be_visible()
    expect(page.get_by_text("Questions Incorrect").first).to_be_visible()
    expect(page.get_by_text("Practice Questions for Review").first).to_be_visible()

    results = page.get_by_text("Your Results").first
    scroll_locator_into_view(page, results)

    # Tall enough that counts + practice questions share one frame
    page.set_viewport_size({"width": 390, "height": 1000})
    wait_app(page, 0.5)
    scroll_locator_into_view(page, results)

    path = out / "tutor_mobile_session_summary.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Coach/Tutor mobile proof screenshots")
    parser.add_argument("--base-url", default=os.environ.get("AIHIVE_BASE_URL", "http://localhost:8501"))
    parser.add_argument("--out", default="/tmp/aihive_screenshots")
    parser.add_argument(
        "--only",
        choices=["landing", "plan", "privacy", "tutor", "all"],
        default="all",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Capturing from {args.base_url} → {out}")
    paths = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 375, "height": 667},
            device_scale_factor=2,
        )
        page = context.new_page()
        page.goto(args.base_url, wait_until="domcontentloaded", timeout=60000)
        wait_app(page, 4)

        if args.only in ("landing", "all"):
            paths.append(capture_coach_landing(page, out))
            print(f"✓ {paths[-1].name}")
        if args.only in ("plan", "all"):
            # Landing leaves us on Coach; plan capture continues from there
            if args.only == "plan":
                capture_coach_landing(page, out)
            paths.append(capture_coach_action_plan(page, out))
            print(f"✓ {paths[-1].name}")
        if args.only in ("privacy", "all"):
            paths.append(capture_coach_privacy(page, out))
            print(f"✓ {paths[-1].name}")
        if args.only in ("tutor", "all"):
            paths.append(capture_tutor_summary(page, out))
            print(f"✓ {paths[-1].name}")

        browser.close()

    print("Done:")
    for path in paths:
        print(f"  {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
