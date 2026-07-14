import itertools
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ModelRoute:
    public_id: str
    provider_name: str
    provider_slug: str
    upstream_model_id: str


class KeyPool:
    """Round-robin pool of API keys for one provider, with health tracking."""

    def __init__(self, name: str, base_url: str, keys: List[str]):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.keys = keys
        self._cycle = itertools.cycle(range(len(keys))) if keys else None
        self._lock = Lock()
        # Stats monitoring
        self.usage = [0] * len(keys)
        self.errors = [0] * len(keys)
        self.disabled_until = [0.0] * len(keys)

    def _next_index(self) -> Optional[int]:
        if not self.keys:
            return None
        now = time.time()
        with self._lock:
            for _ in range(len(self.keys)):
                idx = next(self._cycle)
                if self.disabled_until[idx] <= now:
                    return idx
            # If all are in cooldown, pick the one whose cooldown ends soonest
            return min(range(len(self.keys)), key=lambda i: self.disabled_until[i])

    def order(self) -> List[int]:
        """Return key indices to try, starting from the round-robin pick."""
        start = self._next_index()
        if start is None:
            return []
        n = len(self.keys)
        return [(start + i) % n for i in range(n)]

    def mark_ok(self, idx: int):
        self.usage[idx] += 1

    def mark_bad(self, idx: int, cooldown: float = 60.0):
        self.errors[idx] += 1
        self.disabled_until[idx] = time.time() + cooldown


class Gateway:
    def __init__(self, cfg: Dict[str, Any]):
        self.providers: Dict[str, KeyPool] = {}
        # routes: provider_slug::upstream_model_id -> ModelRoute
        self.routes: Dict[str, ModelRoute] = {}
        # routes_by_model: upstream_model_id -> List of route public_ids
        self.routes_by_model: Dict[str, List[str]] = {}
        # models list for /v1/models (compatible with openai model list format)
        self.models: List[Dict[str, Any]] = []

        for p in cfg.get("providers", []):
            if not p.get("enabled", True):
                continue

            name = p["name"]
            slug = p.get("slug", name.lower().replace(".", "_"))
            pool = KeyPool(name, p["base_url"], p.get("keys", []))
            self.providers[name] = pool

            for upstream_model_id in p.get("models", []):
                public_id = f"{slug}::{upstream_model_id}"

                if public_id in self.routes:
                    raise RuntimeError(f"Duplicate route ID detected: {public_id}")

                route = ModelRoute(
                    public_id=public_id,
                    provider_name=name,
                    provider_slug=slug,
                    upstream_model_id=upstream_model_id,
                )

                self.routes[public_id] = route
                self.routes_by_model.setdefault(upstream_model_id, []).append(public_id)

                self.models.append({
                    "id": public_id,
                    "object": "model",
                    "owned_by": name,
                    "upstream_model_id": upstream_model_id,
                })

    def resolve(self, public_model_id: str) -> Optional[tuple[ModelRoute, KeyPool]]:
        route = self.routes.get(public_model_id)
        if route is None:
            return None

        pool = self.providers.get(route.provider_name)
        if pool is None:
            return None

        return route, pool
