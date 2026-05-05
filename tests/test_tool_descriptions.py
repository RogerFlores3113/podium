"""Tests for recruiter-domain tool descriptions (AGT-01)."""


def test_document_search_description_mentions_recruiter_document_types():
    """document_search description must mention recruiter document types like resumes or job descriptions (AGT-01)."""
    from app.tools.document_search import DocumentSearchTool
    tool = DocumentSearchTool()
    desc = tool.description.lower()
    assert any(kw in desc for kw in ("resume", "job description", "offer letter", "candidate")), (
        "document_search description must mention recruiter-domain document types "
        "(resume, job description, offer letter, or candidate)"
    )


def test_memory_search_description_mentions_recruiter_context():
    """memory_search description must mention recruiter-relevant context (AGT-01)."""
    from app.tools.memory_search import MemorySearchTool
    tool = MemorySearchTool()
    desc = tool.description.lower()
    assert any(kw in desc for kw in ("candidate", "preference", "recruiter", "past context", "company")), (
        "memory_search description must mention recruiter context "
        "(candidate, preference, recruiter, past context, or company)"
    )


def test_web_search_description_mentions_recruiter_searches():
    """web_search description must mention recruiter-relevant search topics (AGT-01)."""
    from app.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    desc = tool.description.lower()
    assert any(kw in desc for kw in ("company", "salary", "job market", "hiring", "candidate")), (
        "web_search description must mention recruiter-relevant search topics "
        "(company, salary, job market, hiring, or candidate)"
    )
