"""
Unit tests for Tutor session summary view-model.
No API key required — uses demo-mode TutorAI only.
"""
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tutor.lesson_page import build_session_summary_view
from tutor.models import StudySession
from tutor.tutor_ai import TutorAI


@pytest.fixture
def demo_tutor():
    tutor = TutorAI()
    # Force demo path even if an API key exists in the environment
    tutor.is_demo = True
    tutor.client = None
    return tutor


def test_summary_view_includes_counts_and_practice_questions(demo_tutor):
    """Completed session with mixed answers exposes both counts and practice questions."""
    session = StudySession(user_id="summary_user", topic="Photosynthesis", level="Beginner")
    session.add_message("assistant", "What is photosynthesis?", is_question=True)

    is_correct_1, _ = demo_tutor.process_answer(session, "idk")
    assert is_correct_1 is False
    session.questions_answered_incorrectly += 1

    is_correct_2, _ = demo_tutor.process_answer(
        session,
        "Plants use sunlight, water, and carbon dioxide to make food through photosynthesis.",
    )
    assert is_correct_2 is True
    session.questions_answered_correctly += 1
    session.chunks_completed = 2

    summary, questions = demo_tutor.generate_summary(session)
    session.mark_completed(summary, questions)

    view = build_session_summary_view(session)

    assert view["questions_correct"] >= 1
    assert view["questions_incorrect"] >= 1
    assert view["questions_correct"] == session.questions_answered_correctly
    assert view["questions_incorrect"] == session.questions_answered_incorrectly
    assert len(view["practice_questions"]) == 3
    assert all(isinstance(q, str) and len(q) > 0 for q in view["practice_questions"])
    assert view["summary_text"]
    assert "photosynthesis" in view["summary_text"].lower() or "Photosynthesis" in view["topic"]


def test_summary_view_defaults_for_empty_session():
    session = StudySession(user_id="empty", topic="Algebra", level="Beginner")
    view = build_session_summary_view(session)
    assert view["questions_correct"] == 0
    assert view["questions_incorrect"] == 0
    assert view["practice_questions"] == []
    assert view["summary_text"] == ""
    assert view["topic"] == "Algebra"
