import typer
import asyncio
import json
import os
import sys
import difflib

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
EVAL_DIR = os.path.join(ROOT_DIR, "eval")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, EVAL_DIR)

from runtime.config import load_config
from runtime.cortex import CortexRuntime
from simulator import CortexSimulator

app = typer.Typer()

def normalize_type(type_str):
    type_map = {
        "move": "action",
        "perform_action": "action",
        "action": "action",
        "speak": "speak",
        "emotion": "emotion",
        "sit": "action",                # ADD
        "shake paw": "action",         # ADD
        "run": "action",               # ADD
        "execute": "action"            # If applicable
    }
    return type_map.get(type_str, type_str)

def fuzzy_match(val1, val2, threshold=0.8):
    # Simple fuzzy ratio
    return difflib.SequenceMatcher(None, val1.lower(), val2.lower()).ratio() >= threshold

def calculate_score(expected, actual, mode, weights, criteria):
    if mode == "exact":
        return 1.0 if expected == actual else 0.0

    elif mode == "partial":
        score = 0.0
        max_score = sum(weights.get(cmd["type"], 1) for cmd in expected if cmd["type"] in criteria)
        matched = set()

        for cmd in expected:
            cmd_type_norm = normalize_type(cmd["type"])
            cmd_value = cmd["value"]
            for i, act in enumerate(actual):
                act_type_norm = normalize_type(act["type"])
                act_value = act["value"]
                if i in matched:
                    continue
                if cmd_type_norm == act_type_norm:
                    if cmd_value == act_value or fuzzy_match(cmd_value, act_value):
                        score += weights.get(cmd["type"], 1)
                        matched.add(i)
                        break

        return score / max_score if max_score > 0 else 0.0

    elif mode == "sequence":
        filtered_expected = [cmd for cmd in expected if cmd["type"] in criteria]
        filtered_actual = [cmd for cmd in actual if cmd["type"] in criteria]
        return 1.0 if filtered_expected == filtered_actual else 0.0

    return 0.0

@app.command()
def evaluate(test_path: str, config_name: str, runs: int = 1):
    """
    Evaluate test cases from a JSON file against a specific agent config.
    Supports modes: exact, partial, sequence.
    Outputs a detailed report as JSON.
    """
    with open(test_path, "r") as f:
        test_cases = json.load(f)

    config = load_config(config_name)
    runtime = CortexRuntime(config, debug_once=True)
    simulator = CortexSimulator(runtime)

    async def run_tests():
        total = 0
        passed = 0
        failed = 0
        cumulative_score = 0
        max_total = 0
        results = []

        for i in range(runs):
            print(f"\n[Test Run #{i+1}] --------------------------------")
            for case in test_cases:
                total += 1
                prompt = case["prompt"]
                expected = case["expected"]
                name = case.get("name", prompt[:30])
                mode = case.get("mode", "exact")
                weights = case.get("weights", {"move": 1, "speak": 1, "emotion": 1})
                criteria = case.get("criteria", ["move", "speak", "emotion"])
                max_marks = case.get("marks", 1)

                print(f"\n[Running] {name}...")

                # Use simulator instead of direct runtime
                result = await simulator.simulate_tick(prompt)
                actual = result["actions"]

                score_percent = calculate_score(expected, actual, mode, weights, criteria)
                score = round(score_percent * max_marks, 2)
                cumulative_score += score
                max_total += max_marks

                status = "pass" if score_percent == 1.0 else "partial" if score_percent > 0 else "fail"

                if status == "pass":
                    typer.secho(f"[PASS] ({score}/{max_marks})", fg=typer.colors.GREEN)
                    passed += 1
                else:
                    typer.secho(f"[{status.upper()}] ({score}/{max_marks})", fg=typer.colors.YELLOW)
                    print("Got:\n", json.dumps(actual, indent=2))
                    print("Expected:\n", json.dumps(expected, indent=2))
                    failed += 1

                results.append({
                    "name": name,
                    "prompt": prompt,
                    "mode": mode,
                    "score": score,
                    "max_score": max_marks,
                    "status": status,
                    "expected": expected,
                    "actual": actual
                })

        # Print summary
        print("\n[Test Summary]")
        print(f"Total Tests Run: {total}")
        print(f"[PASSED] {passed}")
        print(f"[FAILED/PARTIAL] {failed}")
        print(f"[FINAL SCORE] {round(cumulative_score, 2)} / {max_total}")

        # Save report
        from datetime import datetime
        timestamp = datetime.now().strftime("%b%d_%H%M")

        test_file_base = os.path.splitext(os.path.basename(test_path))[0]
        config_safe = config_name.replace("/", "_").replace("\\", "_")

        report_filename = f"Evaluation Report - {test_file_base} with {config_safe} - {timestamp}.json"
        report_dir = os.path.join(EVAL_DIR, "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, report_filename)

        with open(report_path, "w") as rf:
            json.dump(results, rf, indent=2)

        print(f"\n[REPORT] Detailed report saved to: {report_path}")

        # Update index.json
        def make_readable(name):
            base = os.path.splitext(name)[0]
            base = base.replace("_", " ").replace("-", " ")
            return base.strip().title()

        index_file = os.path.join(report_dir, "index.json")
        all_reports = []

        for fname in os.listdir(report_dir):
            if fname.endswith(".json") and fname != "index.json":
                all_reports.append({
                    "filename": fname,
                    "title": make_readable(fname)
                })

        with open(index_file, "w") as f:
            json.dump(all_reports, f, indent=2)

        print(f"📂 index.json updated with {len(all_reports)} report(s).")

    asyncio.run(run_tests())

if __name__ == "__main__":
    app()

