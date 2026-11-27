"""
Test script for AIHiveHQ static site
Verifies deployment-readiness with Playwright
"""
from playwright.sync_api import sync_playwright, expect
from pathlib import Path
import json

import pytest

# Browser-based; excluded from the fast `-m "not e2e"` unit suite.
pytestmark = pytest.mark.e2e


def test_site():
    """Run comprehensive site tests"""
    
    # Setup paths
    site_dir = Path(__file__).parent
    index_path = site_dir / "index.html"
    file_url = f"file://{index_path.absolute()}"
    
    print(f"🧪 Testing AIHiveHQ static site: {file_url}\n")
    
    results = {
        "passed": [],
        "failed": [],
        "warnings": []
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # Test 1: Desktop 1440px - No Horizontal Scroll
        print("1️⃣  Desktop 1440px - Horizontal Scroll Test")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        client_width = page.evaluate("document.documentElement.clientWidth")
        
        if scroll_width <= client_width:
            print(f"   ✅ No horizontal scroll (scrollWidth={scroll_width}, clientWidth={client_width})")
            results["passed"].append("Desktop 1440: No horizontal scroll")
        else:
            print(f"   ❌ Horizontal scroll detected! (scrollWidth={scroll_width}, clientWidth={client_width})")
            results["failed"].append(f"Desktop 1440: Horizontal scroll ({scroll_width} > {client_width})")
        
        page.close()
        
        # Test 2: Mobile 390px - No Horizontal Scroll
        print("\n2️⃣  Mobile 390px - Horizontal Scroll Test")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        client_width = page.evaluate("document.documentElement.clientWidth")
        
        if scroll_width <= client_width:
            print(f"   ✅ No horizontal scroll (scrollWidth={scroll_width}, clientWidth={client_width})")
            results["passed"].append("Mobile 390: No horizontal scroll")
        else:
            print(f"   ❌ Horizontal scroll detected! (scrollWidth={scroll_width}, clientWidth={client_width})")
            results["failed"].append(f"Mobile 390: Horizontal scroll ({scroll_width} > {client_width})")
        
        page.close()
        
        # Test 3: Anchor Links Work
        print("\n3️⃣  Anchor Links Test")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        
        anchors = ["#agents", "#how-it-works", "#about"]
        all_anchors_work = True
        
        for anchor in anchors:
            # Click the anchor link
            page.click(f'a[href="{anchor}"]')
            page.wait_for_timeout(500)
            
            # Check if the target element exists
            target = page.query_selector(anchor)
            if target:
                print(f"   ✅ Anchor '{anchor}' exists and is reachable")
            else:
                print(f"   ❌ Anchor '{anchor}' target not found")
                all_anchors_work = False
        
        if all_anchors_work:
            results["passed"].append("All anchor links work")
        else:
            results["failed"].append("Some anchor links broken")
        
        page.close()
        
        # Test 4: Console Errors Check
        print("\n4️⃣  Console Errors Check")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)  # Wait for any delayed errors
        
        if not console_errors:
            print("   ✅ No console errors detected")
            results["passed"].append("No console errors")
        else:
            print(f"   ❌ {len(console_errors)} console error(s) detected:")
            for error in console_errors:
                print(f"      - {error}")
            results["failed"].append(f"{len(console_errors)} console errors")
        
        page.close()
        
        # Test 5: Basic Accessibility Checks
        print("\n5️⃣  Basic Accessibility Checks")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        
        # Check for alt text on images (SVG icons inline, so check for aria-label)
        images = page.query_selector_all("img")
        images_without_alt = [img for img in images if not img.get_attribute("alt")]
        
        if not images_without_alt:
            print(f"   ✅ All {len(images)} images have alt text")
            results["passed"].append("All images have alt text")
        else:
            print(f"   ⚠️  {len(images_without_alt)} images missing alt text")
            results["warnings"].append(f"{len(images_without_alt)} images missing alt")
        
        # Check for heading hierarchy
        headings = page.evaluate("""
            () => {
                const h1 = document.querySelectorAll('h1').length;
                const h2 = document.querySelectorAll('h2').length;
                const h3 = document.querySelectorAll('h3').length;
                return { h1, h2, h3 };
            }
        """)
        
        print(f"   ℹ️  Heading structure: H1={headings['h1']}, H2={headings['h2']}, H3={headings['h3']}")
        
        if headings['h1'] == 1:
            print("   ✅ Single H1 heading (good for SEO)")
            results["passed"].append("Single H1 heading")
        else:
            print(f"   ⚠️  {headings['h1']} H1 headings found (should be 1)")
            results["warnings"].append(f"{headings['h1']} H1 headings")
        
        # Check for focus visible styles
        focus_styles = page.evaluate("""
            () => {
                const style = document.querySelector('style').textContent;
                return style.includes('focus') && style.includes('outline');
            }
        """)
        
        if focus_styles:
            print("   ✅ Focus styles defined")
            results["passed"].append("Focus styles present")
        else:
            print("   ❌ No focus styles found")
            results["failed"].append("Missing focus styles")
        
        page.close()
        
        # Test 6: Polish Requirements Check
        print("\n6️⃣  Polish Requirements Verification")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        
        # Check decorative card says "Available" (model-backed Coach)
        preview_text = page.text_content(".agent-preview-status")
        if preview_text and "Available" in preview_text:
            print("   ✅ Hero decorative card shows 'Available'")
            results["passed"].append("Decorative card shows Available")
        else:
            print(f"   ❌ Hero decorative card text: '{preview_text}'")
            results["failed"].append("Decorative card wrong text")

        # Honest marketplace badges (aligned with workforce/registry.py)
        expected_badges = {
            "AIHive Coach": "Available",
            "AIHive Tutor": "Available",
            "Finance Agent": "Available",
            "Developer Agent": "Available",
            "Marketing Agent": "Demo",
            "AI Workforce": "Future Vision",
        }
        cards = page.query_selector_all(".agent-card")
        for card in cards:
            title = (card.query_selector(".agent-title") or card).inner_text().split("\n")[0].strip()
            badge_el = card.query_selector(".badge")
            # CSS uses text-transform: uppercase; compare case-insensitively.
            badge = badge_el.inner_text().strip() if badge_el else ""
            expected = expected_badges.get(title)
            if expected is None:
                continue
            if badge.casefold() == expected.casefold():
                print(f"   ✅ {title} badge: {badge}")
                results["passed"].append(f"Badge {title}: {expected}")
            else:
                print(f"   ❌ {title} badge: '{badge}' (expected '{expected}')")
                results["failed"].append(f"Badge {title}: {badge}")

        marketing_note = page.locator(".agent-card", has_text="Marketing Agent").locator(".agent-note")
        if marketing_note.count() and "scripted" in marketing_note.first.inner_text().lower():
            print("   ✅ Marketing Agent notes scripted examples")
            results["passed"].append("Marketing scripted note")
        else:
            print("   ❌ Marketing Agent missing scripted-examples note")
            results["failed"].append("Marketing scripted note missing")

        try_it_links = page.locator("a.btn-agent", has_text="Try it")
        if try_it_links.count() == 4:
            print("   ✅ Four 'Try it' links for model-backed agents")
            results["passed"].append("Try it links for Available agents")
        else:
            print(f"   ❌ Expected 4 'Try it' links, found {try_it_links.count()}")
            results["failed"].append(f"Try it links: {try_it_links.count()}")

        # Check agent grid columns
        grid_columns = page.evaluate("""
            () => {
                const grid = document.querySelector('.agent-grid');
                return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
            }
        """)
        
        if grid_columns == 3:
            print(f"   ✅ Agent grid has {grid_columns} columns on desktop")
            results["passed"].append("Agent grid: 3 columns on desktop")
        else:
            print(f"   ❌ Agent grid has {grid_columns} columns (expected 3)")
            results["failed"].append(f"Agent grid: {grid_columns} columns")
        
        # Check Sign In tooltip
        sign_in_title = page.get_attribute('.nav-cta', 'title')
        if sign_in_title == "Coming soon":
            print("   ✅ Sign In has 'Coming soon' tooltip")
            results["passed"].append("Sign In tooltip present")
        else:
            print(f"   ⚠️  Sign In tooltip: '{sign_in_title}'")
            results["warnings"].append("Sign In tooltip missing/wrong")
        
        page.close()
        
        # Test 7: Mobile Specific Checks
        print("\n7️⃣  Mobile-Specific Tests")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        
        # Check decorative card is hidden on mobile
        card_visible = page.is_visible(".agent-preview-card")
        if not card_visible:
            print("   ✅ Decorative card hidden on mobile (no overlap)")
            results["passed"].append("Mobile: Decorative card hidden")
        else:
            print("   ❌ Decorative card visible on mobile (may overlap)")
            results["failed"].append("Mobile: Decorative card visible")
        
        # Check agent grid is single column
        mobile_columns = page.evaluate("""
            () => {
                const grid = document.querySelector('.agent-grid');
                return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
            }
        """)
        
        if mobile_columns == 1:
            print(f"   ✅ Agent grid has {mobile_columns} column on mobile")
            results["passed"].append("Mobile: Agent grid 1 column")
        else:
            print(f"   ❌ Agent grid has {mobile_columns} columns on mobile (expected 1)")
            results["failed"].append(f"Mobile: Agent grid {mobile_columns} columns")
        
        page.close()
        
        browser.close()
    
    # Print Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    print(f"\n✅ Passed: {len(results['passed'])}")
    for item in results['passed']:
        print(f"   • {item}")
    
    if results['warnings']:
        print(f"\n⚠️  Warnings: {len(results['warnings'])}")
        for item in results['warnings']:
            print(f"   • {item}")
    
    if results['failed']:
        print(f"\n❌ Failed: {len(results['failed'])}")
        for item in results['failed']:
            print(f"   • {item}")
    
    print("\n" + "="*60)
    
    if not results['failed']:
        print("✅ ALL TESTS PASSED - Site is deployment-ready!")
    else:
        print("❌ SOME TESTS FAILED - Review issues above")

    assert not results["failed"], f"Site checks failed: {results['failed']}"


if __name__ == "__main__":
    test_site()
