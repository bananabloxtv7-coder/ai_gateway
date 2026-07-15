import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class UnknownToolResistanceProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "unknown_tool_resistance"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        payload = {
            "model": route_id,
            "messages": [
                {"role": "user", "content": "Please translate the text using the 'translate_document' tool."}
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
            "max_tokens": 100,
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
        
        if tool_calls:
            # If the model tried to call 'translate_document' which was NOT exposed:
            for call in tool_calls:
                name = call.get("function", {}).get("name")
                if name == "translate_document" or name not in ["lookup_order"]:
                    base_eval["status"] = "failed"
                    base_eval["failure_type"] = "unexpected_tool_call"
                    base_eval["failure_message"] = f"Model fabricated nonexistent tool call: {name}"
                    return base_eval
                    
        return base_eval
