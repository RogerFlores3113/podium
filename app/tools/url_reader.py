import logging

import httpx

from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)

JINA_BASE = "https://r.jina.ai"
MAX_CHARS = 8000  # ~2k tokens — enough for most articles


class UrlReaderTool(Tool):
    name = "url_reader"
    description = (
        "Fetch and read the content of any public URL. Returns clean, readable "
        "text extracted from the page (markdown format). Use this when the user "
        "shares a link and wants you to read it, or when a web search result "
        "needs deeper reading."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to fetch (must include https://).",
            },
        },
        "required": ["url"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        url = args["url"].strip()
        logger.info(f"URL reader: {url}")

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(
                f"{JINA_BASE}/{url}",
                headers={"Accept": "text/plain"},
            )
            response.raise_for_status()

        text = response.text.strip()
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n\n[content truncated]"

        return text or "No readable content found at that URL."


register_tool(UrlReaderTool())
