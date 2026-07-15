import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult, Timing

class ToolResultFollowupProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "tool_result_followup"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        messages = [
            {"role": "user", "content": "Find the current status of order 73921. Use the available tool. Do not guess the order status."}
        ]
        tools = [
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
        ]
        
        # Turn 1: Request tool call
        payload = {
            "model": route_id,
            "messages": messages,
            "tools": tools,
            "max_tokens": 150,
            "stream": False
        }
        res1 = await client.chat_completion(route_id, payload)
        if res1.status != "passed":
            return res1
            
        choices = res1.raw_response.get("choices", [])
        if not choices:
            res1.status = "error"
            res1.failure_type = "invalid_openai_response"
            return res1
            
        msg1 = choices[0].get("message", {})
        tool_calls = msg1.get("tool_calls", [])
        if not tool_calls:
            res1.status = "failed"
            res1.failure_type = "missing_tool_call"
            return res1
            
        call = tool_calls[0]
        call_id = call.get("id")
        
        # Turn 2: Follow up with tool response
        messages.append(msg1)
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": "lookup_order",
            "content": json.dumps({"order_id": 73921, "status": "processing"})
        })
        
        payload2 = {
            "model": route_id,
            "messages": messages,
            "tools": tools,
            "max_tokens": 150,
            "stream": False
        }
        res2 = await client.chat_completion(route_id, payload2)
        
        # Combine timing and metadata
        if res2.status == "passed":
            res2.timing.first_byte_ms = res1.timing.first_byte_ms
            res2.timing.total_ms += res1.timing.total_ms
            
        return res2

    def evaluate(self, result: ProbeResult) -> dict:
        base_eval = super().evaluate(result)
        if base_eval["status"] != "passed":
            return base_eval
            
        choices = result.raw_response.get("choices", [])
        if not choices:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "invalid_openai_response"
            return base_eval
            
        content = choices[0].get("message", {}).get("content", "").lower()
        if "processing" not in content:
            base_eval["status"] = "failed"
            base_eval["failure_type"] = "tool_result_not_understood"
            base_eval["failure_message"] = f"Expected model to understand status 'processing', got response: {content}"
            
        return base_eval
