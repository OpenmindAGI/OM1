import os
import json
from datetime import datetime
from typing import Any, Dict, List


class AgentEvaluationLogger:
    def __init__(self, log_dir: str = None):
        if log_dir is None:
            # Use the evaluations directory inside eval folder
            log_dir = os.path.join(os.path.dirname(__file__), "evaluations")
        
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path_jsonl = os.path.join(log_dir, f"eval_{timestamp}.jsonl")
        self.log_file_path_txt = os.path.join(log_dir, f"eval_{timestamp}.log")

    def log_tick(self, prompt: str, output: Any, actions: List[Dict[str, Any]], meta: Dict[str, Any] = None):
        timestamp_now = datetime.utcnow().isoformat()
        output_data = output.dict() if hasattr(output, "dict") else str(output)

        # JSONL Log (machine-friendly)
        record = {
            "timestamp": timestamp_now,
            "prompt": prompt,
            "output": output_data,
            "actions": actions,
            "meta": meta or {}
        }
        with open(self.log_file_path_jsonl, "a") as f_jsonl:
            f_jsonl.write(json.dumps(record) + "\n")

        # Pretty Log (dev-friendly)
        with open(self.log_file_path_txt, "a") as f_txt:
            f_txt.write(f"[{timestamp_now}]\n")
            f_txt.write("Prompt:\n")
            f_txt.write(prompt.strip() + "\n\n")
            f_txt.write("Output:\n")
            f_txt.write(json.dumps(output_data, indent=2) + "\n\n")
            f_txt.write("Actions:\n")
            for action in actions:
                f_txt.write(f"  - {action['type']}: {action['value']}\n")
            if meta:
                f_txt.write("\nMeta:\n")
                f_txt.write(json.dumps(meta, indent=2) + "\n")
            f_txt.write("\n" + "-" * 80 + "\n\n")