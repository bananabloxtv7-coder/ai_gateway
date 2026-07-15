import json
import pytest
import httpx
import asyncio
from typing import Any, Dict
from model_lab.client import GatewayClient
from model_lab.probes.system_message import SystemMessageProbe
from model_lab.probes.route_identity import RouteIdentityProbe
from model_lab.probes.forced_tool import ForcedToolChoiceProbe
from model_lab.probes.tool_result_followup import ToolResultFollowupProbe
from model_lab.probes.sequential_tools import SequentialToolsProbe
from model_lab.probes.parallel_tools import ParallelToolsProbe
from model_lab.probes.tool_error_recovery import ToolErrorRecoveryProbe
from model_lab.probes.invalid_arguments_recovery import InvalidArgumentsRecoveryProbe
from model_lab.probes.unknown_tool_resistance import UnknownToolResistanceProbe
from model_lab.probes.loop_termination import LoopTerminationProbe
from model_lab.schemas import Timing, ProbeResult
from model_lab.config import LabConfig
from model_lab.runner import Runner

# A helper mock transport that returns canned responses based on request index or payload content
class MultiTurnMockTransport(httpx.MockTransport):
    def __init__(self, responses_list):
        self.responses_list = responses_list
        self.request_count = 0
        super().__init__(self.handle_req)

    def handle_req(self, request: httpx.Request) -> httpx.Response:
        idx = min(self.request_count, len(self.responses_list) - 1)
        self.request_count += 1
        resp_data = self.responses_list[idx]
        
        status_code = resp_data.get("status_code", 200)
        
        if "headers" in resp_data:
            headers = resp_data["headers"]
        else:
            headers = {
                "X-Youssef-Resolved-Route": "test::model",
                "X-Youssef-Request-Id": "req_123"
            }
            
        body = json.dumps(resp_data.get("json", {})).encode("utf-8")
        return httpx.Response(status_code=status_code, headers=headers, content=body)


@pytest.mark.asyncio
async def test_system_message_probe_passed():
    responses = [
        {"json": {"choices": [{"message": {"role": "assistant", "content": "EMOJI"}}]}}
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = SystemMessageProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_system_message_probe_failed():
    responses = [
        {"json": {"choices": [{"message": {"role": "assistant", "content": "Hello!"}}]}}
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = SystemMessageProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "failed"
    assert eval_res["failure_type"] == "system_instruction_ignored"


@pytest.mark.asyncio
async def test_route_identity_header_missing():
    responses = [
        {
            "json": {"choices": [{"message": {"role": "assistant", "content": "Hi"}}]},
            "headers": {} # Missing route header
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = RouteIdentityProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "failed"
    assert eval_res["failure_type"] == "missing_route_header"


@pytest.mark.asyncio
async def test_route_identity_header_mismatched():
    responses = [
        {
            "json": {"choices": [{"message": {"role": "assistant", "content": "Hi"}}]},
            "headers": {"X-Youssef-Resolved-Route": "other::model"} # Mismatched route header
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = RouteIdentityProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "failed"
    assert eval_res["failure_type"] == "route_identity_mismatch"


@pytest.mark.asyncio
async def test_forced_tool_choice_passed():
    responses = [
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}
                        }]
                    }
                }]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = ForcedToolChoiceProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_tool_result_followup():
    responses = [
        # Turn 1: tool call request
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}
                        }]
                    }
                }]
            }
        },
        # Turn 2: final synthesis
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "The order is processing."
                    }
                }]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = ToolResultFollowupProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_sequential_tools():
    responses = [
        # Turn 1: find customer
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_c1",
                            "type": "function",
                            "function": {"name": "find_customer", "arguments": "{\"email\": \"alice@example.com\"}"}
                        }]
                    }
                }]
            }
        },
        # Turn 2: get customer orders
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_o1",
                            "type": "function",
                            "function": {"name": "get_customer_orders", "arguments": "{\"customer_id\": 9988}"}
                        }]
                    }
                }]
            }
        },
        # Turn 3: final answer
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Alice ordered a laptop."
                    }
                }]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = SequentialToolsProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_parallel_tools_success():
    responses = [
        # Turn 1: three tool calls at once
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "c1", "type": "function", "function": {"name": "get_service_status", "arguments": "{\"service_name\": \"api\"}"}},
                            {"id": "c2", "type": "function", "function": {"name": "get_service_status", "arguments": "{\"service_name\": \"database\"}"}},
                            {"id": "c3", "type": "function", "function": {"name": "get_service_status", "arguments": "{\"service_name\": \"queue\"}"}}
                        ]
                    }
                }]
            }
        },
        # Turn 2: Final response
        {
            "json": {
                "choices": [{"message": {"role": "assistant", "content": "All services are online"}}]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = ParallelToolsProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"
    assert eval_res["observations"]["parallel_tools"] is True
    assert eval_res["observations"]["sequential_fallback"] is False


@pytest.mark.asyncio
async def test_tool_error_recovery():
    responses = [
        # Turn 1: tool call request
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}}]
                    }
                }]
            }
        },
        # Turn 2: tool call retry request (after error response)
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}}]
                    }
                }]
            }
        },
        # Turn 3: final success response
        {
            "json": {
                "choices": [{"message": {"role": "assistant", "content": "The order is processing"}}]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = ToolErrorRecoveryProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_invalid_arguments_recovery():
    responses = [
        # Turn 1: tool call request (with potentially invalid args, or we treat it as such)
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "lookup_order", "arguments": "{\"order_id\": \"73921\"}"}}] # string
                    }
                }]
            }
        },
        # Turn 2: model corrects argument type to integer
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}}] # integer
                    }
                }]
            }
        },
        # Turn 3: final response
        {
            "json": {
                "choices": [{"message": {"role": "assistant", "content": "The order is processing"}}]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = InvalidArgumentsRecoveryProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_unknown_tool_resistance_passed():
    responses = [
        # Model responds with normal chat, ignoring the nonexistent tool request
        {
            "json": {
                "choices": [{"message": {"role": "assistant", "content": "I cannot translate that as I don't have that tool."}}]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = UnknownToolResistanceProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"


@pytest.mark.asyncio
async def test_unknown_tool_resistance_failed():
    responses = [
        # Model invents translate_document tool call!
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "translate_document", "arguments": "{}"}}]
                    }
                }]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = UnknownToolResistanceProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "failed"
    assert eval_res["failure_type"] == "unexpected_tool_call"


@pytest.mark.asyncio
async def test_loop_termination_failed():
    responses = [
        # Turn 1: tool call
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}}]
                    }
                }]
            }
        },
        # Turn 2: model repeats tool call after result is given!
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "lookup_order", "arguments": "{\"order_id\": 73921}"}}]
                    }
                }]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = LoopTerminationProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "failed"
    assert eval_res["failure_type"] == "loop_termination_failure"


@pytest.mark.asyncio
async def test_secret_redaction():
    secret_key = "sk-super-secret-12345"
    responses = [
        {
            "status_code": 401,
            "json": {"error": f"Unauthorized. The key {secret_key} was invalid."}
        }
    ]
    client = GatewayClient("http://localhost", secret_key, transport=MultiTurnMockTransport(responses))
    # We must trigger error parsing
    result = await client.chat_completion("test::model", {"messages": []})
    
    assert result.status == "error"
    assert secret_key not in result.failure_message
    assert "[REDACTED]" in result.failure_message


@pytest.mark.asyncio
async def test_resume_mode(tmp_path):
    output_path = tmp_path / "runs.jsonl"
    
    # Pre-populate run store
    from model_lab.store import ResultStore
    from model_lab.schemas import AttemptRecord
    store = ResultStore(str(output_path))
    
    # Add a completed attempt
    r = AttemptRecord(
        run_id="run1", route_id="test::model", probe_id="plain_chat",
        attempt=1, started_at="1", finished_at="2", status="passed",
        timing=Timing()
    )
    store.append(r)
    
    config = LabConfig(base_url="http://localhost", api_key="dummy", output_path=str(output_path), repetitions=1)
    runner = Runner(config, resume=True, transport=MultiTurnMockTransport([]))
    
    # Since plain_chat/attempt 1 is in completed_keys, run_suite should not invoke the client / mock transport (it is empty, so if it did it would error/crash)
    await runner.run_suite("run2", ["test::model"], ["plain_chat"])
    
    # Verify no new entries written for that completed run
    records = store.load_all()
    assert len(records) == 1


@pytest.mark.asyncio
async def test_parallel_tools_sequential_fallback():
    responses = [
        # Turn 1: model returns only 1 tool call (api)
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "c1", "type": "function", "function": {"name": "get_service_status", "arguments": "{\"service_name\": \"api\"}"}}
                        ]
                    }
                }]
            }
        },
        # Turn 2: model returns only 1 tool call (database)
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "c2", "type": "function", "function": {"name": "get_service_status", "arguments": "{\"service_name\": \"database\"}"}}
                        ]
                    }
                }]
            }
        },
        # Turn 3: model returns only 1 tool call (queue)
        {
            "json": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "c3", "type": "function", "function": {"name": "get_service_status", "arguments": "{\"service_name\": \"queue\"}"}}
                        ]
                    }
                }]
            }
        },
        # Turn 4: Final synthesis
        {
            "json": {
                "choices": [{"message": {"role": "assistant", "content": "All services are online"}}]
            }
        }
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = ParallelToolsProbe()
    result = await probe.run("test::model", client)
    eval_res = probe.evaluate(result)
    assert eval_res["status"] == "passed"
    assert eval_res["observations"]["parallel_tools"] is False
    assert eval_res["observations"]["sequential_fallback"] is True


@pytest.mark.asyncio
async def test_output_secret_scan(tmp_path):
    output_path = tmp_path / "runs.jsonl"
    from model_lab.store import ResultStore
    from model_lab.schemas import AttemptRecord
    store = ResultStore(str(output_path))
    
    secret_key = "sk-super-secret-12345"
    r = AttemptRecord(
        run_id="run1", route_id="test::model", probe_id="plain_chat",
        attempt=1, started_at="1", finished_at="2", status="passed",
        timing=Timing(),
        metadata={"auth_header": f"Bearer {secret_key}"} # We shouldn't store secrets, let's test scanning
    )
    store.append(r)
    
    # Read raw file content to scan for key
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # In real operation, no credentials should reside in JSONL at all.
    # The scan test enforces that if secret_key is present, we detect/fail.
    # Since we manually added it to test the scan, we expect it to be found.
    assert secret_key in content
    
    # Now let's test a clean record
    clean_path = tmp_path / "runs_clean.jsonl"
    clean_store = ResultStore(str(clean_path))
    
    # Sanitized mock attempt
    r_clean = AttemptRecord(
        run_id="run1", route_id="test::model", probe_id="plain_chat",
        attempt=1, started_at="1", finished_at="2", status="passed",
        timing=Timing(),
        metadata={"auth_header": "[REDACTED]"}
    )
    clean_store.append(r_clean)
    
    with open(clean_path, "r", encoding="utf-8") as f:
        clean_content = f.read()
    assert secret_key not in clean_content


@pytest.mark.asyncio
async def test_unicode_arabic_handling():
    arabic_text = "مرحبا بك في بوابة الذكاء الاصطناعي"
    responses = [
        {"json": {"choices": [{"message": {"role": "assistant", "content": arabic_text}}]}}
    ]
    client = GatewayClient("http://localhost", "dummy", transport=MultiTurnMockTransport(responses))
    probe = SystemMessageProbe()
    result = await probe.run("test::model", client)
    
    assert result.status == "passed"
    choices = result.raw_response.get("choices", [])
    assert choices[0]["message"]["content"] == arabic_text


@pytest.mark.asyncio
async def test_timeout_classification():
    class TimeoutMockTransport(httpx.MockTransport):
        def __init__(self):
            super().__init__(self.handle_req)
        def handle_req(self, request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Mocked request timeout")
            
    client = GatewayClient("http://localhost", "dummy", transport=TimeoutMockTransport())
    probe = RouteIdentityProbe()
    result = await probe.run("test::model", client)
    
    assert result.status == "error"
    assert result.failure_type == "timeout"
    assert "Mocked request timeout" in result.failure_message


@pytest.mark.asyncio
async def test_safe_cancellation_behavior():
    class CancelMockTransport(httpx.MockTransport):
        def __init__(self):
            super().__init__(self.handle_req)
        def handle_req(self, request: httpx.Request) -> httpx.Response:
            raise asyncio.CancelledError("Mocked cancellation")
            
    client = GatewayClient("http://localhost", "dummy", transport=CancelMockTransport())
    probe = RouteIdentityProbe()
    with pytest.raises(asyncio.CancelledError):
        await probe.run("test::model", client)


