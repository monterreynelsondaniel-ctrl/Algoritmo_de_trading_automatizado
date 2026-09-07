"""Official OpenAI Responses API adapter, imported lazily for offline use."""

import json
import time


class OpenAIResponsesClient:
    def __init__(self, api_key, timeout_seconds=30):
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("Install the 'openai' package to use live AI mode") from error
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def structured_response(self, *, model, system_prompt, payload, schema, reasoning_effort):
        started = time.monotonic()
        response = self._client.responses.create(
            model=model,
            reasoning={"effort": reasoning_effort},
            instructions=system_prompt,
            input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            text={"format": schema},
            store=False,
        )
        if not response.output_text:
            raise ValueError("OpenAI response did not contain structured output")
        usage = getattr(response, "usage", None)
        usage_data = usage.to_dict() if hasattr(usage, "to_dict") else None
        return json.loads(response.output_text), {
            "response_id": getattr(response, "id", None),
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "usage": usage_data,
        }
