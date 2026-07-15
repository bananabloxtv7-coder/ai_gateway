import pytest
import json
from model_lab.client import SSEParser, assemble_streaming_tool_calls

def test_sse_parser_basic():
    parser = SSEParser()
    events = parser.process_chunk(b"data: {\"test\": 1}\n\n")
    assert len(events) == 1
    assert events[0] == '{"test": 1}'

def test_sse_parser_fragmented():
    parser = SSEParser()
    events = parser.process_chunk(b"data: {\"te")
    assert len(events) == 0
    events = parser.process_chunk(b"st\": 2}\n\n")
    assert len(events) == 1
    assert events[0] == '{"test": 2}'

def test_sse_parser_done():
    parser = SSEParser()
    events = parser.process_chunk(b"data: [DONE]\n\n")
    assert len(events) == 0

def test_assemble_streaming_tool_calls():
    events = [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_123", "function": {"name": "get_weather"}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "location\": \"NY\"}"}}]}}]}
    ]
    tools = assemble_streaming_tool_calls(events)
    assert len(tools) == 1
    assert tools[0]["id"] == "call_123"
    assert tools[0]["function"]["name"] == "get_weather"
    assert tools[0]["function"]["arguments"] == "{\"location\": \"NY\"}"
