from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class RouteIdentityProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "route_identity"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        payload = {
            "model": route_id,
            "messages": [
                {"role": "user", "content": "Respond with 'Hello'."}
            ],
            "max_tokens": 10,
            "stream": False
        }
        return await client.chat_completion(route_id, payload)
