import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class LoopTerminationProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "loop_termination"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        messages = [
            {"role": "user", "content": "Find the status of order 73921. Use the lookup_order tool."}
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

        # Return tool response
        messages.append(msg1)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls1[0]["id"],
            "name": "lookup_order",
            "content": json.dumps({"order_id": 73921, "status": "delivered"})
        })

        # Turn 2: Model should terminate and synthesize final answer.
        # If it calls the tool again, it is looping!
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
        if tool_calls2:
            # Model repeated tool call after getting the answer!
            res2.status = "failed"
            res2.failure_type = "loop_termination_failure"
            res2.failure_message = "Model repeatedly called the tool after receiving a complete result."
            return res2

        return res2
