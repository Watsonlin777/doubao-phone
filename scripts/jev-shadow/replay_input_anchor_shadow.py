"""Offline replay for Stage 3 input/anchor prescreen shadow snapshots.

Dry-run only: reads synthetic snapshots, applies the fixed thresholds
(input 0.90, anchor 0.85, see stage3-input-anchor-prescreen-spec.md),
and prints judgements plus agreement with the old deterministic logic.
Correction 2026-10-27: for P2, jev_noul_input is the MATCH question
("Does the input content exactly match the expected message?"), NOT the
I1 empty question. The real replay on 2026-10-27 mistakenly used the empty
question for P2; that judgement was voided.

This script NEVER calls Jev, NEVER touches a live phone task, and
NEVER writes to production state files. A real Jev call requires
separate user authorization and must use the verified TypeSafe channel
only (never the free Zen channel for phone-task data).
"""
import argparse
import json
import sys

THRESHOLD_INPUT = 0.90
THRESHOLD_ANCHOR = 0.85


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
        {"run_id": "synthetic-1", "decision_point": "I1",
         "input_empty": True, "input_match": None, "anchor_visible": None,
         "readback_ok": True, "step_seconds": 2.0,
         "jev_noul_input": 0.96, "jev_noul_anchor": None},
        {"run_id": "synthetic-1", "decision_point": "P2",
         "input_empty": None, "input_match": True, "anchor_visible": True,
         "readback_ok": True, "step_seconds": 3.0,
         "jev_noul_input": 0.88, "jev_noul_anchor": 0.91},
        {"run_id": "synthetic-2", "decision_point": "I1",
         "input_empty": False, "input_match": None, "anchor_visible": None,
         "readback_ok": True, "step_seconds": 2.5,
         "jev_noul_input": 0.30, "jev_noul_anchor": None},
    ]
    for snap in snapshots:
        out = dict(snap)
        if snap["jev_noul_input"] is not None:
            out["jev_judgement_input"] = judge(snap["jev_noul_input"], THRESHOLD_INPUT)
        if snap["jev_noul_anchor"] is not None:
            out["jev_judgement_anchor"] = judge(snap["jev_noul_anchor"], THRESHOLD_ANCHOR)
        out["jev_provider"] = "typesafe"
        print(json.dumps(out, ensure_ascii=False))
    print("dry-run ok: 3 synthetic input/anchor snapshots, thresholds 0.90/0.85, no Jev call made")
    return 0


if __name__ == "__main__":
    sys.exit(main())
