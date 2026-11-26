"""
Unit tests for FinanceAI — guardrails, demo labelling, cost, no key leakage
All tests run WITHOUT a real OpenAI key (monkeypatch a fake key when needed).
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture
def finance_ai_demo():
    """FinanceAI in demo mode (no API key)."""
    with patch("aihive_coach.config.config.is_demo_mode", return_value=True), \
         patch("aihive_coach.config.config.OPENAI_API_KEY", None):
        from finance.finance_ai import FinanceAI
        ai = FinanceAI()
        ai.is_demo = True
        yield ai


@pytest.fixture
def finance_ai_real(monkeypatch):
    """FinanceAI in real mode with mocked OpenAI — fake key, never skipped."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = (
        "A simple budget starts with income minus planned expenses."
    )
    mock_response.usage.prompt_tokens = 200
    mock_response.usage.completion_tokens = 80
    mock_client.chat.completions.create = Mock(return_value=mock_response)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-not-real")

    with patch("openai.OpenAI", return_value=mock_client), \
         patch("aihive_coach.config.config.OPENAI_API_KEY", "sk-test-fake-key-not-real"), \
         patch("aihive_coach.config.config.is_demo_mode", return_value=False):
        from finance.finance_ai import FinanceAI
        ai = FinanceAI()
        ai.client = mock_client
        ai.is_demo = False
        yield ai, mock_client


def test_guardrail_refusal_investment(finance_ai_demo):
    """Investment questions must be refused without calling AI."""
    answer, cost = finance_ai_demo.answer("Which stocks should I buy?")
    assert "licensed" in answer.lower() or "professional" in answer.lower()
    assert "investment" in answer.lower() or "financial-product" in answer.lower() or "product" in answer.lower()
    assert cost["model"] == "safety-filter"
    assert cost["cost_usd"] == 0.0


def test_guardrail_refusal_crypto(finance_ai_demo):
    answer, cost = finance_ai_demo.answer("Should I invest in bitcoin and crypto?")
    assert cost["model"] == "safety-filter"
    assert "consult" in answer.lower() or "licensed" in answer.lower()


def test_guardrail_refusal_insurance_loan(finance_ai_demo):
    answer, _ = finance_ai_demo.answer("Which insurance and loan products are best?")
    assert "licensed" in answer.lower() or "professional" in answer.lower()


def test_guardrail_refusal_real_mode(finance_ai_real):
    """Guardrail works in real mode too — OpenAI must not be called."""
    ai, mock_client = finance_ai_real
    answer, cost = ai.answer("What ETF or mutual fund should I pick?")
    assert cost["model"] == "safety-filter"
    mock_client.chat.completions.create.assert_not_called()
    assert "licensed" in answer.lower() or "professional" in answer.lower()


def test_demo_labelling(finance_ai_demo):
    """Demo responses must be clearly labelled as scripted, not AI."""
    answer, cost = finance_ai_demo.answer("How do I build a simple monthly budget?")
    assert "Demo mode – scripted, not AI" in answer
    assert "AI-powered" not in answer
    assert cost["model"] == "demo"
    assert cost["cost_usd"] == 0.0


def test_demo_saving_habits(finance_ai_demo):
    answer, _ = finance_ai_demo.answer("How can I start saving and build an emergency fund?")
    assert "Demo mode – scripted, not AI" in answer
    assert len(answer) > 40


def test_is_forbidden_patterns(finance_ai_demo):
    assert finance_ai_demo.is_forbidden("buy apple stock") is True
    assert finance_ai_demo.is_forbidden("predict returns on my portfolio") is True
    assert finance_ai_demo.is_forbidden("which bank is best") is True
    assert finance_ai_demo.is_forbidden("How do I track my grocery spending?") is False
    assert finance_ai_demo.is_forbidden("What is the 50/30/20 rule of thumb?") is False


def test_estimate_cost(finance_ai_demo):
    """gpt-4o-mini: $0.15/$0.60 per 1M tokens."""
    # 1M input + 1M output = 0.15 + 0.60 = 0.75
    cost = finance_ai_demo.estimate_cost(1_000_000, 1_000_000)
    assert abs(cost - 0.75) < 1e-9
    # 1000 in + 500 out
    cost2 = finance_ai_demo.estimate_cost(1000, 500)
    expected = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
    assert abs(cost2 - expected) < 1e-9


def test_real_mode_cost_logging(finance_ai_real, capsys):
    """Real mode returns cost numbers and logs numbers only (no key)."""
    ai, mock_client = finance_ai_real
    answer, cost = ai.answer("How do I organise expense categories?")
    assert "budget" in answer.lower() or "expense" in answer.lower() or "income" in answer.lower()
    assert cost["input_tokens"] == 200
    assert cost["output_tokens"] == 80
    assert cost["cost_usd"] > 0
    expected = ai.estimate_cost(200, 80)
    assert cost["cost_usd"] == expected
    mock_client.chat.completions.create.assert_called_once()

    captured = capsys.readouterr()
    assert "[COST]" in captured.out
    assert "sk-test" not in captured.out
    assert "sk-" not in captured.out


def test_no_key_leakage_in_response(finance_ai_real):
    """Responses and cost_info must never contain the API key."""
    ai, _ = finance_ai_real
    answer, cost = ai.answer("Explain expense tracking habits")
    blob = answer + str(cost)
    assert "sk-test-fake-key-not-real" not in blob
    assert "OPENAI_API_KEY" not in blob


def test_cost_guard_constants():
    """Session cost guard constants are defined and sensible."""
    from finance.finance_ai import SESSION_COST_LIMIT_USD, MAX_QA_TURNS
    assert SESSION_COST_LIMIT_USD > 0
    assert MAX_QA_TURNS > 0


def test_cost_guard_blocks_when_over_limit():
    """Simulate the page-level cost guard logic."""
    from finance.finance_ai import SESSION_COST_LIMIT_USD, MAX_QA_TURNS

    total_cost = SESSION_COST_LIMIT_USD
    turns = 0
    allowed = not (turns >= MAX_QA_TURNS or total_cost >= SESSION_COST_LIMIT_USD)
    assert allowed is False

    total_cost = 0.0
    turns = MAX_QA_TURNS
    allowed = not (turns >= MAX_QA_TURNS or total_cost >= SESSION_COST_LIMIT_USD)
    assert allowed is False

    total_cost = 0.0
    turns = 0
    allowed = not (turns >= MAX_QA_TURNS or total_cost >= SESSION_COST_LIMIT_USD)
    assert allowed is True
