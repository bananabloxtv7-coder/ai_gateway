"""
AI Gateway — OpenAI-compatible proxy that pools MANY API keys behind ONE key.

Concept (as shown in the video):
  * You register several API keys per provider (keys you legitimately own).
  * The gateway exposes a single OpenAI-compatible endpoint (/v1/...).
  * Requests are load-balanced across keys (round-robin) and automatically
    fail over to the next key/provider on 401/402/429/5xx — so the aggregate
    quota behaves as if it "never runs out", and dozens of models
    (GPT / Claude / Gemini / open models ...) are reachable through one API.

Run:
  pip install -r requirements.txt
  cp keys.example.json keys.json   # then edit
  uvicorn main:app --host 0.0.0.0 --port 8080 --reload
"""
from __future__ import annotations

import itertools
import json
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from no_limit import build_unified_config, create_example_no_limit_keys

# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).parent
CONFIG_PATH = Path(os.getenv("GATEWAY_CONFIG", BASE_DIR / "keys.json"))

# The single "master" key your apps use to talk to the gateway.
# Leave empty to disable gateway auth (local use only).
GATEWAY_MASTER_KEY = os.getenv("GATEWAY_MASTER_KEY", "")

# HTTP status codes that mean "this key is exhausted / bad -> try the next one".
ROTATE_ON = {401, 402, 403, 429, 500, 502, 503, 504}


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Config not found: {CONFIG_PATH}. Copy keys.example.json to keys.json.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class KeyPool:
    """Round-robin pool of API keys for one provider, with health tracking."""

    def __init__(self, name: str, base_url: str, keys: List[str]):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.keys = keys
        self._cycle = itertools.cycle(range(len(keys))) if keys else None
        self._lock = Lock()
        # stats
        self.usage = [0] * len(keys)          # successful requests per key
        self.errors = [0] * len(keys)         # errors per key
        self.disabled_until = [0.0] * len(keys)  # cooldown timestamp per key

    def _next_index(self) -> Optional[int]:
        if not self.keys:
            return None
        now = time.time()
        with self._lock:
            for _ in range(len(self.keys)):
                idx = next(self._cycle)
                if self.disabled_until[idx] <= now:
                    return idx
            # all in cooldown -> pick the one whose cooldown ends soonest
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
        # model_name -> provider_name
        self.model_map: Dict[str, str] = {}
        # ordered list of models for /v1/models
        self.models: List[Dict[str, Any]] = []
        for p in cfg.get("providers", []):
            if not p.get("enabled", True):
                continue
            pool = KeyPool(p["name"], p["base_url"], p.get("keys", []))
            self.providers[p["name"]] = pool
            for m in p.get("models", []):
                self.model_map[m] = p["name"]
                self.models.append({"id": m, "object": "model", "owned_by": p["name"]})

    def resolve(self, model: str) -> Optional[KeyPool]:
        prov = self.model_map.get(model)
        if prov:
            return self.providers[prov]
        # fallback: if only one provider, route everything to it
        if len(self.providers) == 1:
            return next(iter(self.providers.values()))
        return None


# Build unified config: keys.json + pi models.json + keys_no_limit.json
_raw_cfg = load_config()
_unified_cfg = build_unified_config(_raw_cfg)

# Auto-create example keys_no_limit.json if missing
create_example_no_limit_keys()

GW = Gateway(_unified_cfg)

app = FastAPI(title="AI Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_auth(authorization: Optional[str]):
    if not GATEWAY_MASTER_KEY:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token != GATEWAY_MASTER_KEY:
        raise HTTPException(status_code=401, detail="Invalid gateway key.")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/")
def root():
    return {"service": "AI Gateway", "status": "ok", "providers": list(GW.providers)}


@app.get("/v1/models")
def list_models(authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    return {"object": "list", "data": GW.models}


@app.get("/admin/stats")
def stats(authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    out = []
    for name, pool in GW.providers.items():
        out.append({
            "provider": name,
            "keys": len(pool.keys),
            "usage": pool.usage,
            "errors": pool.errors,
            "total_usage": sum(pool.usage),
            "total_errors": sum(pool.errors),
            "models": [m for m, p in GW.model_map.items() if p == name],
        })
    return {"providers": out}


@app.get("/admin/no-limit")
def no_limit_status(authorization: Optional[str] = Header(None)):
    """Show which providers came from pi models.json vs keys.json vs keys_no_limit.json."""
    check_auth(authorization)
    from no_limit import _is_placeholder_key, load_pi_providers, load_no_limit_keys
    base_cfg = load_config()
    pi_provs = load_pi_providers()
    extra_keys = load_no_limit_keys()
    return {
        "providers_from_keys_json": [p["name"] for p in base_cfg.get("providers", [])],
        "providers_from_pi_models": [p["name"] for p in pi_provs],
        "providers_with_extra_keys": [k for k in extra_keys if not k.startswith("_")],
        "merged_providers": list(GW.providers.keys()),
        "total_models": len(GW.models),
        "key_counts": {
            name: {
                "total_keys": len(pool.keys),
                "extra_no_limit_keys": sum(
                    1 for k in extra_keys.get(name, []) if not _is_placeholder_key(k)
                ),
            }
            for name, pool in GW.providers.items()
        },
    }


async def _forward(pool: KeyPool, payload: Dict[str, Any], stream: bool):
    """Try each key in the pool until one succeeds."""
    url = f"{pool.base_url}/chat/completions"
    last_err = None
    for idx in pool.order():
        key = pool.keys[idx]
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=15.0))
            if stream:
                req = client.build_request("POST", url, headers=headers, json=payload)
                resp = await client.send(req, stream=True)
                if resp.status_code in ROTATE_ON:
                    await resp.aclose()
                    await client.aclose()
                    pool.mark_bad(idx)
                    last_err = f"{pool.name} key#{idx} -> HTTP {resp.status_code}"
                    continue
                if resp.status_code >= 400:
                    body = await resp.aread()
                    await resp.aclose()
                    await client.aclose()
                    raise HTTPException(status_code=resp.status_code, detail=body.decode("utf-8", "ignore"))
                pool.mark_ok(idx)

                async def gen():
                    try:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                    finally:
                        await resp.aclose()
                        await client.aclose()

                return StreamingResponse(gen(), media_type="text/event-stream")
            else:
                resp = await client.post(url, headers=headers, json=payload)
                await client.aclose()
                if resp.status_code in ROTATE_ON:
                    pool.mark_bad(idx)
                    last_err = f"{pool.name} key#{idx} -> HTTP {resp.status_code}: {resp.text[:200]}"
                    continue
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                pool.mark_ok(idx)
                return JSONResponse(resp.json())
        except HTTPException:
            raise
        except Exception as e:  # network error -> rotate
            pool.mark_bad(idx)
            last_err = f"{pool.name} key#{idx} -> {type(e).__name__}: {e}"
            continue
    raise HTTPException(status_code=502, detail=f"All keys exhausted. Last error: {last_err}")


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    payload = await request.json()
    model = payload.get("model", "")
    pool = GW.resolve(model)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Unknown model '{model}'. See /v1/models.")
    stream = bool(payload.get("stream", False))
    return await _forward(pool, payload, stream)
