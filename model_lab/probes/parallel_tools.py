import json
from typing import Any, List
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class ParallelToolsProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "parallel_tools"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        messages = [
            {"role": "user", "content": "Check the status of the following three services: api, database, and queue. Call the status tool for each service."}
        ]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_service_status",
                    "description": "Get status of a specific service",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {"type": "string"}
                        },
                        "required": ["service_name"]
                    }
                }
            }
        ]
        
        target_services = {"api", "database", "queue"}
        called_services = set()
        parallel_tools = False
        sequential_fallback = False
        
        # Loop for up to 3 turns to allow sequential fallback
        for turn in range(3):
            payload = {
                "model": route_id,
                "messages": messages,
                "tools": tools,
                "max_tokens": 150,
                "stream": False
            }
            res = await client.chat_completion(route_id, payload)
            if res.status != "passed":
                return res
                
            msg = res.raw_response["choices"][0]["message"]
            tool_calls = msg.get("tool_calls", [])
            
            if not tool_calls:
                # If we haven't checked all services, it's a failure
                if len(called_services) < len(target_services):
                    res.status = "failed"
                    res.failure_type = "parallel_call_failure"
                    res.failure_message = f"Model stopped before checking all services. Checked: {called_services}"
                return res
                
            if len(tool_calls) > 1:
                if turn == 0:
                    parallel_tools = True
                else:
                    sequential_fallback = True
            elif len(tool_calls) == 1:
                sequential_fallback = True
                
            messages.append(msg)
            
            # Form tool responses
            for call in tool_calls:
                call_id = call.get("id")
                func_name = call.get("function", {}).get("name")
                args = json.loads(call.get("function", {}).get("arguments", "{}"))
                service = args.get("service_name")
                
                if func_name == "get_service_status" and service in target_services:
                    called_services.add(service)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": func_name,
                        "content": json.dumps({"service": service, "status": "online"})
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": func_name or "get_service_status",
                        "content": json.dumps({"error": "invalid service"})
                    })

            if len(called_services) == len(target_services):
                # Final synthesis turn
                payload_final = {
                    "model": route_id,
                    "messages": messages,
                    "tools": tools,
                    "max_tokens": 150,
                    "stream": False
                }
                res_final = await client.chat_completion(route_id, payload_final)
                res_final.tool_call_observations = {
                    "parallel_tools": parallel_tools,
                    "sequential_fallback": sequential_fallback
                }
                return res_final
                
        res.status = "failed"
        res.failure_type = "parallel_call_failure"
        res.failure_message = f"Timeout/Max turns reached. Checked: {called_services}"
        return res
