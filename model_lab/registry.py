import json
from typing import List, Dict, Any
from model_lab.store import ResultStore
import statistics

def aggregate_results(input_path: str, output_path: str):
    store = ResultStore(input_path)
    records = store.load_all()
    
    # route_id -> probe_id -> list of records
    grouped: Dict[str, Dict[str, List[Any]]] = {}
    
    for r in records:
        grouped.setdefault(r.route_id, {}).setdefault(r.probe_id, []).append(r)
        
    registry = []
    
    for route_id, probes_data in grouped.items():
        capabilities = {}
        total_runs = 0
        total_passed = 0
        
        for probe_id, probe_records in probes_data.items():
            runs = len(probe_records)
            passed = sum(1 for r in probe_records if r.status == "passed")
            
            capabilities[probe_id] = (passed == runs and runs > 0)
            
            total_runs += runs
            total_passed += passed
            
        # Classification logic
        if total_runs == 0:
            classification = "untested"
        elif total_passed == 0:
            classification = "incompatible"
        else:
            is_agent_ready = (
                capabilities.get("plain_chat", False) and
                capabilities.get("system_message", False) and
                capabilities.get("route_identity", False) and
                capabilities.get("single_tool_call", False) and
                capabilities.get("streaming_tool_call", False)
            )
            is_tool_capable = capabilities.get("single_tool_call", False)
            is_text_qualified = (
                capabilities.get("plain_chat", False) or
                capabilities.get("system_message", False) or
                capabilities.get("route_identity", False)
            )

            if is_agent_ready:
                classification = "agent-ready"
            elif is_tool_capable:
                classification = "tool-capable"
            elif is_text_qualified:
                classification = "text-only-qualified"
            else:
                classification = "incompatible"

            # If there are any failed attempts in an otherwise qualified route, mark it as unstable
            if total_passed < total_runs:
                classification = "unstable"
        
        registry.append({
            "route_id": route_id,
            "classification": classification,
            "capabilities": capabilities,
            "stats": {
                "total_runs": total_runs,
                "passed": total_passed,
                "success_rate": round(total_passed / total_runs, 2) if total_runs else 0.0
            }
        })
        
    registry.sort(key=lambda x: x["route_id"])
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    return registry
