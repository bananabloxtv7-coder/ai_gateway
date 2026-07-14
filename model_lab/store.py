import os
import json
from typing import List
from model_lab.schemas import AttemptRecord

class ResultStore:
    def __init__(self, filepath: str):
        self.filepath = filepath
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
    def append(self, record: AttemptRecord):
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(record.to_jsonl() + "\n")
            
    def load_all(self) -> List[AttemptRecord]:
        if not os.path.exists(self.filepath):
            return []
        records = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    records.append(AttemptRecord(**data))
        return records
        
    def get_completed_keys(self) -> set:
        """Returns a set of strings uniquely identifying completed attempts."""
        keys = set()
        for r in self.load_all():
            keys.add(f"{r.route_id}::{r.probe_id}::{r.attempt}")
        return keys
