"""End-to-end tests for the stdlib preview server (static pages + inquiry API)."""
import datetime as dt
import json
import threading
import urllib.error
import urllib.request

import pytest

from leadership import server as srv


@pytest.fixture()
def base(tmp_path):
    httpd = srv.make_server(host="127.0.0.1", port=0, db_path=str(tmp_path / "inq.db"))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", httpd
    httpd.shutdown()
    httpd.server_close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def get(url, follow=True):
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    try:
        r = opener.open(url, timeout=10)
        return r.status, r.headers, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode("utf-8", "replace")


def post(url, body, ctype="application/json", headers=None):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": ctype, **(headers or {})})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def payload(**over):
    d = {"full_name": "QA Tester", "company": "QA Co", "email": "qa@example.com", "phone": "", "participants": "1–10",
         "duration": "Half day", "objectives": "Testing the inquiry endpoint end to end.",
         "preferred_date": (dt.date.today() + dt.timedelta(days=30)).isoformat(), "additional": "", "website": "", "consent": True}
    d.update(over)
    return d


def test_pages_are_served(base):
    url, _ = base
    for path in ["/", "/leadership/", "/leadership/expedition/", "/leadership/demo/", "/leadership/assets/sim.js"]:
        status, _, _ = get(url + path)
        assert status == 200, path


def test_directory_without_slash_redirects(base):
    url, _ = base
    status, headers, _ = get(url + "/leadership", follow=False)
    assert status == 301 and headers["Location"].endswith("/leadership/")


def test_security_headers_and_csp(base):
    url, _ = base
    _, headers, _ = get(url + "/leadership/demo/")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    _, home_headers, _ = get(url + "/")
    assert "Content-Security-Policy" not in home_headers  # homepage uses inline scripts; CSP scoped to /leadership


def test_valid_inquiry_is_stored(base):
    url, httpd = base
    status, body = post(url + "/api/leadership/inquiry", payload())
    assert status == 201 and body["ok"] and body["reference"].startswith("LDR-")
    assert body["email_delivery"] == "not_enabled"
    assert httpd.store.get(body["reference"])["company"] == "QA Co"


def test_invalid_inquiry_returns_field_errors(base):
    url, httpd = base
    status, body = post(url + "/api/leadership/inquiry", payload(email="nope", consent=False))
    assert status == 400 and set(body["errors"]) >= {"email", "consent"}
    assert httpd.store.count() == 0


def test_bad_content_type_size_and_json(base):
    url, _ = base
    assert post(url + "/api/leadership/inquiry", b"a=b", ctype="application/x-www-form-urlencoded")[0] == 415
    assert post(url + "/api/leadership/inquiry", b"{not json")[0] == 400
    assert post(url + "/api/leadership/inquiry", b"x" * (srv.MAX_BODY + 1))[0] == 413


def test_rate_limit(base):
    url, _ = base
    hdr = {"X-Forwarded-For": "203.0.113.9"}
    codes = [post(url + "/api/leadership/inquiry", payload(email="bad"), headers=hdr)[0] for _ in range(srv.RATE_LIMIT + 1)]
    assert codes[-1] == 429 and all(c == 400 for c in codes[:-1])


def test_unknown_api_routes_404(base):
    url, _ = base
    assert get(url + "/api/leadership/inquiries")[0] == 404  # no listing endpoint: submissions are never exposed
    assert post(url + "/api/other", payload())[0] == 404


def test_rate_limiter_window():
    rl = srv.RateLimiter(limit=2, window=10)
    assert rl.allow("a", 0) and rl.allow("a", 1) and not rl.allow("a", 2)
    assert rl.allow("a", 12)
