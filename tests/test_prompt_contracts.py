"""Structural contract tests for the two live LLM prompts (PROMPT-01).

These assert against the REAL prompt constants so future edits cannot silently
drop the invariants the memory taxonomy and agent loop-prevention rely on.
"""

from app.services.agent import AGENT_SYSTEM_PROMPT
from app.services.memory import EXTRACTION_PROMPT


def test_agent_prompt_keeps_the_verbatim_synthesis_rule():
    assert "Never end your turn with only tool calls" in AGENT_SYSTEM_PROMPT


def test_agent_prompt_keeps_the_loop_prevention_guidance():
    assert "Avoid search loops" in AGENT_SYSTEM_PROMPT


def test_agent_prompt_lists_all_six_registered_tools():
    for tool in (
        "document_search",
        "web_search",
        "url_reader",
        "python_executor",
        "memory_search",
        "memory_save",
    ):
        assert tool in AGENT_SYSTEM_PROMPT


def test_extraction_prompt_instructs_json_array_output():
    assert "JSON" in EXTRACTION_PROMPT
    assert "array" in EXTRACTION_PROMPT


def test_extraction_prompt_defines_all_three_categories():
    for category in ("fact", "preference", "context"):
        assert category in EXTRACTION_PROMPT


def test_extraction_prompt_retains_the_length_and_no_inference_rules():
    assert "150" in EXTRACTION_PROMPT
    assert "Do not infer" in EXTRACTION_PROMPT
