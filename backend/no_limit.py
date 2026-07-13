"""
No-Limit Module — auto-discovers providers from pi's models.json and merges
them into the gateway with multi-key support.

Flow:
  1. Read ~/.pi/agent/models.json → extract all providers (baseUrl, apiKey, models)
  2. Read keys_no_limit.json (if exists) → override/add multiple keys per provider
  3. Merge with keys.json providers → pass unified config to Gateway
  4. Gateway's existing round-robin + failover handles the rest seamlessly
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


PI_MODELS_PATH = Path.home() / ".pi" / "agent" / "models.json"
NO_LIMIT_KEYS_PATH = Path(os.getenv(
    "NO_LIMIT_KEYS",
    str(Path(__file__).parent / "keys_no_limit.json")
))


def load_pi_providers() -> List[Dict[str, Any]]:
    """Extract OpenAI-compatible providers from pi's models.json."""
    if not PI_MODELS_PATH.exists():
        return []

    with open(PI_MODELS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    providers: List[Dict[str, Any]] = []

    for name, prov in data.get("providers", {}).items():
        # Only include OpenAI-compatible providers (api == "openai-completions")
        if prov.get("api") != "openai-completions":
            continue

        base_url = prov.get("baseUrl", "")
        api_key = prov.get("apiKey", "")
        models_raw = prov.get("models", [])

        if not base_url or not api_key:
            continue

        # Extract model IDs
        model_ids = [m["id"] for m in models_raw if m.get("id")]

        providers.append({
            "name": name,
            "enabled": True,
            "base_url": base_url,
            "keys": [api_key],  # default single key from pi
            "models": model_ids,
        })

    return providers


def _is_placeholder_key(key: str) -> bool:
    """Ignore example/empty keys so they don't break the pool."""
    if not key or not isinstance(key, str):
        return True
    lowered = key.lower()
    return lowered.startswith("sk-your-") or lowered.startswith("nvapi-your-") or lowered == ""


def load_no_limit_keys() -> Dict[str, List[str]]:
    """Load additional keys from keys_no_limit.json.
    Format: { "provider_name": ["key1", "key2", ...], ... }
    """
    if not NO_LIMIT_KEYS_PATH.exists():
        return {}

    with open(NO_LIMIT_KEYS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_providers(
    base_providers: List[Dict[str, Any]],
    pi_providers: List[Dict[str, Any]],
    extra_keys: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """Merge all provider sources into one unified list.
    
    Priority: keys_no_limit.json keys > keys.json keys > pi's apiKey
    
    Deduplication: If a provider exists in multiple sources, merge models & keys.
    """
    merged: Dict[str, Dict[str, Any]] = {}

    # Pass 1: base providers from keys.json
    for p in base_providers:
        name = p["name"]
        merged[name] = {
            "name": name,
            "enabled": p.get("enabled", True),
            "base_url": p["base_url"],
            "keys": list(p.get("keys", [])),
            "models": list(p.get("models", [])),
        }

    # Pass 2: pi providers (add or merge)
    for p in pi_providers:
        name = p["name"]
        if name in merged:
            # Merge models (deduplicate)
            existing_models = set(merged[name]["models"])
            for m in p["models"]:
                if m not in existing_models:
                    merged[name]["models"].append(m)
                    existing_models.add(m)
            # Merge keys (deduplicate)
            existing_keys = set(merged[name]["keys"])
            for k in p["keys"]:
                if k not in existing_keys:
                    merged[name]["keys"].append(k)
                    existing_keys.add(k)
        else:
            merged[name] = {
                "name": name,
                "enabled": True,
                "base_url": p["base_url"],
                "keys": list(p["keys"]),
                "models": list(p["models"]),
            }

    # Pass 3: no-limit extra keys (append to existing keys, not override)
    for name, keys in extra_keys.items():
        if name.startswith("_"):
            continue
        if name not in merged:
            # extra_keys alone without a provider definition (keys.json or pi models) are ignored
            continue
        existing_keys = set(merged[name]["keys"])
        for k in keys:
            if _is_placeholder_key(k):
                continue
            if k not in existing_keys:
                merged[name]["keys"].append(k)
                existing_keys.add(k)

    # Reject providers with zero keys
    result = []
    for p in merged.values():
        if p["keys"]:
            result.append(p)

    return result


def build_unified_config(base_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Build the final config by merging keys.json + pi models.json + keys_no_limit.json."""
    base_providers = base_cfg.get("providers", [])
    pi_providers = load_pi_providers()
    extra_keys = load_no_limit_keys()

    unified = merge_providers(base_providers, pi_providers, extra_keys)

    return {"providers": unified}


def create_example_no_limit_keys():
    """Generate an example keys_no_limit.json if it doesn't exist."""
    if NO_LIMIT_KEYS_PATH.exists():
        return

    example = {
        "_comment": "No-Limit keys — add multiple real API keys per provider here. They are APPENDED to existing keys (from keys.json or pi models.json).",
        "Alibaba": ["sk-your-real-alibaba-key-1", "sk-your-real-alibaba-key-2", "sk-your-real-alibaba-key-3"],
        "NVIDIA": ["nvapi-your-real-nvidia-key-1", "nvapi-your-real-nvidia-key-2"],
        "flatkey.ai": ["sk-your-real-flatkey-key-1", "sk-your-real-flatkey-key-2"],
        "cometapi": ["sk-your-real-cometapi-key-1", "sk-your-real-cometapi-key-2"]
    }

    with open(NO_LIMIT_KEYS_PATH, "w", encoding="utf-8") as f:
        json.dump(example, f, indent=2, ensure_ascii=False)

    print(f"[no-limit] Created example file: {NO_LIMIT_KEYS_PATH}")