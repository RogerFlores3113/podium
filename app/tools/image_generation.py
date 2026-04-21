import logging

from openai import AsyncOpenAI

from app.config import settings
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)


class ImageGenerationTool(Tool):
    name = "image_generation"
    description = (
        "Generate an image from a text description using DALL-E 3. Returns a URL "
        "to the generated image. Use this when the user explicitly asks to create, "
        "draw, or generate an image."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed description of the image to generate.",
            },
            "size": {
                "type": "string",
                "enum": ["1024x1024", "1792x1024", "1024x1792"],
                "description": "Image dimensions. Default is 1024x1024.",
                "default": "1024x1024",
            },
        },
        "required": ["prompt"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        prompt = args["prompt"].strip()
        size = args.get("size", "1024x1024")
        logger.info(f"Image generation: {prompt[:80]}")

        api_key = settings.openai_api_key
        if not api_key:
            return "Error: Image generation is not configured (missing OpenAI API key)."

        client = AsyncOpenAI(api_key=api_key)
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,  # type: ignore[arg-type]
            n=1,
        )

        url = response.data[0].url
        if not url:
            return "Image generation failed: no URL returned."

        return url


register_tool(ImageGenerationTool())
