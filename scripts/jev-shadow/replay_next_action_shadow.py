"""Offline replay for Stage 4 next-action shadow snapshots.

Dry-run only: reads synthetic snapshots, applies the fixed choice
confidence threshold (0.85, see stage4-next-action-spec.md), and prints
judgements plus agreement with the old logic's chosen action.

This script NEVER calls Jev, NEVER touches a live phone task, and
NEVER writes to production state files. A real Jev call requires
separate user authorization and must use the verified TypeSafe channel
only (never the free Zen channel for phone-task data).
"""
import argparse
import json
import sys

THRESHOLD = 0.85


def judge(choice, confidence):
    if choice is None or confidence is None:
        return "unknown"
    return choice if confidence >= THRESHOLD else "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True,
                        help="Only synthetic snapshots are processed.")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("dry-run is required")
    snapshots = [
        {"run_id": "synthetic-1", "decision_point": "N1",
         "next_action": "proceed", "check_passed": True,
         "readback_ok": True, "step_seconds": 3.0,
         "jev_choice": "proceed", "jev_confidence": 0.92},
        {"run_id": "synthetic-1", "decision_point": "N2",
         "next_action": "proceed", "check_passed": True,
         "readback_ok": True, "step_seconds": 2.5,
         "jev_choice": "re-read", "jev_confidence": 0.80},
        {"run_id": "synthetic-2", "decision_point": "N1",
         "next_action": "stop", "check_passed": False,
         "readback_ok": True, "step_seconds": 4.0,
         "jev_choice": "stop", "jev_confidence": 0.97},
    ]
    for snap in snapshots:
        out = dict(snap)
        out["jev_judgement"] = judge(snap["jev_choice"], snap["jev_confidence"])
        out["jev_provider"] = "typesafe"
        out["agree"] = out["jev_judgement"] == snap["next_action"] if out["jev_judgement"] != "unknown" else None
        print(json.dumps(out, ensure_ascii=False))
    print("dry-run ok: 3 synthetic next-action snapshots, threshold 0.85, no Jev call made")
    return 0


if __name__ == "__main__":
    sys.exit(main())
