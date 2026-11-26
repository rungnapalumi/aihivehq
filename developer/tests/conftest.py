"""
Developer E2E fixtures (Playwright) and shared unit helpers.
Screenshots go to /tmp — never commit PNGs.
"""
import pytest
import subprocess
import time
import os
import sys
from playwright.sync_api import sync_playwright
from unittest.mock import MagicMock

STREAMLIT_PORT = 8505
APP_URL = f"http://localhost:{STREAMLIT_PORT}"
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
SCREENSHOT_DIR = "/tmp"


@pytest.fixture
def fake_openai_key(monkeypatch):
    """
    Install a fake API key so tests never skip for a missing real key.
    Also clears any demo-forcing env so is_demo_mode() sees the fake key.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-not-real")
    monkeypatch.setattr(
        "aihive_coach.config.Config.OPENAI_API_KEY",
        "sk-test-fake-key-not-real",
    )
    monkeypatch.setattr(
        "aihive_coach.config.config.OPENAI_API_KEY",
        "sk-test-fake-key-not-real",
    )
    return "sk-test-fake-key-not-real"


@pytest.fixture
def mock_openai_client(monkeypatch, fake_openai_key):
    """
    Provide a MagicMock OpenAI client. Patch openai.OpenAI to return it.
    Default response is empty JSON — tests override per feature.
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "{}"
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 150
    mock_client.chat.completions.create.return_value = mock_response

    mock_openai_mod = MagicMock()
    mock_openai_mod.OpenAI.return_value = mock_client
    monkeypatch.setitem(sys.modules, "openai", mock_openai_mod)

    return mock_client, mock_response


@pytest.fixture(scope="module")
def streamlit_app():
    """Start Streamlit app for Developer E2E (port 8505)."""
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}'", shell=True)
    time.sleep(1)

    app_path = os.path.join(REPO_ROOT, "aihive_coach", "app.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT
    # Force demo mode for E2E so we never need a real key
    env.pop("OPENAI_API_KEY", None)

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
    time.sleep(12)

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}'", shell=True)


@pytest.fixture(scope="module")
def browser(streamlit_app):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    yield page
    page.close()


@pytest.fixture(scope="module")
def app_url():
    return APP_URL
