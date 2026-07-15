from typing import Any
from model_lab.probes.base import BaseProbe
from model_lab.schemas import ProbeResult

class PlainChatProbe(BaseProbe):
    @property
    def probe_id(self) -> str:
        return "plain_chat"

    async def run(self, route_id: str, client: Any) -> ProbeResult:
        payload = {
            "model": route_id,
            "messages": [
                {"role": "user", "content": "Hello, how are you?"}
            ],
            "max_tokens": 50,
            "stream": False
        }
        return await client.chat_completion(route_id, payload)
