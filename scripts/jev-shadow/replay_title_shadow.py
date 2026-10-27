"""Offline replay for Stage 2 title-prescreen shadow snapshots.

Dry-run only: reads synthetic snapshots, applies the fixed threshold
(0.90, see stage2-title-prescreen-spec.md), and prints match/unknown
judgements plus agreement with the old exact-title logic.

This script NEVER calls Jev, NEVER touches a live phone task, and
NEVER writes to production state files. A real Jev call requires
separate user authorization and must use the verified TypeSafe channel
only (never the free Zen channel for phone-task data).
"""
import argparse
import json
import sys

THRESHOLD = 0.90


def judge(noul):
    if noul is None:
        return "unknown"
    return "match" if noul >= THRESHOLD else "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True,
                        help="Only synthetic snapshots are processed.")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("dry-run is required")
    # Synthetic snapshots: title_match is the old exact logic result.
    # jev_noul is a placeholder for what an offline Jev call would return;
    # in dry-run it is supplied here, not fetched from any service.
    snapshots = [
        {"run_id": "synthetic-1", "decision_point": "T1",
         "title_match": True, "readback_ok": True, "step_seconds": 4.0,
         "jev_noul": 0.97},
        {"run_id": "synthetic-1", "decision_point": "T2",
         "title_match": True, "readback_ok": True, "step_seconds": 3.5,
         "jev_noul": 0.88},
        {"run_id": "synthetic-2", "decision_point": "T1",
         "title_match": False, "readback_ok": True, "step_seconds": 5.0,
         "jev_noul": 0.42},
    ]
    for snap in snapshots:
        judgement = judge(snap["jev_noul"])
        # Agreement: Jev 'match' agrees only when old logic also matched.
        # Jev 'unknown' is never agreement to send; it means re-read/stop.
        agree = (judgement == "match") == snap["title_match"] if judgement == "match" else None
        out = dict(snap)
        out["jev_judgement"] = judgement
        out["jev_provider"] = "typesafe"
        out["agree"] = agree
        print(json.dumps(out, ensure_ascii=False))
    print("dry-run ok: 3 synthetic title snapshots, threshold 0.90, no Jev call made")
    return 0


if __name__ == "__main__":
    sys.exit(main())
