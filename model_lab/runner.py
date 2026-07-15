import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Any
import logging

from model_lab.config import LabConfig
from model_lab.client import GatewayClient
from model_lab.store import ResultStore
from model_lab.schemas import AttemptRecord
from model_lab.probes import AVAILABLE_PROBES

logger = logging.getLogger("model_lab.runner")


class Runner:
    def __init__(self, config: LabConfig, resume: bool = False, force: bool = False, transport: Optional[Any] = None):
        self.config = config
        self.resume = resume
        self.force = force
        self.client = GatewayClient(config.base_url, config.api_key, config.timeout, transport=transport)
        self.store = ResultStore(config.output_path)
        self.completed_keys = set()
        
        if resume and not force:
            self.completed_keys = self.store.get_completed_keys()
            
        self.semaphore = asyncio.Semaphore(config.concurrency)

    async def _run_single_attempt(self, route_id: str, probe_id: str, attempt: int, run_id: str):
        key = f"{route_id}::{probe_id}::{attempt}"
        if key in self.completed_keys and not self.force:
            logger.info(f"Skipping completed attempt {key}")
            return

        probe_cls = AVAILABLE_PROBES.get(probe_id)
        if not probe_cls:
            logger.error(f"Unknown probe: {probe_id}")
            return
            
        probe = probe_cls()
        
        async with self.semaphore:
            logger.info(f"Running attempt {key}")
            started_at = datetime.now(timezone.utc).isoformat()
            
            raw_result = await probe.run(route_id, self.client)
            eval_result = probe.evaluate(raw_result)
            
            finished_at = datetime.now(timezone.utc).isoformat()
            
            record = AttemptRecord(
                run_id=run_id,
                route_id=route_id,
                probe_id=probe_id,
                attempt=attempt,
                started_at=started_at,
                finished_at=finished_at,
                status=eval_result["status"],
                failure_type=eval_result["failure_type"],
                failure_message=eval_result["failure_message"],
                http_status=raw_result.http_status,
                stream=raw_result.timing.total_ms > 0, # just an approximation
                request_id=raw_result.request_id,
                requested_route=raw_result.requested_route,
                resolved_route=raw_result.resolved_route,
                route_identity_matched=raw_result.route_identity_matched,
                valid_openai_shape=raw_result.valid_openai_shape,
                timing=raw_result.timing,
                tool_call_observations=eval_result["observations"]
            )
            
            self.store.append(record)
            self.completed_keys.add(key)
            logger.info(f"Completed attempt {key} with status {record.status}")


    async def run_suite(self, run_id: str, routes: List[str], probes: List[str]):
        tasks = []
        for route_id in routes:
            for probe_id in probes:
                for attempt in range(1, self.config.repetitions + 1):
                    tasks.append(self._run_single_attempt(route_id, probe_id, attempt, run_id))
                    
        await asyncio.gather(*tasks)
