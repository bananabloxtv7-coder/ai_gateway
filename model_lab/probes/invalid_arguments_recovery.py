import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class InvalidArgumentsRecoveryProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "invalid_arguments_recovery"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        messages = [
            {"role": "user", "content": "Find status of order 73921."}
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

        # Return invalid arguments feedback
        messages.append(msg1)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls1[0]["id"],
            "name": "lookup_order",
            "content": json.dumps({"error": "Invalid arguments. 'order_id' must be an integer, you provided a string."})
        })

        # Turn 2: Model recovers and calls it again
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
            res2.failure_type = "invalid_arguments_recovery_failure"
            res2.failure_message = "Model did not correct arguments after receiving validation error"
            return res2

        # Verify arguments are valid now (e.g. integer)
        try:
            args = json.loads(tool_calls2[0]["function"]["arguments"])
            if not isinstance(args.get("order_id"), int):
                res2.status = "failed"
                res2.failure_type = "invalid_arguments_recovery_failure"
                res2.failure_message = f"Model arguments still invalid: {args}"
                return res2
        except Exception as e:
            res2.status = "failed"
            res2.failure_type = "invalid_arguments_recovery_failure"
            res2.failure_message = f"Failed to parse model arguments: {e}"
            return res2

        # Return success
        messages.append(msg2)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls2[0]["id"],
            "name": "lookup_order",
            "content": json.dumps({"order_id": 73921, "status": "processing"})
        })

        # Turn 3: Final Response
        payload3 = {
            "model": route_id,
            "messages": messages,
            "tools": tools,
            "max_tokens": 150,
            "stream": False
        }
        return await client.chat_completion(route_id, payload3)
