import logging

from app.services.memory import search_memories
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)


class MemorySearchTool(Tool):
    name = "memory_search"
    description = (
        "Search what the user has shared in past conversations — recruiter preferences, "
        "candidate notes, company context, and ongoing hiring context. Use this when "
        "the user references something they told you before, asks you to recall a preference, "
        "or when past context from previous sessions would improve your answer. "
        "Returns memories ordered by relevance."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "What to search for. Use natural language describing "
                    "the topic or context you're trying to recall."
                ),
            },
            "top_k": {
                "type": "integer",
                "description": "Number of memories to return (1-10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        query = args["query"]
        top_k = args.get("top_k", 5)

        logger.info(f"Memory search: {query} (user={ctx.user_id})")

        memories = await search_memories(
            db=ctx.db,
            user_id=ctx.user_id,
            query=query,
            top_k=top_k,
        )

        if not memories:
            return "No relevant memories found."

        formatted = []
        for i, mem in enumerate(memories, 1):
            formatted.append(
                f"{i}. [{mem['category']}, relevance {mem['similarity']:.2f}]\n"
                f"   {mem['content']}"
            )

        return "\n\n".join(formatted)


register_tool(MemorySearchTool())
