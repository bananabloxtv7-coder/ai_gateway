import json
import os
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).parent
CONFIG_PATH = Path(os.getenv("GATEWAY_CONFIG", BASE_DIR / "providers.json"))


def read_keys_from_env(variable_name: str) -> List[str]:
    raw_value = os.getenv(variable_name, "").strip()
    if not raw_value:
        return []

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{variable_name} must be a valid JSON array."
        ) from exc

    if not isinstance(value, list):
        raise RuntimeError(
            f"{variable_name} must contain a JSON array."
        )

    keys = [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]

    if not keys:
        raise RuntimeError(
            f"{variable_name} contains no usable keys."
        )

    return keys


def load_providers_config() -> Dict[str, Any]:
    # Default to example if the main config doesn't exist
    path_to_use = CONFIG_PATH
    if not path_to_use.exists():
        example_path = BASE_DIR / "providers.example.json"
        if example_path.exists():
            path_to_use = example_path
        else:
            raise RuntimeError(f"Providers configuration not found at {CONFIG_PATH}")

    with open(path_to_use, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Hydrate keys from env variables
    hydrated_providers = []
    for provider in config.get("providers", []):
        if not provider.get("enabled", True):
            continue

        # Load keys from the environment variable specified in keys_env
        keys_env_var = provider.get("keys_env")
        if keys_env_var:
            keys = read_keys_from_env(keys_env_var)
            provider["keys"] = keys
        else:
            provider["keys"] = []

        hydrated_providers.append(provider)

    return {"providers": hydrated_providers}
