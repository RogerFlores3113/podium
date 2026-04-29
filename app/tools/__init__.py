import logging

from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)

# Module-level registry. Tools register themselves on import.
_TOOLS: dict[str, Tool] = {}


def register_tool(tool: Tool) -> None:
    """Register a tool instance in the global registry."""
    if tool.name in _TOOLS:
        logger.warning(f"Tool {tool.name} already registered, overwriting")
    _TOOLS[tool.name] = tool
    logger.info(f"Registered tool: {tool.name}")


def get_tool(name: str) -> Tool:
    """Get a tool by name. Raises KeyError if not found."""
    if name not in _TOOLS:
        raise KeyError(f"Unknown tool: {name}")
    return _TOOLS[name]


def all_tools() -> list[Tool]:
    """Return all registered tools."""
    return list(_TOOLS.values())


def get_tool_schemas() -> list[dict]:
    """Return the OpenAI-format schema for all registered tools."""
    return [t.to_openai_schema() for t in all_tools()]


# Import tool modules to trigger their registration.
# Each module calls register_tool() at import time.
from app.tools import web_search  # noqa: E402, F401
from app.tools import document_search  # noqa: E402, F401
from app.tools import python_executor  # noqa: E402, F401
from app.tools import memory_search  # noqa: E402, F401
from app.tools import url_reader  # noqa: E402, F401
