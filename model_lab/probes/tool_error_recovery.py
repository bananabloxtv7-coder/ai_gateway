import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class ToolErrorRecoveryProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "tool_error_recovery"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        messages = [
            {"role": "user", "content": "Find status of order 73921. If the service is temporarily unavailable, retry the call once. If it persists, report the failure."}
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

        # Turn 1
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

        msg1 = res1.raw_response["choices"][0]["message"]
        tool_calls1 = msg1.get("tool_calls", [])
        if not tool_calls1:
            res1.status = "failed"
            res1.failure_type = "missing_tool_call"
            return res1

        # Return a temporary error
        messages.append(msg1)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls1[0]["id"],
            "name": "lookup_order",
            "content": json.dumps({"error": {"code": "temporary_failure", "message": "Service temporarily unavailable"}})
        })

        # Turn 2: Model should retry
        payload2 = {
            "model": route_id,
            "messages": messages,
            "tools": tools,
            "max_tokens": 150,
            "stream": False
        }
        res2 = await client.chat_completion(route_id, payload2)
        if res2.status != "passed":
            return res2

        msg2 = res2.raw_response["choices"][0]["message"]
        tool_calls2 = msg2.get("tool_calls", [])
        if not tool_calls2:
            res2.status = "failed"
            res2.failure_type = "tool_error_recovery_failure"
            res2.failure_message = "Model did not retry the tool after failure"
            return res2

        # Return success on second try
        messages.append(msg2)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls2[0]["id"],
            "name": "lookup_order",
            "content": json.dumps({"order_id": 73921, "status": "processing"})
        })

        # Turn 3: Final response
        payload3 = {
            "model": route_id,
            "messages": messages,
            "tools": tools,
            "max_tokens": 150,
            "stream": False
        }
        return await client.chat_completion(route_id, payload3)
