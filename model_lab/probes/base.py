from abc import ABC, abstractmethod
from typing import Any, Dict
from model_lab.schemas import AttemptRecord, ProbeResult

class BaseProbe(ABC):
    @property
    @abstractmethod
    def probe_id(self) -> str:
        pass

    @abstractmethod
    async def run(self, route_id: str, client: Any) -> ProbeResult:
        """
        Executes the probe using the provided GatewayClient and returns the raw ProbeResult.
        """
        pass
        
    def evaluate(self, result: ProbeResult) -> Dict[str, Any]:
        """
        Evaluates the ProbeResult and sets the final status, failure_type, and extracts observations.
        Returns a dict with 'status', 'failure_type', 'failure_message', 'observations'.
        """
        if result.status in ("error", "failed"):
            return {
                "status": result.status,
                "failure_type": result.failure_type,
                "failure_message": result.failure_message,
                "observations": result.tool_call_observations
            }
            
        if not result.resolved_route:
            return {
                "status": "failed",
                "failure_type": "missing_route_header",
                "failure_message": "X-Youssef-Resolved-Route header is missing from gateway response",
                "observations": result.tool_call_observations
            }

        if result.route_identity_matched is False:
            return {
                "status": "failed",
                "failure_type": "route_identity_mismatch",
                "failure_message": f"Route identity mismatch: resolved route is {result.resolved_route}",
                "observations": result.tool_call_observations
            }
            
        if not result.valid_openai_shape:
            return {
                "status": "failed",
                "failure_type": "invalid_openai_response",
                "failure_message": "Response does not have valid OpenAI shape",
                "observations": result.tool_call_observations
            }
            
        return {
            "status": "passed",
            "failure_type": None,
            "failure_message": None,
            "observations": result.tool_call_observations
        }
