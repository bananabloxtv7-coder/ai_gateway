"""
Configuration management for Model Lab.
Reads settings strictly from environment variables.
Never expose API keys in representations.
"""
import os
from dataclasses import dataclass, field
import sys


@dataclass
class LabConfig:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    timeout: float = 120.0
    concurrency: int = 1
    repetitions: int = 3
    output_path: str = "model_lab/results/runs.jsonl"
    
    @classmethod
    def from_env(cls) -> "LabConfig":
        base_url = os.environ.get("YOUSSEF_BASE_URL")
        api_key = os.environ.get("YOUSSEF_API_KEY")
        
        if not base_url:
            print("ERROR: YOUSSEF_BASE_URL environment variable is missing.", file=sys.stderr)
            sys.exit(1)
        if not api_key:
            print("ERROR: YOUSSEF_API_KEY environment variable is missing.", file=sys.stderr)
            sys.exit(1)
            
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
        )
