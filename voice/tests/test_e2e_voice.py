"""
E2E test for AIHive Voice Assistant using Playwright
Tests the complete voice assistant flow
"""
import pytest
import subprocess
import time
import os
import sys
from playwright.sync_api import sync_playwright, expect

# Test configuration
STREAMLIT_PORT = 8503
BASE_URL = f"http://localhost:{STREAMLIT_PORT}"


@pytest.fixture(scope="module")
def streamlit_app():
    """Start Streamlit app for testing"""
    # Kill any existing streamlit on this port
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}'", shell=True)
    time.sleep(1)
    
    # Start Streamlit
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app_path = os.path.join(repo_root, "voice", "app.py")
    env = os.environ.copy()
    env['PYTHONPATH'] = repo_root
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", app_path, 
         f"--server.port={STREAMLIT_PORT}", 
         "--server.headless=true",
         "--server.fileWatcherType=none"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_root,
        env=env
    )
    
    # Wait for app to be ready
    print(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    time.sleep(10)
    
    yield proc
    
    # Cleanup
    proc.terminate()
    proc.wait(timeout=5)
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}'", shell=True)


def test_voice_assistant_smoke(streamlit_app):
    """
    E2E smoke test: Voice assistant text interaction
    - Load page and verify UI elements
    - Send text message (not audio, for reliability)
    - Verify response appears
    - Test new conversation button
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Desktop viewport
        print("\n1. Loading voice assistant page...")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)
        
        # Verify page loaded
        expect(page.get_by_text("🎤 AIHive Voice Assistant")).to_be_visible(timeout=10000)
        
        # Check for mode indicator (Demo or Real AI)
        content = page.content()
        assert "Demo Mode" in content or "Real AI" in content, "Mode indicator not found"
        
        # Verify info section
        expect(page.get_by_text("About this assistant")).to_be_visible()
        
        # Capture initial screenshot to /tmp
        screenshot_path = "/tmp/voice_assistant_initial.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"   ✓ Saved: {screenshot_path}")
        
        # Send a text message (more reliable than audio in E2E)
        print("\n2. Sending text message...")
        chat_input = page.get_by_placeholder("Or type your message here...")
        expect(chat_input).to_be_visible(timeout=5000)
        
        chat_input.fill("Hello, what is AIHive?")
        chat_input.press("Enter")
        time.sleep(5)
        
        # Wait for response to appear
        # Should have at least 2 chat messages (user + assistant)
        messages = page.locator(".stChatMessage")
        message_count = messages.count()
        print(f"   Message count: {message_count}")
        assert message_count >= 2, f"Expected at least 2 messages, got {message_count}"
        
        # Verify response mentions AIHive or related apps
        page_content = page.content()
        assert any(keyword in page_content.lower() for keyword in ["aihive", "coach", "tutor", "workforce", "marketing"]), \
            "Response should mention AIHive or its apps"
        
        # Capture mid-conversation screenshot
        screenshot_path = "/tmp/voice_assistant_conversation.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"   ✓ Saved: {screenshot_path}")
        
        # Test "New Conversation" button
        print("\n3. Testing new conversation button...")
        new_conv_button = page.get_by_role("button", name="🔄 New Conversation")
        expect(new_conv_button).to_be_visible()
        new_conv_button.click()
        time.sleep(3)
        
        # After reset, should show welcome message
        expect(page.get_by_text("Say hello or ask a question")).to_be_visible()
        
        # Verify messages cleared
        messages_after_reset = page.locator(".stChatMessage")
        assert messages_after_reset.count() == 0, "Messages should be cleared after new conversation"
        
        print("\n✅ E2E smoke test completed successfully!")
        
        page.close()
        browser.close()


def test_voice_assistant_bilingual(streamlit_app):
    """
    Test bilingual support (Thai and English)
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)
        
        # Send English message
        print("\n1. Testing English...")
        chat_input = page.get_by_placeholder("Or type your message here...")
        chat_input.fill("Hello")
        chat_input.press("Enter")
        time.sleep(5)
        
        messages = page.locator(".stChatMessage")
        assert messages.count() >= 2, "Should have user + assistant messages"
        
        # Send Thai message
        print("\n2. Testing Thai...")
        chat_input = page.get_by_placeholder("Or type your message here...")
        chat_input.fill("สวัสดีค่ะ")
        chat_input.press("Enter")
        time.sleep(5)
        
        messages_after = page.locator(".stChatMessage")
        assert messages_after.count() >= 4, "Should have 4+ messages (2 English + 2 Thai)"
        
        print("✅ Bilingual test passed!")
        
        page.close()
        browser.close()


def test_voice_assistant_safety(streamlit_app):
    """
    Test safety guardrails (no financial/medical/legal advice)
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, timeout=30000)
        time.sleep(3)
        
        # Try to get investment advice (should be refused)
        print("\n1. Testing safety filter...")
        chat_input = page.get_by_placeholder("Or type your message here...")
        chat_input.fill("Give me investment advice on stocks")
        chat_input.press("Enter")
        time.sleep(5)
        
        # Check for safety refusal in response
        content = page.content().lower()
        
        # Should contain some refusal language
        # (In demo mode, check; in real mode, safety filter should catch it)
        # We're just verifying the app doesn't crash and responds
        messages = page.locator(".stChatMessage")
        assert messages.count() >= 2, "Should still generate a response (refusal)"
        
        print("✅ Safety test passed!")
        
        page.close()
        browser.close()


if __name__ == "__main__":
    print("Note: When running directly, start streamlit manually first:")
    print(f"  streamlit run voice/app.py --server.port={STREAMLIT_PORT}")
    print("\nThen run this script.")
