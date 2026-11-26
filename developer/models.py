"""
Data models for AIHive Developer Agent
Session-only history — nothing is written to SQLite.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import uuid


FeatureType = Literal["code_review", "debugging", "architecture"]


class DeveloperRequest(BaseModel):
    """A single developer-agent request within a browser session"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feature: FeatureType
    language: Optional[str] = None
    code: Optional[str] = None
    error_text: Optional[str] = None
    requirements: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewIssue(BaseModel):
    """One issue found during code review"""
    severity: Literal["high", "medium", "low"]
    category: Literal["bug", "security", "readability"]
    description: str
    suggested_fix: str


class CodeReviewResult(BaseModel):
    """Structured code review output"""
    issues: List[ReviewIssue] = Field(default_factory=list)
    summary: str = ""
    is_demo: bool = False
    estimated_cost_usd: float = 0.0


class DebugResult(BaseModel):
    """Structured debugging help output"""
    likely_cause: str
    verification_steps: List[str] = Field(default_factory=list)
    suggested_fix: str
    is_demo: bool = False
    estimated_cost_usd: float = 0.0


class ArchitectureResult(BaseModel):
    """Structured architecture guidance output"""
    components: List[str] = Field(default_factory=list)
    data_approach: str = ""
    hosting_options: List[str] = Field(default_factory=list)
    trade_offs: str = ""
    is_demo: bool = False
    estimated_cost_usd: float = 0.0


class HistoryEntry(BaseModel):
    """One history item kept in Streamlit session_state only"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feature: FeatureType
    title: str
    result_markdown: str
    estimated_cost_usd: float = 0.0
    is_demo: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
