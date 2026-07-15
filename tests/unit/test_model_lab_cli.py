import sys
import os
import json
import pytest
from unittest.mock import patch
from model_lab.cli import main

def test_cli_dry_run(tmp_path, monkeypatch):
    # Setup dummy environment variables
    monkeypatch.setenv("YOUSSEF_API_KEY", "dummy_key")
    monkeypatch.setenv("YOUSSEF_BASE_URL", "http://localhost")
    
    # Create routes file matching the JSON structure expected: {"routes": [...]}
    routes_file = tmp_path / "routes.json"
    with open(routes_file, "w") as f:
        json.dump({"routes": ["openai::gpt-4o", "anthropic::claude-3-opus"]}, f)
        
    output_file = tmp_path / "runs.jsonl"
    
    test_args = [
        "model_lab",
        "probe",
        "--routes-file", str(routes_file),
        "--suite", "protocol",
        "--dry-run",
        "--output", str(output_file),
        "--concurrency", "2",
        "--repetitions", "1",
        "--max-routes", "1"
    ]
    
    with patch.object(sys, "argv", test_args):
        # Should execute successfully without throwing errors or running actual requests
        try:
            main()
        except SystemExit as e:
            assert e.code == 0


def test_cli_config_failure(monkeypatch):
    # Unset critical environment variables
    monkeypatch.delenv("YOUSSEF_API_KEY", raising=False)
    monkeypatch.delenv("YOUSSEF_BASE_URL", raising=False)
    
    test_args = ["model_lab", "probe", "--route", "openai::gpt-4o"]
    
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # Should exit with non-zero exit code
        assert exc_info.value.code == 1


def test_cli_aggregate(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUSSEF_API_KEY", "dummy_key")
    monkeypatch.setenv("YOUSSEF_BASE_URL", "http://localhost")
    
    runs_file = tmp_path / "runs.jsonl"
    # Create a dummy runs.jsonl line
    from model_lab.schemas import AttemptRecord, Timing
    from model_lab.store import ResultStore
    store = ResultStore(str(runs_file))
    r = AttemptRecord(
        run_id="run1", route_id="test::model", probe_id="plain_chat",
        attempt=1, started_at="1", finished_at="2", status="passed",
        timing=Timing()
    )
    store.append(r)
    
    registry_file = tmp_path / "registry.json"
    
    test_args = [
        "model_lab",
        "aggregate",
        "--input", str(runs_file),
        "--output", str(registry_file)
    ]
    
    with patch.object(sys, "argv", test_args):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
            
    # Verify aggregate output exists and contains compiled results
    assert os.path.exists(registry_file)
    with open(registry_file, "r") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["route_id"] == "test::model"
