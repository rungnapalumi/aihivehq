"""
Unit tests for DeveloperAI — all three features, demo labeling, cost guard,
mocked OpenAI (fake key via monkeypatch; never skip for missing real key).
"""
import io
import logging
import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from developer.developer_ai import (
    DeveloperAI,
    CostGuardExceeded,
    DEMO_LABEL,
    DEFAULT_SESSION_COST_LIMIT_USD,
)
from developer.models import CodeReviewResult, DebugResult, ArchitectureResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_ai_with_mock(monkeypatch, content: str, prompt_tokens=120, completion_tokens=80):
    """Build a DeveloperAI in non-demo mode with a mocked OpenAI client."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-not-real")
    # is_demo_mode() reads the class attribute via classmethod
    monkeypatch.setattr(
        "aihive_coach.config.Config.OPENAI_API_KEY", "sk-test-fake-key-not-real"
    )
    monkeypatch.setattr(
        "aihive_coach.config.config.OPENAI_API_KEY", "sk-test-fake-key-not-real"
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    mock_response.usage.total_tokens = prompt_tokens + completion_tokens
    mock_client.chat.completions.create.return_value = mock_response

    mock_openai_mod = MagicMock()
    mock_openai_mod.OpenAI.return_value = mock_client
    monkeypatch.setitem(sys.modules, "openai", mock_openai_mod)

    ai = DeveloperAI()
    assert ai.is_demo is False, "Fake key must disable demo mode"
    assert ai.client is mock_client
    return ai, mock_client


def _make_demo_ai(monkeypatch):
    """Force demo mode (no key)."""
    monkeypatch.setattr("aihive_coach.config.Config.OPENAI_API_KEY", None)
    monkeypatch.setattr("aihive_coach.config.config.OPENAI_API_KEY", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ai = DeveloperAI()
    assert ai.is_demo is True
    return ai


# ---------------------------------------------------------------------------
# Code review
# ---------------------------------------------------------------------------
def test_code_review_ai_mocked(monkeypatch):
    payload = """
    {
      "summary": "Two issues found",
      "issues": [
        {
          "severity": "high",
          "category": "security",
          "description": "SQL string concatenation",
          "suggested_fix": "Use parameterized queries"
        },
        {
          "severity": "low",
          "category": "readability",
          "description": "Magic number",
          "suggested_fix": "Name the constant"
        }
      ]
    }
    """
    ai, client = _make_ai_with_mock(monkeypatch, payload)
    result = ai.review_code("query = 'SELECT * FROM t WHERE id=' + user_id", "python")

    assert isinstance(result, CodeReviewResult)
    assert result.is_demo is False
    assert len(result.issues) == 2
    assert result.issues[0].severity == "high"
    assert result.issues[0].category == "security"
    assert "parameterized" in result.issues[0].suggested_fix.lower()
    assert result.estimated_cost_usd > 0
    client.chat.completions.create.assert_called_once()


def test_code_review_demo_labels_and_security_heuristic(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    result = ai.review_code("x = eval(user_input)\npassword = 'secret123'", "python")

    assert result.is_demo is True
    assert result.estimated_cost_usd == 0.0
    assert DEMO_LABEL in result.summary
    assert "AI-powered" not in result.summary.lower()
    severities = {i.category for i in result.issues}
    assert "security" in severities


def test_code_review_demo_default_issue(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    result = ai.review_code("print('hello')", "python")
    assert result.is_demo is True
    assert len(result.issues) >= 1
    assert DEMO_LABEL in result.summary


# ---------------------------------------------------------------------------
# Debugging
# ---------------------------------------------------------------------------
def test_debug_help_ai_mocked(monkeypatch):
    payload = """
    {
      "likely_cause": "Missing dict key 'user_id'",
      "verification_steps": ["Print keys", "Check upstream"],
      "suggested_fix": "Use data.get('user_id')"
    }
    """
    ai, client = _make_ai_with_mock(monkeypatch, payload)
    result = ai.debug_help(
        error_text="KeyError: 'user_id'",
        code="print(data['user_id'])",
        language="python",
    )

    assert isinstance(result, DebugResult)
    assert result.is_demo is False
    assert "user_id" in result.likely_cause
    assert len(result.verification_steps) == 2
    assert "get" in result.suggested_fix.lower()
    assert result.estimated_cost_usd > 0
    client.chat.completions.create.assert_called_once()


def test_debug_help_demo_keyerror(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    result = ai.debug_help(
        error_text="KeyError: 'foo'",
        code="d['foo']",
        language="python",
    )
    assert result.is_demo is True
    assert DEMO_LABEL in result.likely_cause
    assert "AI-powered" not in result.likely_cause.lower()
    assert len(result.verification_steps) >= 1
    assert result.suggested_fix


def test_debug_help_demo_typeerror(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    result = ai.debug_help(
        error_text="TypeError: 'NoneType' object is not subscriptable",
        code="x = None\nx[0]",
    )
    assert result.is_demo is True
    assert "None" in result.likely_cause or "none" in result.likely_cause.lower()


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------
def test_architecture_ai_mocked(monkeypatch):
    payload = """
    {
      "components": ["UI", "API", "SQLite"],
      "data_approach": "Start with SQLite; Postgres later is optional",
      "hosting_options": [
        "Run locally for free",
        "Optional paid always-on host if needed"
      ],
      "trade_offs": "Simple stack is cheaper; paid hosting is optional for uptime"
    }
    """
    ai, client = _make_ai_with_mock(monkeypatch, payload)
    result = ai.architecture_help("A habit tracker web app")

    assert isinstance(result, ArchitectureResult)
    assert result.is_demo is False
    assert "UI" in result.components
    assert any("free" in h.lower() or "local" in h.lower() for h in result.hosting_options)
    # Must not frame paid as required
    joined = " ".join(result.hosting_options + [result.trade_offs]).lower()
    assert "required" not in joined or "not required" in joined or "optional" in joined
    assert result.estimated_cost_usd > 0
    client.chat.completions.create.assert_called_once()


def test_architecture_demo_neutral_costing(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    result = ai.architecture_help("A personal notes app with search")

    assert result.is_demo is True
    assert DEMO_LABEL in result.trade_offs
    assert "AI-powered" not in result.trade_offs.lower()
    assert len(result.components) >= 2
    assert len(result.hosting_options) >= 2
    hosting_blob = " ".join(result.hosting_options).lower()
    assert "free" in hosting_blob or "local" in hosting_blob
    # Paid must not be presented as required
    for option in result.hosting_options:
        lower = option.lower()
        if "paid" in lower:
            assert "required" not in lower or "not required" in lower or "optional" in lower


# ---------------------------------------------------------------------------
# Cost estimation + logging + guard
# ---------------------------------------------------------------------------
def test_estimate_cost_gpt4o_mini_pricing():
    # 1M prompt tokens => $0.15; 1M completion => $0.60
    cost = DeveloperAI.estimate_cost(1_000_000, 1_000_000)
    assert abs(cost - 0.75) < 1e-6

    # Small request
    small = DeveloperAI.estimate_cost(1000, 500)
    expected = 1000 * (0.15 / 1_000_000) + 500 * (0.60 / 1_000_000)
    assert abs(small - expected) < 1e-9


def test_cost_logging_numbers_only_no_key_leak(monkeypatch, caplog):
    monkeypatch.setattr("aihive_coach.config.config.LOG_API_USAGE", True)
    with caplog.at_level(logging.INFO, logger="developer_ai"):
        DeveloperAI.log_estimated_cost(100, 50, 0.000045, "code_review")

    assert caplog.records, "Expected a cost log record"
    msg = caplog.records[-1].getMessage()
    assert "prompt_tokens=100" in msg
    assert "completion_tokens=50" in msg
    assert "estimated_cost_usd=" in msg
    assert "sk-" not in msg
    assert "OPENAI" not in msg
    assert "api_key" not in msg.lower()


def test_cost_guard_blocks_when_limit_reached(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    with pytest.raises(CostGuardExceeded) as exc:
        ai.review_code(
            "print(1)",
            "python",
            session_cost_usd=DEFAULT_SESSION_COST_LIMIT_USD,
            cost_limit_usd=DEFAULT_SESSION_COST_LIMIT_USD,
        )
    assert exc.value.session_cost >= DEFAULT_SESSION_COST_LIMIT_USD


def test_cost_guard_allows_under_limit(monkeypatch):
    ai = _make_demo_ai(monkeypatch)
    result = ai.review_code(
        "print(1)",
        "python",
        session_cost_usd=0.0,
        cost_limit_usd=DEFAULT_SESSION_COST_LIMIT_USD,
    )
    assert result is not None


def test_ai_path_records_estimated_cost(monkeypatch):
    payload = '{"summary":"ok","issues":[]}'
    ai, _ = _make_ai_with_mock(
        monkeypatch, payload, prompt_tokens=200, completion_tokens=100
    )
    result = ai.review_code("x=1", "python")
    expected = DeveloperAI.estimate_cost(200, 100)
    assert abs(result.estimated_cost_usd - expected) < 1e-9


def test_no_api_key_in_demo_result_text(monkeypatch):
    """Ensure scripted outputs never echo key material or claim AI-powered."""
    ai = _make_demo_ai(monkeypatch)
    review = ai.review_code("eval(x)", "python")
    debug = ai.debug_help("KeyError: a", "d['a']")
    arch = ai.architecture_help("todo app")

    for text in (
        review.summary,
        debug.likely_cause,
        arch.trade_offs,
        str(review.model_dump()),
        str(debug.model_dump()),
        str(arch.model_dump()),
    ):
        assert "sk-" not in text
        assert "OPENAI_API_KEY" not in text
        assert "ai-powered" not in text.lower()


def test_fake_key_never_skipped(monkeypatch):
    """Regression: tests must run with a monkeypatched fake key (no skip)."""
    ai, _ = _make_ai_with_mock(
        monkeypatch,
        '{"summary":"s","issues":[{"severity":"low","category":"bug",'
        '"description":"d","suggested_fix":"f"}]}',
    )
    # If we reached here without pytest.skip, the requirement is met.
    assert ai.client is not None
    result = ai.review_code("a=1", "python")
    assert result.is_demo is False
