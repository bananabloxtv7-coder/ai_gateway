import json
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
import time

from model_lab.schemas import Timing, ProbeResult


class SSEParser:
    """
    A reusable SSE parser that handles arbitrary byte boundaries,
    comments, blank lines, and [DONE] messages.
    """
    def __init__(self):
        self.buffer = ""

    def process_chunk(self, chunk: bytes) -> List[str]:
        """
        Process a chunk of bytes and return a list of JSON string events.
        """
        self.buffer += chunk.decode("utf-8", errors="replace")
        events = []
        
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            
            if not line or line.startswith(":"):
                continue
                
            if line.startswith("data: "):
                data = line[len("data: "):].strip()
                if data == "[DONE]":
                    continue
                events.append(data)
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    continue
                events.append(data)

        return events


def assemble_streaming_tool_calls(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Assembles fragmented streaming tool calls into complete tool calls.
    """
    tool_calls_dict = {}

    for event in events:
        choices = event.get("choices", [])
        if not choices:
            continue
            
        delta = choices[0].get("delta", {})
        delta_tool_calls = delta.get("tool_calls", [])
        
        for dtc in delta_tool_calls:
            idx = dtc.get("index")
            if idx is None:
                continue
                
            if idx not in tool_calls_dict:
                tool_calls_dict[idx] = {
                    "id": "",
                    "type": "function",
                    "function": {
                        "name": "",
                        "arguments": ""
                    }
                }
            
            if "id" in dtc and dtc["id"]:
                tool_calls_dict[idx]["id"] += dtc["id"]
                
            if "function" in dtc:
                func = dtc["function"]
                if "name" in func and func["name"]:
                    tool_calls_dict[idx]["function"]["name"] += func["name"]
                if "arguments" in func and func["arguments"]:
                    tool_calls_dict[idx]["function"]["arguments"] += func["arguments"]

    # Convert to list ordered by index
    sorted_indices = sorted(tool_calls_dict.keys())
    return [tool_calls_dict[i] for i in sorted_indices]


class GatewayClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport
        
    async def chat_completion(self, route_id: str, payload: Dict[str, Any]) -> ProbeResult:
        """
        Sends a normal or streaming chat completion request and returns a ProbeResult.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Youssef-Route": route_id
        }
        
        is_stream = payload.get("stream", False)
        
        # Ensure model is set if not
        if "model" not in payload:
            payload["model"] = route_id

        timing = Timing()
        t0 = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                if is_stream:
                    req = client.build_request("POST", url, headers=headers, json=payload)
                    resp = await client.send(req, stream=True)
                else:
                    resp = await client.post(url, headers=headers, json=payload)
                    
                timing.first_byte_ms = (time.time() - t0) * 1000
                
                request_id = resp.headers.get("X-Youssef-Request-Id")
                requested_route = resp.headers.get("X-Youssef-Requested-Model")
                resolved_route = resp.headers.get("X-Youssef-Resolved-Route")
                
                route_identity_matched = (resolved_route == route_id) if resolved_route else False

                if resp.status_code >= 400:
                    timing.total_ms = (time.time() - t0) * 1000
                    if is_stream:
                        body = await resp.aread()
                        await resp.aclose()
                        error_text = body.decode("utf-8", "ignore")
                    else:
                        error_text = resp.text
                    
                    # Ensure NO secrets are captured in the error text!
                    # Basic sanitization
                    if self.api_key in error_text:
                        error_text = error_text.replace(self.api_key, "[REDACTED]")

                    return ProbeResult(
                        status="error",
                        failure_type="http_error",
                        failure_message=f"HTTP {resp.status_code}: {error_text[:200]}",
                        http_status=resp.status_code,
                        request_id=request_id,
                        requested_route=requested_route,
                        resolved_route=resolved_route,
                        route_identity_matched=route_identity_matched,
                        timing=timing
                    )

                if is_stream:
                    parser = SSEParser()
                    events_json = []
                    
                    try:
                        async for chunk in resp.aiter_bytes():
                            for event_data in parser.process_chunk(chunk):
                                try:
                                    events_json.append(json.loads(event_data))
                                except json.JSONDecodeError:
                                    pass # Malformed event, ignore or log securely
                    finally:
                        await resp.aclose()
                        
                    timing.total_ms = (time.time() - t0) * 1000
                    
                    # Finalize parsing stream content
                    content = ""
                    for e in events_json:
                        choices = e.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                content += delta["content"]
                    
                    tool_calls = assemble_streaming_tool_calls(events_json)
                    
                    msg = {"role": "assistant"}
                    if content:
                        msg["content"] = content
                    if tool_calls:
                        msg["tool_calls"] = tool_calls

                    raw_response = {
                        "choices": [
                            {"message": msg}
                        ]
                    }
                    
                    return ProbeResult(
                        status="passed",
                        http_status=resp.status_code,
                        request_id=request_id,
                        requested_route=requested_route,
                        resolved_route=resolved_route,
                        route_identity_matched=route_identity_matched,
                        valid_openai_shape=True, # Simplified assumption for now
                        timing=timing,
                        raw_response=raw_response
                    )
                else:
                    try:
                        data = resp.json()
                        timing.total_ms = (time.time() - t0) * 1000
                        
                        return ProbeResult(
                            status="passed",
                            http_status=resp.status_code,
                            request_id=request_id,
                            requested_route=requested_route,
                            resolved_route=resolved_route,
                            route_identity_matched=route_identity_matched,
                            valid_openai_shape=isinstance(data, dict) and "choices" in data,
                            timing=timing,
                            raw_response=data
                        )
                    except json.JSONDecodeError:
                        timing.total_ms = (time.time() - t0) * 1000
                        return ProbeResult(
                            status="error",
                            failure_type="invalid_openai_response",
                            failure_message="Response was not valid JSON",
                            http_status=resp.status_code,
                            request_id=request_id,
                            requested_route=requested_route,
                            resolved_route=resolved_route,
                            route_identity_matched=route_identity_matched,
                            timing=timing
                        )
                        
        except httpx.TimeoutException as exc:
            timing.total_ms = (time.time() - t0) * 1000
            return ProbeResult(
                status="error",
                failure_type="timeout",
                failure_message=str(exc),
                timing=timing
            )
        except httpx.RequestError as exc:
            timing.total_ms = (time.time() - t0) * 1000
            return ProbeResult(
                status="error",
                failure_type="connection_error",
                failure_message=str(exc),
                timing=timing
            )
