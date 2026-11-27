"""Static checks for the Leadership pages and the main-site navigation."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
L = SITE / "leadership"
PAGES = {"landing": L / "index.html", "expedition": L / "expedition" / "index.html", "demo": L / "demo" / "index.html"}


def read(p):
    return p.read_text(encoding="utf-8")


def test_main_nav_has_leadership_link():
    html = read(SITE / "index.html")
    nav = html[html.index("<nav>"):html.index("</nav>")]
    assert nav.count('href="/leadership/"') == 2  # desktop + mobile menus


def test_leadership_pages_exist_and_share_nav():
    for name, p in PAGES.items():
        html = read(p)
        assert 'href="/leadership/"' in html and 'href="/leadership/expedition/"' in html and 'href="/leadership/demo/"' in html, name
        assert 'aria-current="page"' in html, name
        assert '<meta name="viewport"' in html


def test_landing_copy_and_programs():
    html = read(PAGES["landing"])
    text = re.sub(r"<[^>]+>", "", html)
    assert "Leadership is a journey. Not a classroom." in text
    assert "Experiential Leadership Development Powered by Human Expertise, Orienteering and Artificial Intelligence." in text
    for line in ["The forest is your boardroom.", "The map is your strategy.", "Your team is your greatest asset."]:
        assert line in text
    assert "Explore Leadership Expedition" in text and "Request a Corporate Program" in text
    for prog in ["Leadership Expedition", "Executive Simulation", "Team Transformation"]:
        assert prog in text
    assert text.count("Coming soon") >= 2


def test_expedition_missions_and_journey():
    text = re.sub(r"<[^>]+>", "", read(PAGES["expedition"]))
    for m in ["Strategic Navigator", "Leading Through Uncertainty", "Distributed Leadership", "The CEO Challenge"]:
        assert m in text
    for c in ["Strategic Thinking", "Risk Management", "Adaptability", "Change Management", "Delegation", "Communication",
              "Trust", "Business Judgment", "Prioritization"]:
        assert c in text
    for s in ["Leadership Discovery", "Behavioral Evidence Collection", "AI Leadership Report", "Guided Reflection", "Leadership Action Plan"]:
        assert s in text
    assert "AIHive Coach" in text


def test_inquiry_form_fields():
    html = read(PAGES["expedition"])
    for name in ["full_name", "company", "email", "phone", "participants", "duration", "objectives", "preferred_date", "additional", "consent"]:
        assert f'name="{name}"' in html, name
    assert 'data-endpoint="/api/leadership/inquiry"' in html


def test_demo_labels_simulated_environment():
    html = read(PAGES["demo"]) + read(L / "assets" / "demo.js")
    assert "Simulated training environment" in html or "simulated training environment" in html.lower()
    assert "NOT A REAL" in html


def test_no_prices_testimonials_or_secrets():
    files = list(L.rglob("*.html")) + list(L.rglob("*.js")) + list(L.rglob("*.css"))
    for f in files:
        t = read(f)
        assert not re.search(r"(฿|\bTHB\b|\bUSD\b|\$\s?\d|\bbaht\b)", t, re.I), f
        assert "testimonial" not in t.lower(), f
        assert not re.search(r"sk-[A-Za-z0-9]{10,}|OPENAI_API_KEY|RENDER_API_KEY|rnd_[A-Za-z0-9]{10,}", t), f


def test_images_exist_and_are_credited():
    credits = read(L / "CREDITS.md")
    for p in PAGES.values():
        for src in re.findall(r"/leadership/assets/img/([\w.-]+)", read(p)):
            assert (L / "assets" / "img" / src).exists(), src
            assert src in credits, f"{src} missing from CREDITS.md"
