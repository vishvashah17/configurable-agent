import os
import json
import datetime
from pathlib import Path

class ResultLogger:
    """Save each interactive or dashboard run result in JSON (auto-numbered runs)."""

    def __init__(self, base_dir="results"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.run_id = self._get_next_run_id()
        self.run_dir = self.base_dir / f"run_{self.run_id:03d}"
        self.run_dir.mkdir(exist_ok=True)
        self.file_path = self.run_dir / "results.json"
        print(f"[+] Results will be saved in: {self.run_dir}")

    def _get_next_run_id(self):
        """Automatically pick next run number."""
        runs = [int(p.name.split('_')[1]) for p in self.base_dir.glob("run_*") if p.is_dir()]
        return max(runs, default=0) + 1

    def save_result(self, question, baseline, configurable, similar, reflection=None, metrics=None):
        """Append a single Q/A interaction to results.json safely"""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "question": question,
            "baseline_answer": baseline,
            "configurable": {
                "plan": configurable.get("plan"),
                "answer": configurable.get("answer"),
                "persona": configurable.get("persona")
            },
            "similar_examples": similar,
            "metrics": metrics or {}
        }

        results = []
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    results = json.load(f)
            except json.JSONDecodeError:
                print("[⚠] Corrupted results.json, recreating a new one...")
                results = []
        else:
            print(f"[+] Creating new results file: {self.file_path}")

        results.append(entry)

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            print(f"[✓] Saved result #{len(results)} to {self.file_path}")
        except Exception as e:
            print(f"[❌] Error writing results: {e}")
