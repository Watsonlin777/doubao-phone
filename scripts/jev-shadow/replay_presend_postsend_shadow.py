"""Offline replay for Stage 5 pre-send gate and post-send check shadows.

Dry-run only: reads synthetic snapshots, applies the fixed thresholds
(pre-send gate 0.95, post-send check 0.90, see
stage5-presend-postsend-spec.md), and prints judgements.

This script NEVER calls Jev, NEVER touches a live phone task, and
NEVER writes to production state files. A real Jev call requires
separate user authorization and must use the verified TypeSafe channel
only (never the free Zen channel for phone-task data).
"""
import argparse
import json
import sys

THRESHOLD_GATE = 0.95
THRESHOLD_POST = 0.90


def judge(noul, threshold):
    if noul is None:
        return "unknown"
    return "match" if noul >= threshold else "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True,
                        help="Only synthetic snapshots are processed.")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("dry-run is required")
    snapshots = [
        {"run_id": "synthetic-1", "decision_point": "G1",
         "gate_pass": True, "send_after_present": None, "plus_one": None,
         "readback_ok": True, "step_seconds": 2.0, "jev_noul": 0.97},
        {"run_id": "synthetic-1", "decision_point": "G2",
         "gate_pass": None, "send_after_present": True, "plus_one": True,
         "readback_ok": True, "step_seconds": 3.0, "jev_noul": 0.93},
        {"run_id": "synthetic-2", "decision_point": "G1",
         "gate_pass": True, "send_after_present": None, "plus_one": None,
         "readback_ok": True, "step_seconds": 2.5, "jev_noul": 0.92},
    ]
    for snap in snapshots:
        threshold = THRESHOLD_GATE if snap["decision_point"] == "G1" else THRESHOLD_POST
        out = dict(snap)
        out["jev_judgement"] = judge(snap["jev_noul"], threshold)
        out["jev_provider"] = "typesafe"
        print(json.dumps(out, ensure_ascii=False))
    print("dry-run ok: 3 synthetic pre-send/post-send snapshots, thresholds 0.95/0.90, no Jev call made")
    return 0


if __name__ == "__main__":
    sys.exit(main())
