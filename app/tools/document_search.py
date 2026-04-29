import logging

from app.services.retrieval import retrieve_relevant_chunks
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)


class DocumentSearchTool(Tool):
    name = "document_search"
    description = (
        "Search the user's personal document library for relevant content. "
        "Use this when the user asks about topics that might be covered in "
        "their uploaded documents. Returns the most relevant passages with "
        "similarity scores."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Use natural language.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (1-10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        query = args["query"]
        top_k = args.get("top_k", 5)

        logger.info(f"Document search: {query} (user={ctx.user_id})")

        chunks = await retrieve_relevant_chunks(
            db=ctx.db,
            query=query,
            user_id=ctx.user_id,
            top_k=top_k,
            include_seed=ctx.is_guest,
        )

        if not chunks:
            return "No relevant documents found in your library."

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            formatted.append(
                f"[Result {i}, relevance {chunk['similarity']:.2f}]\n"
                f"{chunk['content']}"
            )

        return "\n\n---\n\n".join(formatted)


register_tool(DocumentSearchTool())