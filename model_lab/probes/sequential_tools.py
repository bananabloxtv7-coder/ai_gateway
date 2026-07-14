import json
from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class SequentialToolsProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "sequential_tools"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        messages = [
            {"role": "user", "content": "Find the customer with email 'alice@example.com' and then retrieve their orders using the customer ID."}
        ]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "find_customer",
                    "description": "Find customer ID by email",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"}
                        },
                        "required": ["email"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_customer_orders",
                    "description": "Get list of orders for customer ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "integer"}
                        },
                        "required": ["customer_id"]
                    }
                }
            }
        ]

        # Turn 1: Find customer
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
        tool_calls = msg1.get("tool_calls", [])
        if not tool_calls or tool_calls[0]["function"]["name"] != "find_customer":
            res1.status = "failed"
            res1.failure_type = "wrong_tool_name"
            res1.failure_message = f"Expected find_customer tool call, got: {tool_calls}"
            return res1

        call1 = tool_calls[0]
        args1 = json.loads(call1["function"]["arguments"])
        if args1.get("email") != "alice@example.com":
            res1.status = "failed"
            res1.failure_type = "tool_arguments_schema_mismatch"
            res1.failure_message = f"Expected email='alice@example.com', got {args1.get('email')}"
            return res1

        # Turn 2: Retrieve orders using ID
        messages.append(msg1)
        messages.append({
            "role": "tool",
            "tool_call_id": call1["id"],
            "name": "find_customer",
            "content": json.dumps({"customer_id": 9988})
        })

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
        if not tool_calls2 or tool_calls2[0]["function"]["name"] != "get_customer_orders":
            res2.status = "failed"
            res2.failure_type = "wrong_tool_name"
            res2.failure_message = f"Expected get_customer_orders, got {tool_calls2}"
            return res2

        call2 = tool_calls2[0]
        args2 = json.loads(call2["function"]["arguments"])
        if args2.get("customer_id") != 9988:
            res2.status = "failed"
            res2.failure_type = "tool_arguments_schema_mismatch"
            res2.failure_message = f"Expected customer_id=9988, got {args2.get('customer_id')}"
            return res2

        # Turn 3: Final Synthesis
        messages.append(msg2)
        messages.append({
            "role": "tool",
            "tool_call_id": call2["id"],
            "name": "get_customer_orders",
            "content": json.dumps([{"order_id": 1122, "item": "laptop"}])
        })

        payload3 = {
            "model": route_id,
            "messages": messages,
            "tools": tools,
            "max_tokens": 150,
            "stream": False
        }
        res3 = await client.chat_completion(route_id, payload3)
        return res3
