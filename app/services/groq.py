import json
import re
from openai import AsyncOpenAI, BadRequestError
from app.config import Settings


def _parse_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            candidate = text[start : end + 1]
            json.loads(candidate)
            return candidate
    raise ValueError(f"Could not parse JSON: {text[:300]}")


class GroqClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: AsyncOpenAI | None = None

    async def complete(self, system: str, user: str) -> str:
        if not self._client:
            self._client = AsyncOpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.groq_base_url,
            )
        for use_json_mode in (True, False):
            try:
                kwargs: dict = {
                    "model": self.settings.groq_model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": 0.1,
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = await self._client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content
                if not content:
                    raise ValueError("Empty Groq response")
                return _parse_json(content)
            except BadRequestError as e:
                if use_json_mode and "json" in str(e).lower():
                    continue
                raise
            except (json.JSONDecodeError, ValueError):
                if use_json_mode:
                    continue
                raise
        raise ValueError("Failed to get JSON response")
