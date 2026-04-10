import logging

from e2b_code_interpreter import AsyncSandbox

from app.config import settings
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)


class PythonExecutorTool(Tool):
    name = "python_executor"
    description = (
        "Execute Python code in a sandboxed environment. Use this for "
        "calculations, data analysis, plotting, or any task that benefits "
        "from code execution. The sandbox has numpy, pandas, matplotlib, "
        "scipy, and other standard data science libraries pre-installed. "
        "Returns stdout, stderr, and any errors. Print results with print() "
        "to capture them."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code to execute. Must be valid Python. "
                    "Use print() to output results."
                ),
            },
        },
        "required": ["code"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        code = args["code"]
        logger.info(f"Python executor: {len(code)} chars (user={ctx.user_id})")

        if not settings.e2b_api_key:
            return "Error: Python executor is not configured."

        # Create an ephemeral sandbox, run code, tear down.
        # For a future optimization, we could keep sandboxes alive across
        # tool calls within the same conversation — but that requires session
        # tracking and cleanup logic. Ephemeral is simpler and correct.
        sandbox = None
        try:
            sandbox = await AsyncSandbox.create(api_key=settings.e2b_api_key)
            execution = await sandbox.run_code(code)

            # Build a response that includes stdout, stderr, and any error.
            # The LLM needs all of this to understand what happened.
            parts = []

            if execution.logs.stdout:
                stdout_str = "".join(execution.logs.stdout)
                parts.append(f"stdout:\n{stdout_str}")

            if execution.logs.stderr:
                stderr_str = "".join(execution.logs.stderr)
                parts.append(f"stderr:\n{stderr_str}")

            if execution.error:
                parts.append(
                    f"error:\n{execution.error.name}: {execution.error.value}"
                )

            if not parts:
                parts.append("(no output)")

            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"Python executor failed: {e}", exc_info=True)
            return f"Error: Failed to execute code: {e}"
        finally:
            if sandbox:
                try:
                    await sandbox.kill()
                except Exception as e:
                    logger.warning(f"Failed to kill sandbox: {e}")


register_tool(PythonExecutorTool())