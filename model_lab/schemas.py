"""
Data schemas for the Model Lab runs, records, and parsing.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class Timing:
    total_ms: float = 0.0
    first_byte_ms: Optional[float] = None


@dataclass
class AttemptRecord:
    run_id: str
    route_id: str
    probe_id: str
    attempt: int
    started_at: str
    finished_at: str
    status: str  # passed, failed, skipped, error
    failure_type: Optional[str] = None
    failure_message: Optional[str] = None
    http_status: Optional[int] = None
    stream: bool = False
    request_id: Optional[str] = None
    requested_route: Optional[str] = None
    resolved_route: Optional[str] = None
    route_identity_matched: Optional[bool] = None
    valid_openai_shape: Optional[bool] = None
    timing: Timing = field(default_factory=Timing)
    tool_call_observations: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "route_id": self.route_id,
            "probe_id": self.probe_id,
            "attempt": self.attempt,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "failure_type": self.failure_type,
            "failure_message": self.failure_message,
            "http_status": self.http_status,
            "stream": self.stream,
            "request_id": self.request_id,
            "requested_route": self.requested_route,
            "resolved_route": self.resolved_route,
            "route_identity_matched": self.route_identity_matched,
            "valid_openai_shape": self.valid_openai_shape,
            "timing": {
                "total_ms": self.timing.total_ms,
                "first_byte_ms": self.timing.first_byte_ms,
            },
            "tool_call_observations": self.tool_call_observations,
            "metadata": self.metadata,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class ProbeResult:
    """Internal schema representing the raw output returned by a client probe before being transformed into an AttemptRecord."""
    status: str
    failure_type: Optional[str] = None
    failure_message: Optional[str] = None
    http_status: Optional[int] = None
    request_id: Optional[str] = None
    requested_route: Optional[str] = None
    resolved_route: Optional[str] = None
    route_identity_matched: Optional[bool] = None
    valid_openai_shape: Optional[bool] = None
    timing: Timing = field(default_factory=Timing)
    tool_call_observations: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_response: Any = None # Should never contain sensitive info
