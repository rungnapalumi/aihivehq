"""AIHive Leadership preview server (standard library only).

Serves the static website in ``site/`` and one API endpoint:

    POST /api/leadership/inquiry   -> stores a corporate program inquiry (JSON)

Run locally:   PORT=8000 python -m leadership.server
On Render:     start command ``python -m leadership.server`` (free web service, preview only).

The production site (aihivehq.com) is a static site with no backend; this server exists so
the inquiry form can be tested end-to-end in the preview environment.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from collections import defaultdict, deque
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from leadership import inquiry

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
MAX_BODY = 16 * 1024
RATE_LIMIT = 10         # submissions
RATE_WINDOW = 600       # seconds

log = logging.getLogger("aihive.leadership")

LEADERSHIP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)


class RateLimiter:
    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW):
        self.limit, self.window = limit, window
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


class Handler(SimpleHTTPRequestHandler):
    server_version = "AIHive"
    sys_version = ""

    def __init__(self, *args, store=None, limiter=None, **kwargs):
        self.store = store
        self.limiter = limiter
        super().__init__(*args, **kwargs)

    # -- headers --
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        if self.path.startswith("/leadership") or self.path.startswith("/api/"):
            self.send_header("Content-Security-Policy", LEADERSHIP_CSP)
        super().end_headers()

    def log_message(self, fmt, *args):  # keep access logs free of query strings / PII
        log.info("%s %s", self.command, self.path.split("?")[0])

    def _client_key(self) -> str:
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def _json(self, status: int, body: dict):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/leadership/health":
            return self._json(200, {"ok": True})
        if self.path.startswith("/api/"):
            return self._json(404, {"ok": False, "error": "Not found"})
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/leadership/inquiry":
            return self._json(404, {"ok": False, "error": "Not found"})
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return self._json(415, {"ok": False, "error": "Content-Type must be application/json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_BODY:
            return self._json(413 if length > MAX_BODY else 400, {"ok": False, "error": "Invalid request size"})
        if not self.limiter.allow(self._client_key()):
            return self._json(429, {"ok": False, "error": "Too many requests"})
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json(400, {"ok": False, "errors": {"_form": "Invalid JSON"}})
        try:
            status, body = inquiry.handle_submission(payload, self.store)
        except Exception:  # pragma: no cover - defensive
            log.exception("inquiry handling failed")
            return self._json(500, {"ok": False, "error": "Server error"})
        if status == 201:
            log.info("leadership inquiry accepted ref=%s email_delivery=%s", body.get("reference"), body.get("email_delivery"))
        else:
            log.info("leadership inquiry rejected fields=%s", ",".join(sorted(body.get("errors", {}))))
        return self._json(status, body)


def make_server(host: str = "0.0.0.0", port: int = 8000, db_path: str | None = None) -> ThreadingHTTPServer:
    settings = inquiry.get_settings()
    store = inquiry.InquiryStore(db_path or settings["db_path"])
    handler = partial(Handler, directory=str(SITE_DIR), store=store, limiter=RateLimiter())
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.store = store  # type: ignore[attr-defined]
    return httpd


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    port = int(os.environ.get("PORT", "8000"))
    httpd = make_server(port=port)
    log.info("AIHive Leadership preview server on port %s (email delivery: not enabled)", port)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
