from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class SystemMessageProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "system_message"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        payload = {
            "model": route_id,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that must answer only with the word: EMOJI."},
                {"role": "user", "content": "Hello!"}
            ],
            "max_tokens": 50,
            "stream": False
        }
        return await client.chat_completion(route_id, payload)

    def evaluate(self, result: ProbeResult) -> dict:
        base_eval = super().evaluate(result)
        if base_eval["status"] != "passed":
            return base_eval
            
        choices = result.raw_response.get("choices", [])
        if not choices:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "invalid_openai_response"
            return base_eval
            
        content = choices[0].get("message", {}).get("content", "").strip()
        if "EMOJI" not in content.upper():
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "system_instruction_ignored"
            base_eval["failure_message"] = f"Expected response to contain EMOJI, got: {content}"
            
        return base_eval
