import logging

from tavily import AsyncTavilyClient
from tavily.errors import (
    InvalidAPIKeyError,
    UsageLimitExceededError,
    ForbiddenError,
    BadRequestError,
    MissingAPIKeyError,
    TimeoutError as TavilyTimeoutError,
)

from app.config import settings
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web for current information. Use this when the user asks "
        "about recent events, current facts, or anything that might have "
        "changed since your training data. Returns a list of relevant results "
        "with titles, URLs, and summaries."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific and concise.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (1-10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        query = args["query"]
        max_results = args.get("max_results", 5)

        logger.info(f"Web search: {query}")

        if not settings.tavily_api_key:
            return "Error: Web search is not configured."

        try:
            client = AsyncTavilyClient(api_key=settings.tavily_api_key)
            response = await client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",  # "basic" is faster/cheaper; "advanced" for deeper research
            )
        except (InvalidAPIKeyError, MissingAPIKeyError, ForbiddenError):
            logger.error("Tavily authentication/authorization error", exc_info=True)
            return "Web search is temporarily unavailable."
        except UsageLimitExceededError:
            logger.warning("Tavily usage limit reached", exc_info=True)
            return "Web search is temporarily unavailable (usage limit reached)."
        except TavilyTimeoutError:
            logger.warning("Tavily search timed out", exc_info=True)
            return "Web search timed out — please try again."
        except BadRequestError:
            logger.warning("Tavily bad request for query %r", query, exc_info=True)
            return "Web search could not process that query. Please try rephrasing."
        except Exception:
            logger.error("Unexpected web search error", exc_info=True)
            return "Web search is temporarily unavailable."

        results = response.get("results", [])
        if not results:
            return "No results found for that query."

        # Format results as a readable string for the LLM.
        # We include title, URL, and content snippet — the LLM will cite URLs
        # in its final answer.
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. {r['title']}\n"
                f"   URL: {r['url']}\n"
                f"   {r['content'][:800]}"  # Truncate to keep tokens reasonable
            )

        return "\n\n".join(formatted)


# Register on import
register_tool(WebSearchTool())