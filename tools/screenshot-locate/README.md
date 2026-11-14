# Screenshot Locate (optional tool)

Turn a phone screenshot into a tap point, using the Gemini Decisions API
(`gemini-decision-1`). A single-file tool — standard library + PIL only —
that any phone-agent script can call instead of eyeballing coordinates or
waiting on a slow visual-grounder.

This is an **optional** add-on to the phone agent, not part of its core
path. The core skill works without it; this tool makes the locating step
faster and self-checking when you have a Gemini API key.

## What it does

```
screenshot + "the search icon at the top right"  ->  tap point [x, y] (phone pixels)
```

Two-stage pipeline (validated 2026-11-14 on a real WeChat chat-list screenshot):

1. **Stage 1** — a 40x25 grid over the whole screenshot; two `choice`
   questions (column, row) pick the coarse cell.
2. **Stage 2** — a 200x200 crop around that cell's centre; a 10x10 grid
   picks the exact point, mapped back to phone coordinates.

A `--row-only` mode asks only for the row and taps at the screen centre
(`--x-frac`, default 0.5) — for wide targets such as chat rows and the
message input bar, where "the centre of a wide span" is ill-defined and
the column answer is unreliable.

A `--expect STATE` **state guard** classifies the screen first (one
Decisions API `choice` call over the flow's states — WeChat: `chat_list`,
`chat`, `other`, `home`, `locked`, ~1.5k tokens, ~$0.00015, ~1-2 s).
If the screen is not the expected one:

- one level too deep (in a chat, expecting the list) -> Back, re-check;
- wrong app / home / locked -> jump home (`am start` WeChat), re-check;
- one level too shallow (on the list, expecting a chat) -> fail closed
  (entering a chat needs the row tap, which is the caller's job).

After `--max-state-rounds` (default 3) still mismatched, or with no `--adb`
to recover, the tool exits non-zero and produces **no** tap point.
`--state-only` only classifies (no locate). `--live` takes the screenshot
from the phone via `--adb` instead of a file.

## Requirements

- Python 3 + Pillow (`pip install pillow`).
- A Gemini API key. Resolution order: `$GEMINI_API_KEY`, then a Magpie
  `providers.json` (provider ids `google-qqqq`, fallback `google`; the file
  defaults to `~/.config/magpie/providers.json`, override with
  `$MAGPIE_PROVIDERS`). The key value is never printed or logged.
- For `--live` / recovery: `adb` on PATH and the phone reachable
  (`adb connect <host>:<port>`).

Phone coordinates assume a 1440x3168 display (OnePlus 13); change
`PHONE_W` / `PHONE_H` at the top of the file for another device.

## Usage

```bash
# locate a target in a saved screenshot
python3 locate.py shot.png "the search icon at the top right" --json

# wide target: only the row matters, tap at screen centre
python3 locate.py shot.png "the File Transfer Assistant chat row" --row-only --json

# live: take the screenshot from the phone, guard the state, then locate
python3 locate.py --live --adb 127.0.0.1:18092 --expect chat_list \
    "the File Transfer Assistant chat row" --row-only --json

# classify only (no tap point)
python3 locate.py --live --adb 127.0.0.1:18092 --expect chat_list --state-only --json
```

Output (JSON on stdout) includes the tap point plus both stages' picks and
confidences, time, tokens, cost, and the `state_check` block when the guard
ran:

```json
{"target": "...", "mode": "point", "phone": [720, 3086],
 "stage1": {"col": 36, "row": 24, "col_conf": 0.28, "row_conf": 0.98},
 "stage2": {"col": 6, "row": 6, "col_conf": 0.49, "row_conf": 0.67},
 "seconds": 7.7, "tokens": 3533, "cost_usd": 0.000484,
 "state_check": {"expected": "chat", "observed": "chat",
                 "observed_conf": 0.999, "actions": [], "ok": true}}
```

Debug images (stage-1 grid, stage-2 crop, retry crop) are saved next to the
screenshot by default (`--no-debug` to skip, `--workdir DIR` to move them).

## Design findings (measured)

- **High resolution, not ultra_high.** Ultra_high cost ~2x the image tokens
  and was *worse* on both test targets (a title column went from flat to
  flatter; an icon column dropped from 0.544 to 0.239).
- **Two choice questions, not 1000 yes/no questions.** A 1000-question
  `noul` run cost ~35x the tokens for the same information (~$0.007 vs
  ~$0.0002 per locate).
- **Wide targets need row-only.** On the message input bar, point mode
  landed ~180 px too high (on the bar's top edge, no focus) with low
  stage-2 confidence (0.23-0.27) and the retry did not fix it; row-only
  landed on the bar's centre (720, 3086) first try. Rule: wide/short
  targets (input bar, title text) -> row-only; point mode only for small
  square targets.
- **The stage-2 crop must contain the whole target.** When a crop cut off
  the title's left half, the visible centre shifted ~40 phone px right.
  A retry with a 1.5x crop fixes cut-off/edge picks — it does **not** fix
  misidentification.
- **Describe the target with its neighbours.** A bare "search icon at the
  top right" made the model pick the `+` icon twice, and the retry confirmed
  the wrong pick with *higher* confidence. "The search (magnifying glass)
  icon at the top right, to the left of the + icon" hit the right one.
- **Deterministic, but wording-sensitive.** Identical inputs give identical
  outputs digit-for-digit, yet a one-word change or a 23 px crop shift can
  flip the answer. If a result looks wrong, check the debug images and
  rephrase the target.

## Measured performance (2026-11-14, real phone, WeChat)

Full send task (File Transfer Assistant, message "你好") run twice:

| | First run (no guard, point mode) | Second run (guard + row-only input) |
|---|---|---|
| Wall-clock, start to sent | ~8 min | ~3 min 5 s |
| Locate hits | 2/3 (input bar missed, needed a fallback grounder) | 3/3, all first try |
| Locate + guard time | ~17 s | ~40 s |
| Locate + guard cost | ~$0.0013 | ~$0.0017 |

The guard costs ~1-2 s per step when the screen is already right, and ~18 s
to recover from the wrong app (launch + Back + re-classify) — a small price
for a flow that fixes itself instead of tapping the wrong screen. The
wall-clock win came from the input-bar fix: one missed locate cost minutes
of diagnosis in the first run.

Per-locate, the tool takes ~4-8 s and ~$0.0003-0.0007; a visual grounder
took ~20-29 s per locate on the same targets (~4-6x slower). The state
guard's offline validation classified 9/9 saved screenshots correctly
(chat list 0.9998/0.9997, chat 0.997-0.999, another app as `other` 0.9908,
and two mismatch cases correctly rejected); its live recovery (from another
app back to the chat list) passed in 9.25 s with a single jump-home action.

## Limits

- The model judges, it does not see pixel-perfect edges: targets straddling
  a grid boundary (e.g. a title split across two rows) come back with low
  confidence on the neighbours. Treat confidence < 0.45 as "check the debug
  image".
- A retry can confirm a wrong answer more confidently. If the stage-2
  confidence is low *and* the point looks wrong, rephrase the target
  instead of retrying.
- Coordinates are only as good as the screenshot: a stale or scrolled
  screenshot locates a stale target. Use `--live` when the screen may have
  changed since the last shot.
