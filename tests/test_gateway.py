import os
import json
import pytest
from unittest import mock
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

# 1. Set environment variables BEFORE importing auth/main
os.environ["GATEWAY_MASTER_KEY"] = "master123"
os.environ["GATEWAY_ADMIN_KEY"] = "admin456"
os.environ["ALIBABA_API_KEYS"] = '["ali1", "ali2"]'
os.environ["NVIDIA_API_KEYS"] = '["nv1"]'

import auth
import main
from auth import extract_bearer_token
from routes import Gateway, ModelRoute, KeyPool
from config import read_keys_from_env

client = TestClient(main.app)


def test_extract_bearer_token():
    assert extract_bearer_token("Bearer mytoken") == "mytoken"
    assert extract_bearer_token("bearer mytoken") == "mytoken"
    
    with pytest.raises(HTTPException):
        extract_bearer_token("")
    with pytest.raises(HTTPException):
        extract_bearer_token("Bearer")
    with pytest.raises(HTTPException):
        extract_bearer_token("Basic othertoken")


def test_read_keys_from_env():
    with mock.patch.dict(os.environ, {"TEST_API_KEYS": '["key-a", "key-b"]'}):
        keys = read_keys_from_env("TEST_API_KEYS")
        assert keys == ["key-a", "key-b"]

    with mock.patch.dict(os.environ, {"TEST_API_KEYS": "not-a-json"}):
        with pytest.raises(RuntimeError):
            read_keys_from_env("TEST_API_KEYS")

    with mock.patch.dict(os.environ, {"TEST_API_KEYS": '{"not": "array"}'}):
        with pytest.raises(RuntimeError):
            read_keys_from_env("TEST_API_KEYS")


def test_startup_fails_without_master_key():
    import importlib
    with mock.patch.dict(os.environ, {"GATEWAY_MASTER_KEY": ""}):
        with pytest.raises(RuntimeError) as excinfo:
            importlib.reload(auth)
        assert "GATEWAY_MASTER_KEY is required" in str(excinfo.value)
    # Restore key
    importlib.reload(auth)


def test_startup_fails_without_admin_key():
    import importlib
    with mock.patch.dict(os.environ, {"GATEWAY_ADMIN_KEY": ""}):
        with pytest.raises(RuntimeError) as excinfo:
            importlib.reload(auth)
        assert "GATEWAY_ADMIN_KEY is required" in str(excinfo.value)
    # Restore key
    importlib.reload(auth)


def test_gateway_and_admin_keys_must_differ():
    import importlib
    with mock.patch.dict(os.environ, {"GATEWAY_MASTER_KEY": "samekey", "GATEWAY_ADMIN_KEY": "samekey"}):
        with pytest.raises(RuntimeError) as excinfo:
            importlib.reload(auth)
        assert "must be different" in str(excinfo.value)
    # Restore keys
    importlib.reload(auth)


def test_models_rejects_missing_auth():
    resp = client.get("/v1/models")
    assert resp.status_code == 401
    assert "Missing authorization" in resp.text


def test_models_rejects_invalid_auth():
    resp = client.get("/v1/models", headers={"Authorization": "Bearer badtoken"})
    assert resp.status_code == 401
    assert "Invalid API key" in resp.text


def test_models_accepts_valid_gateway_auth():
    # Make sure auth module has correct keys loaded
    auth.GATEWAY_MASTER_KEY = "master123"
    resp = client.get("/v1/models", headers={"Authorization": "Bearer master123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    for m in data["data"]:
        assert "::" in m["id"]


def test_admin_rejects_gateway_key():
    auth.GATEWAY_ADMIN_KEY = "admin456"
    resp = client.get("/admin/stats", headers={"Authorization": "Bearer master123"})
    assert resp.status_code == 401
    assert "Invalid admin key" in resp.text


def test_admin_accepts_admin_key():
    auth.GATEWAY_ADMIN_KEY = "admin456"
    resp = client.get("/admin/stats", headers={"Authorization": "Bearer admin456"})
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    # Verify no secret key is exposed in admin stats
    for p in data["providers"]:
        assert "keys" not in p
        assert "keys_count" in p


def test_duplicate_model_routes_are_preserved():
    cfg = {
        "providers": [
            {
                "name": "Provider A",
                "slug": "p_a",
                "enabled": True,
                "base_url": "https://api.a.com",
                "keys": ["k1"],
                "models": ["model-x"]
            },
            {
                "name": "Provider B",
                "slug": "p_b",
                "enabled": True,
                "base_url": "https://api.b.com",
                "keys": ["k2"],
                "models": ["model-x"]
            }
        ]
    }
    gw = Gateway(cfg)
    assert len(gw.models) == 2
    assert "p_a::model-x" in gw.routes
    assert "p_b::model-x" in gw.routes


def test_explicit_route_resolves_correct_provider():
    cfg = {
        "providers": [
            {
                "name": "Provider A",
                "slug": "p_a",
                "enabled": True,
                "base_url": "https://api.a.com",
                "keys": ["k1"],
                "models": ["model-x"]
            },
            {
                "name": "Provider B",
                "slug": "p_b",
                "enabled": True,
                "base_url": "https://api.b.com",
                "keys": ["k2"],
                "models": ["model-x"]
            }
        ]
    }
    gw = Gateway(cfg)
    
    res_a = gw.resolve("p_a::model-x")
    assert res_a is not None
    route_a, pool_a = res_a
    assert route_a.provider_name == "Provider A"
    assert pool_a.base_url == "https://api.a.com"

    res_b = gw.resolve("p_b::model-x")
    assert res_b is not None
    route_b, pool_b = res_b
    assert route_b.provider_name == "Provider B"
    assert pool_b.base_url == "https://api.b.com"


@pytest.mark.asyncio
async def test_upstream_receives_unprefixed_model_id():
    from routes import ModelRoute, KeyPool
    from forwarder import forward_request
    import httpx
    
    route = ModelRoute(
        public_id="p_a::model-x",
        provider_name="Provider A",
        provider_slug="p_a",
        upstream_model_id="model-x"
    )
    pool = KeyPool("Provider A", "https://api.a.com", ["k1"])
    
    payload = {"model": "p_a::model-x", "messages": [{"role": "user", "content": "hello"}]}

    # Create mock response object
    mock_resp = mock.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "response-x"}}]}

    # Mock AsyncClient
    mock_client = mock.MagicMock(spec=httpx.AsyncClient)
    mock_client.post = mock.AsyncMock(return_value=mock_resp)
    mock_client.aclose = mock.AsyncMock()

    with mock.patch("httpx.AsyncClient", return_value=mock_client):
        resp = await forward_request(route, pool, payload, stream=False)
        assert resp.status_code == 200
        assert resp.headers["X-Youssef-Resolved-Route"] == "p_a::model-x"
        assert resp.headers["X-Youssef-Upstream-Provider"] == "p_a"
        assert resp.headers["X-Youssef-Upstream-Model"] == "model-x"
        
        # Verify model parameter was cleaned of prefix when passed to httpx post
        called_args, called_kwargs = mock_client.post.call_args
        assert called_kwargs["json"]["model"] == "model-x"


@pytest.mark.asyncio
async def test_streaming_preserves_route_headers():
    from routes import ModelRoute, KeyPool
    from forwarder import forward_request
    import httpx

    route = ModelRoute(
        public_id="p_a::model-x",
        provider_name="Provider A",
        provider_slug="p_a",
        upstream_model_id="model-x"
    )
    pool = KeyPool("Provider A", "https://api.a.com", ["k1"])
    payload = {"model": "p_a::model-x", "messages": [], "stream": True}

    mock_resp = mock.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    async def dummy_iter():
        yield b"data: hello\n\n"
    mock_resp.aiter_bytes = dummy_iter
    mock_resp.aclose = mock.AsyncMock()

    mock_client = mock.MagicMock(spec=httpx.AsyncClient)
    mock_client.build_request = mock.MagicMock()
    mock_client.send = mock.AsyncMock(return_value=mock_resp)
    mock_client.aclose = mock.AsyncMock()

    with mock.patch("httpx.AsyncClient", return_value=mock_client):
        resp = await forward_request(route, pool, payload, stream=True)
        assert resp.status_code == 200
        assert resp.headers["X-Youssef-Resolved-Route"] == "p_a::model-x"
        assert resp.headers["X-Youssef-Upstream-Provider"] == "p_a"
        assert resp.headers["X-Youssef-Upstream-Model"] == "model-x"


@pytest.mark.asyncio
async def test_no_secret_is_returned_in_errors():
    from routes import ModelRoute, KeyPool
    from forwarder import forward_request
    import httpx

    route = ModelRoute(
        public_id="p_a::model-x",
        provider_name="Provider A",
        provider_slug="p_a",
        upstream_model_id="model-x"
    )
    pool = KeyPool("Provider A", "https://api.a.com", ["k1"])
    payload = {"model": "p_a::model-x"}

    mock_resp = mock.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 400
    mock_resp.text = "Secret key database error or similar sensitive text"
    
    mock_client = mock.MagicMock(spec=httpx.AsyncClient)
    mock_client.post = mock.AsyncMock(return_value=mock_resp)
    mock_client.aclose = mock.AsyncMock()

    with mock.patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as excinfo:
            await forward_request(route, pool, payload, stream=False)
        assert excinfo.value.status_code == 502
        assert "Upstream provider request failed" in excinfo.value.detail["message"]
        assert "Secret key" not in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_route_failover_does_not_happen_implicitly():
    from routes import ModelRoute, KeyPool
    from forwarder import forward_request
    import httpx

    route = ModelRoute(
        public_id="p_a::model-x",
        provider_name="Provider A",
        provider_slug="p_a",
        upstream_model_id="model-x"
    )
    # 2 keys in pool
    pool = KeyPool("Provider A", "https://api.a.com", ["k1", "k2"])
    payload = {"model": "p_a::model-x"}

    # Mock responses: first key gives 401, second key gives 200
    mock_resp_fail = mock.MagicMock(spec=httpx.Response)
    mock_resp_fail.status_code = 401
    
    mock_resp_ok = mock.MagicMock(spec=httpx.Response)
    mock_resp_ok.status_code = 200
    mock_resp_ok.json.return_value = {"choices": []}

    call_count = 0
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_resp_fail
        else:
            return mock_resp_ok

    mock_client = mock.MagicMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post
    mock_client.aclose = mock_type = mock.AsyncMock()

    with mock.patch("httpx.AsyncClient", return_value=mock_client):
        resp = await forward_request(route, pool, payload, stream=False)
        assert resp.status_code == 200
        assert call_count == 2


def test_admin_no_limit_endpoint():
    auth.GATEWAY_ADMIN_KEY = "admin456"

    # Missing auth
    resp = client.get("/admin/no-limit")
    assert resp.status_code == 401

    # Bad auth
    resp = client.get("/admin/no-limit", headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401

    # Good auth
    resp = client.get("/admin/no-limit", headers={"Authorization": "Bearer admin456"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "enabled"
    assert "discovered_providers" in data
    assert "extra_keys_loaded" in data


def test_admin_stats_includes_models():
    auth.GATEWAY_ADMIN_KEY = "admin456"
    resp = client.get("/admin/stats", headers={"Authorization": "Bearer admin456"})
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    for p in data["providers"]:
        assert "models" in p
        assert isinstance(p["models"], list)
        assert "keys_count" in p
