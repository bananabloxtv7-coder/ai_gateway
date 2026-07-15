import os
import json
import pytest
from model_lab.schemas import AttemptRecord, Timing
from model_lab.store import ResultStore
from model_lab.registry import aggregate_results

def test_aggregation(tmp_path):
    output_path = tmp_path / "registry.json"
    runs_path = tmp_path / "runs.jsonl"
    
    store = ResultStore(str(runs_path))
    
    # 5 matching capabilities for agent-ready classification
    probes = ["plain_chat", "system_message", "route_identity", "single_tool_call", "streaming_tool_call"]
    for p in probes:
        r = AttemptRecord(
            run_id="run1", route_id="test::model", probe_id=p,
            attempt=1, started_at="1", finished_at="2", status="passed",
            timing=Timing()
        )
        store.append(r)
    
    registry = aggregate_results(str(runs_path), str(output_path))
    
    assert len(registry) == 1
    assert registry[0]["route_id"] == "test::model"
    assert registry[0]["classification"] == "agent-ready"
    assert registry[0]["capabilities"]["plain_chat"] is True
    assert registry[0]["capabilities"]["single_tool_call"] is True
    assert registry[0]["capabilities"]["streaming_tool_call"] is True
    assert registry[0]["stats"]["total_runs"] == 5
    assert registry[0]["stats"]["passed"] == 5
    assert registry[0]["stats"]["success_rate"] == 1.0
