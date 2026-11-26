"""
AIHive Finance Assistant — Money Coach Q&A
Educational budgeting/saving-habits explanations with strict guardrails.
Uses gpt-4o-mini when an API key is present; otherwise demo scripted replies.
"""
import sys
import os
import re
from typing import Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config

# gpt-4o-mini pricing: $0.15 / $0.60 per 1M tokens
INPUT_PRICE_PER_1M = 0.15
OUTPUT_PRICE_PER_1M = 0.60

# Per-session cost guard (USD)
SESSION_COST_LIMIT_USD = 0.05
MAX_QA_TURNS = 30

REFUSAL_RESPONSE = (
    "I can't help with investment, tax, legal, credit, or financial-product advice. "
    "I'm an educational budgeting assistant only — I can explain general saving habits "
    "and how to organise a personal budget. For investment, tax, or product decisions, "
    "please consult a licensed financial professional."
)

SYSTEM_PROMPT = """You are AIHive Finance Assistant, an EDUCATIONAL budgeting coach.

Your role:
- Explain personal budgeting concepts, expense tracking habits, and general saving practices.
- Help users understand how to organise income and expenses.
- Keep answers clear, practical, and educational.

STRICT GUARDRAILS — you MUST refuse to:
- Recommend specific stocks, funds, crypto, insurance, loans, banks, or any financial products.
- Give investment, tax, legal, or credit advice.
- Predict returns or market performance.
- Suggest which bank, broker, insurance company, or lender to use.

If asked about any of the above, reply briefly that you cannot provide that advice,
offer a short general educational note about budgeting/saving habits if relevant,
and suggest consulting a licensed professional.

Never claim to be a licensed advisor. Always stay educational only.
Keep answers concise (3-6 short paragraphs max)."""


# Keyword patterns that trigger the pre-check refusal (investment/product advice)
FORBIDDEN_PATTERNS = [
    r"\bstock[s]?\b",
    r"\bshare[s]?\b",
    r"\bequities\b",
    r"\bmutual\s+fund",
    r"\betf[s]?\b",
    r"\bcrypto\b",
    r"\bbitcoin\b",
    r"\bethereum\b",
    r"\binvest(?:ing|ment|ments)?\b",
    r"\bportfolio\b",
    r"\bbroker\b",
    r"\binsurance\b",
    r"\bloan[s]?\b",
    r"\bmortgage\b",
    r"\bcredit\s+card\b",
    r"\bwhich\s+bank\b",
    r"\bbest\s+bank\b",
    r"\btax\s+advice\b",
    r"\btax\s+return\b",
    r"\bpredict\s+(?:return|market)",
    r"\breturn(?:s)?\s+on\s+investment\b",
    r"\broi\b",
    r"\bdividend\b",
    r"\bbond[s]?\b",
    r"\breal\s+estate\s+invest",
    r"\bbuy\s+(?:apple|tesla|nvda|bitcoin)",
    r"\blegal\s+advice\b",
]


class FinanceAI:
    """Money coach Q&A with demo mode, guardrails, and cost tracking."""

    def __init__(self):
        self.is_demo = config.is_demo_mode()
        self.client = None
        if not self.is_demo:
            try:
                import openai
                self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            except ImportError:
                self.is_demo = True

    def is_forbidden(self, text: str) -> bool:
        """Keyword pre-check for investment/product/tax/legal questions."""
        text_lower = text.lower()
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate USD cost for gpt-4o-mini ($0.15/$0.60 per 1M tokens)."""
        cost = (
            (input_tokens / 1_000_000.0) * INPUT_PRICE_PER_1M
            + (output_tokens / 1_000_000.0) * OUTPUT_PRICE_PER_1M
        )
        return round(cost, 6)

    def answer(self, question: str, history: list = None) -> Tuple[str, dict]:
        """
        Answer a budgeting/saving question.
        Returns: (response_text, cost_info)
        cost_info always includes model, cost_usd; may include token counts.
        """
        history = history or []

        # Guardrail pre-check — always enforced (demo and real)
        if self.is_forbidden(question):
            return (
                REFUSAL_RESPONSE,
                {"model": "safety-filter", "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            )

        if self.is_demo:
            return self._demo_answer(question)
        return self._ai_answer(question, history)

    def _demo_answer(self, question: str) -> Tuple[str, dict]:
        """Scripted educational responses for demo mode."""
        q = question.lower()

        if any(w in q for w in ["50/30/20", "50-30-20", "fifty thirty"]):
            response = (
                "**Demo mode – scripted, not AI**\n\n"
                "The 50/30/20 idea is a common rule of thumb some people use as a starting "
                "point for organising a budget: about half of take-home pay toward needs, "
                "about 30% toward wants, and about 20% toward saving. It is a general "
                "educational framework — not a recommendation. Your own numbers may differ "
                "based on location, family size, and goals. Use the Budget Builder to see "
                "how your categories compare."
            )
        elif any(w in q for w in ["save", "saving", "emergency"]):
            response = (
                "**Demo mode – scripted, not AI**\n\n"
                "A common educational habit is to treat saving as a planned expense: decide "
                "an amount first, then budget the rest. Many people also keep a small "
                "emergency buffer for unexpected costs. Track spending for a month so you "
                "can see where money actually goes — that awareness often matters more than "
                "any single percentage rule."
            )
        elif any(w in q for w in ["track", "expense", "spend"]):
            response = (
                "**Demo mode – scripted, not AI**\n\n"
                "Expense tracking works best when it is simple and consistent. Record the "
                "date, category, and amount soon after each purchase. At month-end, compare "
                "actual totals to your budget categories. Look for patterns (e.g. food or "
                "transport running high) rather than aiming for perfection every day."
            )
        elif any(w in q for w in ["budget", "income", "category"]):
            response = (
                "**Demo mode – scripted, not AI**\n\n"
                "A basic personal budget starts with monthly income, then lists expense "
                "categories with planned amounts. Subtract planned expenses from income to "
                "see remaining balance. Adjust category amounts until the plan fits your "
                "situation. Revisit the plan when income or costs change."
            )
        else:
            response = (
                "**Demo mode – scripted, not AI**\n\n"
                "I can help with educational questions about budgeting, expense tracking, "
                "and general saving habits. Try asking how to build a simple monthly budget, "
                "how to track spending, or what the 50/30/20 rule of thumb means. "
                "I do not give investment, tax, legal, or product advice."
            )

        cost_info = {
            "model": "demo",
            "input_tokens": len(question.split()),
            "output_tokens": len(response.split()),
            "cost_usd": 0.0,
        }
        return (response, cost_info)

    def _ai_answer(self, question: str, history: list) -> Tuple[str, dict]:
        """Real AI mode using gpt-4o-mini."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        response = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=500,
        )

        text = response.choices[0].message.content.strip()
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost_usd = self.estimate_cost(input_tokens, output_tokens)

        cost_info = {
            "model": config.OPENAI_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }
        # Log numbers only — never log the API key or message content
        print(
            f"[COST] Finance LLM: model={cost_info['model']} "
            f"in={input_tokens} out={output_tokens} usd={cost_usd}"
        )
        return (text, cost_info)


# Global instance
finance_ai = FinanceAI()
