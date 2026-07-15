import logging
from uuid import uuid4
from typing import Any, Dict
import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from routes import KeyPool, ModelRoute

logger = logging.getLogger("gateway.forwarder")
ROTATE_ON = {401, 402, 403, 429, 500, 502, 503, 504}


async def forward_request(
    route: ModelRoute,
    pool: KeyPool,
    payload: Dict[str, Any],
    stream: bool
) -> Any:
    request_id = f"req_{uuid4().hex}"
    
    # Exclude complex composite public_id before forwarding
    upstream_payload = dict(payload)
    upstream_payload["model"] = route.upstream_model_id

    url = f"{pool.base_url}/chat/completions"
    
    response_headers = {
        "X-Youssef-Request-Id": request_id,
        "X-Youssef-Requested-Model": route.public_id,
        "X-Youssef-Resolved-Route": route.public_id,
        "X-Youssef-Upstream-Provider": route.provider_slug,
        "X-Youssef-Upstream-Model": route.upstream_model_id,
    }

    last_err_msg = "Unknown error"
    
    for idx in pool.order():
        key = pool.keys[idx]
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Connect timeout 15s, read/write timeout 300s
            client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=15.0))
            
            if stream:
                req = client.build_request("POST", url, headers=headers, json=upstream_payload)
                resp = await client.send(req, stream=True)
                
                # Check for rotate triggers
                if resp.status_code in ROTATE_ON:
                    await resp.aclose()
                    await client.aclose()
                    pool.mark_bad(idx)
                    last_err_msg = f"HTTP {resp.status_code}"
                    continue
                
                # Unrecoverable error (e.g. 4xx client errors)
                if resp.status_code >= 400:
                    body = await resp.aread()
                    await resp.aclose()
                    await client.aclose()
                    # Do not leak secrets or backend keys, output sanitized error
                    logger.error(f"Upstream error {resp.status_code} for {request_id}: {body.decode('utf-8', 'ignore')}")
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "message": "Upstream provider request failed.",
                            "request_id": request_id
                        }
                    )
                
                # Success
                pool.mark_ok(idx)
                
                async def gen():
                    try:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                    except Exception as exc:
                        logger.error(f"Stream interrupted for {request_id}: {exc}")
                    finally:
                        await resp.aclose()
                        await client.aclose()

                return StreamingResponse(gen(), media_type="text/event-stream", headers=response_headers)
            
            else:
                resp = await client.post(url, headers=headers, json=upstream_payload)
                await client.aclose()
                
                if resp.status_code in ROTATE_ON:
                    pool.mark_bad(idx)
                    last_err_msg = f"HTTP {resp.status_code}"
                    continue
                
                if resp.status_code >= 400:
                    logger.error(f"Upstream error {resp.status_code} for {request_id}: {resp.text}")
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "message": "Upstream provider request failed.",
                            "request_id": request_id
                        }
                    )
                
                pool.mark_ok(idx)
                return JSONResponse(content=resp.json(), headers=response_headers)
                
        except HTTPException:
            await client.aclose()
            raise
        except Exception as e:
            await client.aclose()
            pool.mark_bad(idx)
            last_err_msg = f"{type(e).__name__}: {str(e)}"
            continue

    # If all keys in the pool failed
    raise HTTPException(
        status_code=502,
        detail={
            "message": "All upstream keys exhausted for this route.",
            "request_id": request_id,
            "error_hint": last_err_msg
        }
    )
