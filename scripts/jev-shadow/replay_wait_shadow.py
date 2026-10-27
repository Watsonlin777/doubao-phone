"""Offline replay for Jev wait/stable shadow records (Stage 1, dry-run only).

Reads snapshot JSONL lines with fields: run_id, decision_point, old_logic_result,
readback_ok, step_seconds. In --dry-run mode it does NOT call Jev, it only builds
the Jev question payload defined in stage1-wait-stable-spec.md and prints the
shadow-log line that would be written (jev_* fields marked dry_run).
Real Jev calls are a separate, user-authorised step after a real phone task.
Usage: python3 replay_wait_shadow.py --input snapshots.jsonl --dry-run
"""
import argparse
import json
import sys

QUESTION = ("Is the screen now stable enough to read reliably, with no loading "
            "indicator, no banner covering the title, and no UI still changing?")
THRESHOLD = 0.80


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.dry_run:
        print("Refusing non-dry-run: real Jev calls need separate user authorisation.", file=sys.stderr)
        return 2
    n = 0
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            snap = json.loads(line)
            for field in ("run_id", "decision_point", "old_logic_result"):
                if field not in snap:
                    print(f"Missing field {field} in snapshot: {line}", file=sys.stderr)
                    return 2
            if snap["decision_point"] not in ("W1", "W2", "W3"):
                print(f"Bad decision_point: {snap['decision_point']}", file=sys.stderr)
                return 2
            out = {
                "run_id": snap["run_id"],
                "decision_point": snap["decision_point"],
                "jev_question": QUESTION,
                "jev_question_type": "noul",
                "threshold": THRESHOLD,
                "jev_judgement": "dry_run",
                "old_logic_result": snap["old_logic_result"],
                "readback_ok": snap.get("readback_ok"),
                "step_seconds": snap.get("step_seconds"),
            }
            print(json.dumps(out, ensure_ascii=False))
            n += 1
    print(f"dry-run ok: {n} snapshot(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
