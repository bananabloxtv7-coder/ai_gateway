import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class StreamingToolCallProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "streaming_tool_call"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        payload = {
            "model": route_id,
            "messages": [
                {"role": "user", "content": "Find the current status of order 73921. Use the available tool."}
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
            "max_tokens": 150,
            "stream": True
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
        if "id" not in call or not call["id"]:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "missing_tool_call_id"
            return base_eval
            
        func = call.get("function", {})
        if func.get("name") != "lookup_order":
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "wrong_tool_name"
            base_eval["failure_message"] = f"Expected lookup_order but got {func.get('name')}"
            return base_eval
            
        try:
            args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "invalid_tool_arguments_json"
            base_eval["failure_message"] = "Fragment assembly failed to produce valid JSON"
            return base_eval
            
        if args.get("order_id") != 73921:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "tool_arguments_schema_mismatch"
            return base_eval
            
        return base_eval
