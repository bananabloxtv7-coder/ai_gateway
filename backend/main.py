import logging
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from auth import require_gateway_auth, require_admin_auth
from config import load_providers_config
from routes import Gateway
from forwarder import forward_request

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway.main")

# Load configuration and initialize Gateway
try:
    config = load_providers_config()
    GW = Gateway(config)
    logger.info(f"Gateway initialized with {len(GW.models)} active routes.")
except Exception as e:
    logger.error(f"Failed to initialize Gateway: {e}")
    raise

app = FastAPI(title="AI Gateway", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    # Public endpoint returning minimum generic details
    return {
        "service": "AI Gateway",
        "status": "ok",
    }


@app.get("/v1/models", dependencies=[Depends(require_gateway_auth)])
def list_models():
    return {"object": "list", "data": GW.models}


@app.post("/v1/chat/completions", dependencies=[Depends(require_gateway_auth)])
async def chat_completions(
    request: Request,
    x_youssef_route: Optional[str] = Header(None)
):
    payload = await request.json()
    model = payload.get("model", "")

    # Priority 1: X-Youssef-Route header
    # Priority 2: model parameter from payload
    selected_route_id = x_youssef_route or model
    if not selected_route_id:
        raise HTTPException(
            status_code=400,
            detail="Missing model in payload or X-Youssef-Route header."
        )

    # Normalize single-colon (e.g. provider:model) to double-colon (provider::model)
    if ":" in selected_route_id and "::" not in selected_route_id:
        selected_route_id = selected_route_id.replace(":", "::")

    resolved = GW.resolve(selected_route_id)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail=f"Route '{selected_route_id}' not found. See GET /v1/models for valid explicit routes."
        )

    route, pool = resolved
    stream = bool(payload.get("stream", False))
    return await forward_request(route, pool, payload, stream)


@app.get("/admin/stats", dependencies=[Depends(require_admin_auth)])
def stats():
    out = []
    for name, pool in GW.providers.items():
        # Do not return key secrets or credentials
        out.append({
            "provider": name,
            "keys_count": len(pool.keys),
            "usage": pool.usage,
            "errors": pool.errors,
            "total_usage": sum(pool.usage),
            "total_errors": sum(pool.errors),
        })
    return {"providers": out}
