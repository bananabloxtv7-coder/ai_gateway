import argparse
import asyncio
import json
import sys
import uuid
import httpx

from model_lab.config import LabConfig
from model_lab.runner import Runner
from model_lab.registry import aggregate_results

def run_discover(config: LabConfig):
    # Synchronously (or asynchronously) fetch /v1/models
    print("Discovering routes...")
    url = f"{config.base_url}/models"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json"
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=config.timeout)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        
        routes = [m["id"] for m in models]
        print(f"Discovered {len(routes)} explicit routes.")
        for r in routes:
            print(f"  - {r}")
            
    except Exception as e:
        print(f"Discovery failed: {e}", file=sys.stderr)
        sys.exit(1)


async def run_probe(args, config: LabConfig):
    routes = []
    if args.route:
        routes.append(args.route)
    elif args.routes_file:
        with open(args.routes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            routes.extend(data.get("routes", []))
            
    if args.max_routes and len(routes) > args.max_routes:
        routes = routes[:args.max_routes]
        
    probes = []
    if args.probe:
        probes.append(args.probe)
    elif args.suite == "protocol":
        probes.extend(["plain_chat", "system_message", "route_identity"])
    elif args.suite == "tool-calling":
        probes.extend([
            "single_tool_call",
            "forced_tool_choice",
            "tool_result_followup",
            "sequential_tools",
            "parallel_tools",
            "streaming_tool_call",
            "tool_error_recovery",
            "invalid_arguments_recovery",
            "unknown_tool_resistance",
            "loop_termination"
        ])
        
    if not routes:
        print("ERROR: No routes specified.", file=sys.stderr)
        sys.exit(1)
        
    if not probes:
        print("ERROR: No probes specified.", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(probes)} probes across {len(routes)} routes with {config.repetitions} repetitions (concurrency={config.concurrency})...")
    
    if args.dry_run:
        print("DRY RUN: Exiting without doing work.")
        return

    runner = Runner(config, resume=args.resume, force=args.force)
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    
    await runner.run_suite(run_id, routes, probes)
    print("Probe suite completed.")

def main():
    parser = argparse.ArgumentParser(prog="python -m model_lab.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # discover
    discover_parser = subparsers.add_parser("discover", help="Discover available explicit routes")
    
    # probe
    probe_parser = subparsers.add_parser("probe", help="Run probes against routes")
    probe_parser.add_argument("--route", help="Explicit route ID to test")
    probe_parser.add_argument("--routes-file", help="Path to JSON file containing routes")
    probe_parser.add_argument("--probe", help="Single probe ID to run")
    probe_parser.add_argument("--suite", choices=["protocol", "tool-calling"], help="Suite of probes to run")
    probe_parser.add_argument("--repetitions", type=int, default=3, help="Number of times to run each probe")
    probe_parser.add_argument("--concurrency", type=int, default=1, help="Concurrent probe executions")
    probe_parser.add_argument("--output", help="Path to write JSONL results")
    probe_parser.add_argument("--resume", action="store_true", help="Resume from previous JSONL")
    probe_parser.add_argument("--force", action="store_true", help="Force overwrite even if resume is set")
    probe_parser.add_argument("--dry-run", action="store_true", help="Print intention and exit")
    probe_parser.add_argument("--max-routes", type=int, help="Limit number of routes tested")
    
    # aggregate
    agg_parser = subparsers.add_parser("aggregate", help="Aggregate JSONL into capability registry")
    agg_parser.add_argument("--input", required=True, help="Input JSONL file")
    agg_parser.add_argument("--output", required=True, help="Output JSON registry file")
    
    args = parser.parse_args()
    
    # Do not execute API commands or read env vars for aggregate
    if args.command == "aggregate":
        aggregate_results(args.input, args.output)
        print(f"Aggregation complete. Wrote {args.output}")
        sys.exit(0)
    
    config = LabConfig.from_env()
    
    if args.command == "discover":
        run_discover(config)
    elif args.command == "probe":
        if args.repetitions is not None:
            config.repetitions = args.repetitions
        if args.concurrency is not None:
            config.concurrency = args.concurrency
        if args.output is not None:
            config.output_path = args.output
            
        asyncio.run(run_probe(args, config))

if __name__ == "__main__":
    main()
