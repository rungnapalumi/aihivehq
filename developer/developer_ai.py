"""
AIHive Developer Agent — AI logic
Real OpenAI (gpt-4o-mini) when a key is present; scripted demo otherwise.
Includes per-call estimated cost logging (numbers only) and helpers for a
per-session cost guard.
"""
import json
import logging
import re
import sys
import os
from typing import Optional, Tuple, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aihive_coach.config import config
from developer.models import (
    CodeReviewResult,
    ReviewIssue,
    DebugResult,
    ArchitectureResult,
)

# gpt-4o-mini: $0.15 / $0.60 per 1M tokens
PROMPT_COST_PER_TOKEN = 0.15 / 1_000_000
COMPLETION_COST_PER_TOKEN = 0.60 / 1_000_000

# Default per-session spend ceiling (USD). UI/tests can override.
DEFAULT_SESSION_COST_LIMIT_USD = 0.05

logger = logging.getLogger("developer_ai")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


DEMO_LABEL = "Demo mode – scripted, not AI"


class CostGuardExceeded(Exception):
    """Raised when a session would exceed its estimated cost limit."""

    def __init__(self, session_cost: float, limit: float):
        self.session_cost = session_cost
        self.limit = limit
        super().__init__(
            f"Session cost guard exceeded: {session_cost:.6f} >= {limit:.6f}"
        )


class DeveloperAI:
    """Code review, debugging, and architecture guidance."""

    def __init__(self):
        self.is_demo = config.is_demo_mode()
        self.client = None
        if not self.is_demo:
            try:
                import openai
                self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception:
                self.is_demo = True
                self.client = None

    # ------------------------------------------------------------------
    # Cost helpers
    # ------------------------------------------------------------------
    @staticmethod
    def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate USD cost for gpt-4o-mini from token counts."""
        cost = (
            prompt_tokens * PROMPT_COST_PER_TOKEN
            + completion_tokens * COMPLETION_COST_PER_TOKEN
        )
        return round(cost, 8)

    @staticmethod
    def log_estimated_cost(
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float,
        feature: str,
    ) -> None:
        """Log numeric cost fields only — never keys, prompts, or code."""
        if not config.LOG_API_USAGE:
            return
        # Numbers only; no secrets, no user content.
        logger.info(
            "developer_cost feature=%s prompt_tokens=%d completion_tokens=%d "
            "estimated_cost_usd=%.8f",
            feature,
            prompt_tokens,
            completion_tokens,
            estimated_cost_usd,
        )

    @staticmethod
    def check_cost_guard(
        session_cost_usd: float,
        limit_usd: float = DEFAULT_SESSION_COST_LIMIT_USD,
    ) -> None:
        """Raise CostGuardExceeded if the session has hit its spend limit."""
        if session_cost_usd >= limit_usd:
            raise CostGuardExceeded(session_cost_usd, limit_usd)

    # ------------------------------------------------------------------
    # Public feature APIs
    # ------------------------------------------------------------------
    def review_code(
        self,
        code: str,
        language: str,
        session_cost_usd: float = 0.0,
        cost_limit_usd: float = DEFAULT_SESSION_COST_LIMIT_USD,
    ) -> CodeReviewResult:
        self.check_cost_guard(session_cost_usd, cost_limit_usd)
        if self.is_demo or not self.client:
            return self._demo_review(code, language)
        return self._ai_review(code, language)

    def debug_help(
        self,
        error_text: str,
        code: str,
        language: str = "python",
        session_cost_usd: float = 0.0,
        cost_limit_usd: float = DEFAULT_SESSION_COST_LIMIT_USD,
    ) -> DebugResult:
        self.check_cost_guard(session_cost_usd, cost_limit_usd)
        if self.is_demo or not self.client:
            return self._demo_debug(error_text, code, language)
        return self._ai_debug(error_text, code, language)

    def architecture_help(
        self,
        requirements: str,
        session_cost_usd: float = 0.0,
        cost_limit_usd: float = DEFAULT_SESSION_COST_LIMIT_USD,
    ) -> ArchitectureResult:
        self.check_cost_guard(session_cost_usd, cost_limit_usd)
        if self.is_demo or not self.client:
            return self._demo_architecture(requirements)
        return self._ai_architecture(requirements)

    # ------------------------------------------------------------------
    # OpenAI calls
    # ------------------------------------------------------------------
    def _chat(self, system: str, user: str, feature: str) -> Tuple[str, float]:
        response = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=min(config.MAX_TOKENS, 1500),
        )
        text = (response.choices[0].message.content or "").strip()
        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = self.estimate_cost(prompt_tokens, completion_tokens)
        self.log_estimated_cost(prompt_tokens, completion_tokens, cost, feature)
        return text, cost

    def _ai_review(self, code: str, language: str) -> CodeReviewResult:
        system = (
            "You are AIHive Developer Agent. Review the pasted code for bugs, "
            "security issues, and readability. Respond ONLY with valid JSON:\n"
            '{"summary":"...","issues":[{"severity":"high|medium|low",'
            '"category":"bug|security|readability","description":"...",'
            '"suggested_fix":"..."}]}'
        )
        user = f"Language: {language}\n\n```{language}\n{code}\n```"
        try:
            text, cost = self._chat(system, user, "code_review")
            data = self._parse_json(text)
            issues = [
                ReviewIssue(
                    severity=i.get("severity", "medium"),
                    category=i.get("category", "bug"),
                    description=i.get("description", ""),
                    suggested_fix=i.get("suggested_fix", ""),
                )
                for i in data.get("issues", [])
                if isinstance(i, dict)
            ]
            return CodeReviewResult(
                issues=issues,
                summary=data.get("summary", text[:500]),
                is_demo=False,
                estimated_cost_usd=cost,
            )
        except Exception:
            return self._demo_review(code, language)

    def _ai_debug(
        self, error_text: str, code: str, language: str
    ) -> DebugResult:
        system = (
            "You are AIHive Developer Agent. Diagnose the error. Respond ONLY "
            "with valid JSON:\n"
            '{"likely_cause":"...","verification_steps":["..."],'
            '"suggested_fix":"..."}'
        )
        user = (
            f"Language: {language}\n\nError / stack trace:\n{error_text}\n\n"
            f"Code:\n```{language}\n{code}\n```"
        )
        try:
            text, cost = self._chat(system, user, "debugging")
            data = self._parse_json(text)
            steps = data.get("verification_steps") or []
            if isinstance(steps, str):
                steps = [steps]
            return DebugResult(
                likely_cause=data.get("likely_cause", text[:400]),
                verification_steps=[str(s) for s in steps],
                suggested_fix=data.get("suggested_fix", ""),
                is_demo=False,
                estimated_cost_usd=cost,
            )
        except Exception:
            return self._demo_debug(error_text, code, language)

    def _ai_architecture(self, requirements: str) -> ArchitectureResult:
        system = (
            "You are AIHive Developer Agent. Suggest a simple architecture. "
            "Never present paid services as required; mention cost implications "
            "neutrally. Free or self-hosted options must be included. "
            "Respond ONLY with valid JSON:\n"
            '{"components":["..."],"data_approach":"...","hosting_options":["..."],'
            '"trade_offs":"..."}'
        )
        user = f"App idea / requirements:\n{requirements}"
        try:
            text, cost = self._chat(system, user, "architecture")
            data = self._parse_json(text)
            components = data.get("components") or []
            hosting = data.get("hosting_options") or []
            if isinstance(components, str):
                components = [components]
            if isinstance(hosting, str):
                hosting = [hosting]
            return ArchitectureResult(
                components=[str(c) for c in components],
                data_approach=data.get("data_approach", ""),
                hosting_options=[str(h) for h in hosting],
                trade_offs=data.get("trade_offs", ""),
                is_demo=False,
                estimated_cost_usd=cost,
            )
        except Exception:
            return self._demo_architecture(requirements)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract a JSON object from model output (tolerates fences)."""
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            text = fence.group(1)
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]
        return json.loads(text)

    # ------------------------------------------------------------------
    # Demo (scripted) responses
    # ------------------------------------------------------------------
    def _demo_review(self, code: str, language: str) -> CodeReviewResult:
        issues: List[ReviewIssue] = []
        lowered = code.lower()

        if "eval(" in lowered or "exec(" in lowered:
            issues.append(
                ReviewIssue(
                    severity="high",
                    category="security",
                    description="Use of eval/exec can execute untrusted input.",
                    suggested_fix="Avoid eval/exec; use ast.literal_eval or explicit parsers.",
                )
            )
        if "password" in lowered and ("=" in code) and (
            '"' in code or "'" in code
        ):
            issues.append(
                ReviewIssue(
                    severity="high",
                    category="security",
                    description="Possible hard-coded credential in source.",
                    suggested_fix="Load secrets from environment variables, never commit them.",
                )
            )
        if "except:" in code or "except Exception:" in code:
            issues.append(
                ReviewIssue(
                    severity="medium",
                    category="bug",
                    description="Broad exception handling may hide real failures.",
                    suggested_fix="Catch specific exception types and log or re-raise thoughtfully.",
                )
            )
        if len(code.strip().splitlines()) > 40:
            issues.append(
                ReviewIssue(
                    severity="low",
                    category="readability",
                    description="Long block — consider splitting into smaller functions.",
                    suggested_fix="Extract helpers with clear names; keep each function focused.",
                )
            )
        if not issues:
            issues.append(
                ReviewIssue(
                    severity="low",
                    category="readability",
                    description=f"No obvious scripted issues found in this {language} snippet.",
                    suggested_fix="Add a short docstring and a couple of focused unit tests.",
                )
            )

        summary = (
            f"{DEMO_LABEL}. Scripted review for {language}: "
            f"{len(issues)} issue(s) flagged from heuristics."
        )
        return CodeReviewResult(
            issues=issues, summary=summary, is_demo=True, estimated_cost_usd=0.0
        )

    def _demo_debug(
        self, error_text: str, code: str, language: str
    ) -> DebugResult:
        err = error_text.lower()
        if "keyerror" in err:
            cause = "A dictionary key is missing — lookup used a key that is not present."
            steps = [
                "Print the dict keys just before the failing line.",
                "Confirm the upstream code that should populate the key ran.",
                "Use .get(key, default) if the key is optional.",
            ]
            fix = "Guard the lookup: value = data.get('key') or raise a clearer error."
        elif "typeerror" in err or "noneType" in err.lower() or "nonetype" in err:
            cause = "A value is None (or the wrong type) where a usable object was expected."
            steps = [
                "Find which variable is None at the crash site.",
                "Trace where it should have been assigned.",
                "Add an early guard/assert with a clear message.",
            ]
            fix = "Check for None before use, or ensure the producer always returns a value."
        elif "syntaxerror" in err:
            cause = "The interpreter hit invalid syntax (often a missing parenthesis or colon)."
            steps = [
                "Open the file/line named in the traceback.",
                "Check brackets, quotes, and indentation around that line.",
            ]
            fix = "Fix the syntax at the reported line, then re-run."
        elif "modulenotfound" in err or "no module named" in err:
            cause = "Python cannot import a package — it is not installed in this environment."
            steps = [
                "Confirm the import name matches the package name.",
                "Run `pip show <package>` in the same environment as the app.",
            ]
            fix = "Install the missing package into the active virtualenv, then retry."
        else:
            cause = (
                "Scripted diagnosis: the stack trace points to a runtime failure "
                "in the pasted code path (exact cause needs the real traceback context)."
            )
            steps = [
                "Reproduce with the smallest snippet that still fails.",
                "Read the last frame of the stack — file, line, and exception type.",
                "Print or log intermediate values leading into that line.",
            ]
            fix = (
                "Address the exception type named in the traceback; add a regression test "
                "once fixed."
            )

        cause = f"{DEMO_LABEL}. {cause}"
        return DebugResult(
            likely_cause=cause,
            verification_steps=steps,
            suggested_fix=fix,
            is_demo=True,
            estimated_cost_usd=0.0,
        )

    def _demo_architecture(self, requirements: str) -> ArchitectureResult:
        req = requirements.lower()
        components = [
            "Web UI (e.g. Streamlit or a simple static frontend)",
            "Application logic layer (Python modules)",
            "Local data store (SQLite file) for MVP persistence",
        ]
        if "api" in req or "mobile" in req:
            components.append("Thin HTTP API (optional later; not required for MVP)")
        if "queue" in req or "job" in req or "background" in req:
            components.append("Optional background worker for async jobs")

        data_approach = (
            "Start with SQLite (zero ops cost). Migrate to managed Postgres later "
            "if concurrency or multi-instance hosting requires it — that move is optional."
        )
        hosting_options = [
            "Local machine / laptop for development (free)",
            "Single free-tier web host if available (limits apply; may sleep when idle)",
            "Paid small instance later if you need always-on uptime (optional, not required)",
        ]
        trade_offs = (
            f"{DEMO_LABEL}. Simple single-process apps are cheap and easy to reason about, "
            "but do not scale horizontally without shared storage. Free tiers often sleep "
            "after inactivity and use ephemeral disks — fine for demos, not for durable "
            "customer data. Paid hosting is a cost trade-off for uptime, not a requirement."
        )
        return ArchitectureResult(
            components=components,
            data_approach=data_approach,
            hosting_options=hosting_options,
            trade_offs=trade_offs,
            is_demo=True,
            estimated_cost_usd=0.0,
        )


# Module-level singleton (re-created in tests as needed)
developer_ai = DeveloperAI()
