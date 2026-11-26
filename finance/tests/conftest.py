"""
Finance E2E Test Fixtures
"""
import pytest
import subprocess
import time
import os
import sys
from playwright.sync_api import sync_playwright

STREAMLIT_PORT = 8505
APP_URL = f"http://localhost:{STREAMLIT_PORT}"


@pytest.fixture(scope="module")
def streamlit_app():
    """Start Streamlit app for finance E2E testing"""
    subprocess.run(f"pkill -f 'streamlit.*{STREAMLIT_PORT}'", shell=True)
    time.sleep(1)

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app_path = os.path.join(repo_root, "aihive_coach", "app.py")

    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root
    # Ensure demo mode for E2E (no real API key required)
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
        cwd=repo_root,
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
def app_url():
    return APP_URL
