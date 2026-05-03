from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    """
    Context passed to every tool execution.

    Tools that need access to the user's data (like document_search)
    use this to scope their queries. Tools that don't care about the user
    (like web_search) simply ignore it.
    """
    user_id: str
    db: AsyncSession
    is_guest: bool = False


class Tool(ABC):
    """
    Base class for all tools the agent can invoke.

    Subclasses define:
      - name: the identifier the LLM uses to call this tool
      - description: a human-readable description the LLM sees in the tool list
      - parameters: a JSON Schema describing the arguments
      - execute(): the actual implementation

    The LLM sees `name`, `description`, and `parameters` when deciding whether
    to invoke a tool. Make the description specific — vague descriptions lead
    to the LLM calling tools incorrectly or not at all.
    """

    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def execute(self, ctx: ToolContext, args: dict[str, Any]) -> str:
        """
        Execute the tool and return a string result.

        The return value is what the LLM sees. Keep it concise but informative.
        If you return JSON, the LLM will parse it. If you return natural language,
        the LLM will summarize it.

        Raise an exception on hard failures. The agent loop catches exceptions
        and reports them to the LLM as tool errors, which the LLM can then
        react to (usually by trying a different approach).
        """
        pass

    def to_openai_schema(self) -> dict:
        """
        Convert this tool to the format litellm/OpenAI expects.

        This is the standard "tools" parameter format that all major providers
        (OpenAI, Anthropic via litellm, Ollama with compatible models) accept.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }