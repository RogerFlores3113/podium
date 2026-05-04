"""Tool for saving a memory to the user's long-term memory store (MEM-01)."""
import logging
import uuid

from app.services.memory import persist_memories
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {"fact", "preference", "context"}


class MemorySaveTool(Tool):
    name = "memory_save"
    description = (
        "Save a fact, preference, or ongoing context about the user to long-term memory. "
        "Use this when the user shares personal information (their name, role, company), "
        "a recruiter-specific preference (preferred answer format, target industries, "
        "hiring criteria), or ongoing context (current open requisitions, budget constraints) "
        "that would be useful in future conversations. "
        "Do NOT save temporary task context — things they just asked about or one-time lookups."
    )
    parameters = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": (
                    "A concise, first-person statement about the user. "
                    'Start with "User ". Example: "User prefers bullet-point answers."'
                ),
            },
            "category": {
                "type": "string",
                "description": (
                    'Category of memory: "fact" (objective information), '
                    '"preference" (likes, dislikes, working style), '
                    'or "context" (ongoing situation or role context).'
                ),
                "enum": ["fact", "preference", "context"],
            },
        },
        "required": ["fact"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        fact = args["fact"].strip()
        category = args.get("category", "context")
        if category not in _VALID_CATEGORIES:
            # Normalize unrecognized LLM-supplied categories to avoid storage silently
            # bypassing retrieval filters (search_memories filters on fact/preference/context).
            category = "context"

        logger.info("Memory save: category=%s user=%s", category, ctx.user_id)

        await persist_memories(
            db=ctx.db,
            user_id=ctx.user_id,
            conversation_id=None,  # not available in ToolContext (D-09-01 Option B)
            memories=[{"category": category, "content": fact}],
        )

        return f"Memory saved: {fact}"


register_tool(MemorySaveTool())
