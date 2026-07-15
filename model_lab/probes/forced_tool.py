import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class ForcedToolChoiceProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "forced_tool_choice"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        payload = {
            "model": route_id,
            "messages": [
                {"role": "user", "content": "Tell me about order 73921."}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup_order",
                        "description": "Find order status",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "order_id": {"type": "integer"}
                            },
                            "required": ["order_id"]
                        }
                    }
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "lookup_order"}},
            "max_tokens": 150,
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
            
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        
        if not tool_calls:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "missing_tool_call"
            return base_eval
            
        call = tool_calls[0]
        func = call.get("function", {})
        if func.get("name") != "lookup_order":
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "wrong_tool_name"
            return base_eval
            
        return base_eval
