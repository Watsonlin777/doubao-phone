#!/usr/bin/env python3
"""Two-stage screenshot locator using the Gemini Decisions API.

Given a phone screenshot and a target description (e.g. "the search icon at
the top right"), returns the tap point in phone coordinates (1440x3168).

Pipeline (validated 2026-11-14 on a WeChat chat-list screenshot):
  stage 1: 40x25 grid over the whole screenshot, choice x/y -> coarse cell
  stage 2: 200x200 crop around the coarse cell centre, 10x10 grid, choice
           x/y -> tap point mapped back to phone coordinates

Findings baked into the defaults:
  - resolution "high", NOT "ultra_high" (ultra_high cost 2x tokens and was
    worse on both targets in round 2)
  - two choice questions beat 1000 noul questions (35x cheaper, same info)
  - wide targets (chat rows): the column is unreliable because the "centre"
    of a wide span is ill-defined; use --row-only and tap at --x-frac
  - the stage-2 crop must contain the whole target, or the visible centre
    shifts (round 4: the title's left half was cut off, final point moved
    ~40 phone px right)
  - describe the target so it cannot be confused with a neighbour
    (e.g. "the search icon, to the left of the + icon"): a bare description
    made the model pick the + icon twice in tool testing, and the retry
    confirmed the wrong pick with higher confidence. A retry fixes a
    cut-off/edge pick, not a misidentification.
  - identical inputs give identical outputs (two runs matched digit for
    digit), but a one-word change or a 23 px crop shift can flip the answer:
    the model is sensitive to wording and framing. If a result looks wrong,
    check the debug images and rephrase the target.

Usage:
  python3 locate.py <screenshot> "<target description>" [--row-only]
                     [--x-frac 0.5] [--crop 200] [--workdir DIR]
                     [--no-debug] [--json]

  --row-only   ask only for the row (wide targets); x = --x-frac of width
  --x-frac     tap x as a fraction of screen width (row-only mode), default 0.5
  --crop       stage-2 crop size in working-image pixels, default 200
  --workdir    where to save the stage-1/stage-2 debug images
               (default: next to the screenshot)
  --json       print only the JSON result (default also prints a summary line
               to stderr)
  --expect STATE  state guard: classify the screen first (one Decisions API
               choice call over the flow's states; wechat: chat_list, chat,
               other, home, locked). If it is not the expected screen:
                 one level too deep (chat, expected chat_list) -> Back, re-check
                 wrong app / home / locked -> jump home (am start WeChat), re-check
                 one level too shallow (chat_list, expected chat) -> fail closed:
                   entering needs the row tap, which is the caller's job
               After --max-state-rounds (default 3) still mismatched, or with
               no --adb to recover, the tool exits non-zero and produces NO
               tap point. --state-only only classifies (no locate); --live
               takes the screenshot from the phone via --adb. Cost: one extra
               choice call (~1.5k tokens, ~$0.00015, ~1-2 s) per check.

API key (value is never printed or logged):
  $GEMINI_API_KEY, or Magpie providers.json (google-qqqq, fallback google).
  The providers file defaults to ~/.config/magpie/providers.json and can be
  overridden with $MAGPIE_PROVIDERS.

Output (JSON on stdout):
  {"target": ..., "mode": "point"|"row", "phone": [x, y],
   "stage1": {"col":..,"row":..,"col_conf":..,"row_conf":..},
   "stage2": {...}, "seconds": .., "tokens": .., "cost_usd": ..,
   "debug": {"stage1_image": ..., "stage2_image": ...}}
"""
import argparse
import base64
import io
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFont

API_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
MODEL = "gemini-decision-1"
PRICE_PER_MTOK = 0.10  # USD per 1M input tokens; output is free
MAGPIE_PROVIDERS = os.environ.get(
    "MAGPIE_PROVIDERS", os.path.expanduser("~/.config/magpie/providers.json"))
PHONE_W, PHONE_H = 1440, 3168  # OnePlus 13 display; screencap is 1440x3168
# (was 3216 — corrected 2026-11-14 after the B screenshot measured 1440x3168;
#  the 1.5% y error did not change any earlier hit/miss call)
NORM_W = 930  # working width; matches the validated experiments


def get_key():
    env = os.environ.get("GEMINI_API_KEY")
    if env:
        return env
    try:
        d = json.load(open(MAGPIE_PROVIDERS))
    except (OSError, ValueError):
        d = {}
    for want_id in ("google-qqqq", "google"):
        for p in d.get("providers", []):
            if p.get("id") == want_id:
                k = p.get("key")
                if isinstance(k, dict):
                    for f in ("value", "apiKey", "api_key", "key"):
                        if isinstance(k.get(f), str) and k[f]:
                            return k[f]
                if isinstance(k, list) and k:
                    first = k[0]
                    if isinstance(first, str) and first:
                        return first
                    if isinstance(first, dict):
                        for f in ("value", "apiKey", "api_key", "key"):
                            if isinstance(first.get(f), str) and first[f]:
                                return first[f]
                if isinstance(k, str) and k:
                    return k
    raise SystemExit("no API key: set GEMINI_API_KEY or provide Magpie providers.json")


def api_call(key, body, retries=2):
    data = json.dumps(body).encode()
    req = urllib.request.Request(API_URL, data=data, headers={
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    }, method="POST")
    last = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.status, json.loads(r.read()), time.time() - t0
        except urllib.error.HTTPError as e:
            last = (e.code, e.read().decode(errors="replace")[:1000])
            if 400 <= e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = ("network", str(e)[:500])
        if attempt < retries:
            time.sleep(1)
    return last[0], {"error": last[1]}, 0.0


def load_font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_grid(im, ncols, nrows):
    im = im.copy()
    d = ImageDraw.Draw(im)
    w, h = im.size
    cw, ch = w / ncols, h / nrows
    font = load_font(13 if max(w, h) > 500 else 11)
    red = (255, 0, 0)
    for i in range(ncols + 1):
        x = i * cw
        d.line([(x, 0), (x, h)], fill=red, width=1)
    for j in range(nrows + 1):
        y = j * ch
        d.line([(0, y), (w, y)], fill=red, width=1)
    for i in range(ncols):
        d.text((i * cw + 2, 2), str(i), fill=red, font=font)
    for j in range(nrows):
        d.text((2, j * ch + 2), str(j), fill=red, font=font)
    return im


def img_b64(im):
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def ask(key, im, intro, target, ncols, nrows, row_only=False):
    questions = {
        "target_row": {"type": "choice",
                       "instructions": "Which grid row contains the center of %s?" % target,
                       "criteria": {"r%02d" % i: "Row %d" % i for i in range(nrows)}}
    }
    if not row_only:
        questions["target_col"] = {"type": "choice",
                                   "instructions": "Which grid column contains the center of %s?" % target,
                                   "criteria": {"c%02d" % i: "Column %d" % i for i in range(ncols)}}
    body = {"model": MODEL,
            "input": [{"type": "text", "text": intro},
                      {"type": "image", "data": img_b64(im), "mime_type": "image/jpeg",
                       "resolution": "high"}],
            "questions": questions}
    st, resp, dt = api_call(key, body)
    if st != 200:
        raise SystemExit("Decisions API error %s: %s" % (st, resp))
    out = {"seconds": round(dt, 2),
           "tokens": resp.get("usage", {}).get("total_tokens", 0)}
    for q, key_name in (("target_col", "col"), ("target_row", "row")):
        if q in resp.get("answers", {}):
            a = resp["answers"][q]
            out[key_name] = int(a["choice"][1:])
            out[key_name + "_conf"] = a.get("confidence")
    return out


# --- state guard -----------------------------------------------------------
# Screens the task can be on, for the --expect guard. The classifier asks the
# Decisions API one choice question over these states. If the observed screen
# is not the expected one, the guard either steps Back (one level too deep),
# jumps home (wrong app / home / locked), or fails closed (one level too
# shallow: entering a chat needs the row tap, which is the caller's job).
STATE_SETS = {
    "wechat": {
        "states": {
            "chat_list": "WeChat chat list screen: a vertical list of conversations, each with an avatar, a name, and a preview of the last message; '微信' title at the top",
            "chat": "WeChat chat conversation screen: message bubbles in the middle and a white text input box at the bottom",
            "other": "A different app, not WeChat: for example a chat app, a browser, a settings screen, or a social media app",
            "home": "The phone home screen or app launcher: app icons arranged on a wallpaper",
            "locked": "The lock screen: a clock with a prompt for PIN, pattern, password, or fingerprint",
        },
        "depth": {"chat_list": 0, "chat": 1},
        "home_cmd": "am start -n com.tencent.mm/.ui.LauncherUI",
    },
}


def classify_state(key, im, flow):
    """One Decisions API choice call: which screen is this? Returns the
    winning label, its confidence, and the raw answer for inspection."""
    states = STATE_SETS[flow]["states"]
    body = {"model": MODEL,
            "input": [{"type": "text", "text": "This is a phone screenshot."},
                      {"type": "image", "data": img_b64(im), "mime_type": "image/jpeg",
                       "resolution": "high"}],
            "questions": {"screen": {"type": "choice",
                                     "instructions": "Which of these best describes the screen shown in this screenshot?",
                                     "criteria": states}}}
    st, resp, dt = api_call(key, body)
    if st != 200:
        raise SystemExit("Decisions API error %s: %s" % (st, resp))
    a = resp.get("answers", {}).get("screen", {})
    return {"label": a.get("choice"),
            "confidence": a.get("confidence"),
            "raw": a,
            "seconds": round(dt, 2),
            "tokens": resp.get("usage", {}).get("total_tokens", 0)}


def adb_cmd(serial, *argv, timeout=30):
    cmd = ["adb", "-s", serial] + list(argv)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise SystemExit("adb not found on PATH; recovery needs adb")
    return r.returncode, (r.stdout + r.stderr).strip()


def adb_shot(serial, path):
    rc, out = adb_cmd(serial, "shell", "screencap", "-p", "/sdcard/locate_state.png")
    if rc != 0:
        raise SystemExit("adb screencap failed: %s" % out)
    rc, out = adb_cmd(serial, "pull", "/sdcard/locate_state.png", path)
    if rc != 0:
        raise SystemExit("adb pull failed: %s" % out)
    return path


def to_work(im):
    w0, h0 = im.size
    if w0 > NORM_W:
        return im.resize((NORM_W, round(h0 * NORM_W / w0)), Image.LANCZOS)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("screenshot", nargs="?", help="screenshot file (omit with --live)")
    ap.add_argument("target", nargs="?", help="target description (omit with --state-only)")
    ap.add_argument("--row-only", action="store_true")
    ap.add_argument("--x-frac", type=float, default=0.5)
    ap.add_argument("--crop", type=int, default=200)
    ap.add_argument("--workdir")
    ap.add_argument("--no-debug", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--expect", help="expected screen state; enables the state guard (flow states)")
    ap.add_argument("--flow", default="wechat", choices=list(STATE_SETS))
    ap.add_argument("--adb", help="adb device serial; enables Back / jump-home recovery and fresh screenshots")
    ap.add_argument("--max-state-rounds", type=int, default=3)
    ap.add_argument("--state-only", action="store_true", help="only classify the screen, do not locate")
    ap.add_argument("--live", action="store_true", help="take the initial screenshot from the phone via --adb")
    ap.add_argument("--home-cmd", help="shell command (run via adb shell) to jump to the task home; overrides the flow default")
    args = ap.parse_args()
    # with --live there is no screenshot file, so a lone positional is the target
    if args.live and args.target is None and args.screenshot is not None:
        args.target, args.screenshot = args.screenshot, None
    if args.expect and args.expect not in STATE_SETS[args.flow]["states"]:
        ap.error("unknown state %r for flow %r (states: %s)" % (args.expect, args.flow, ", ".join(STATE_SETS[args.flow]["states"])))
    if args.live and not args.adb:
        ap.error("--live needs --adb")
    if args.state_only and not args.expect:
        ap.error("--state-only needs --expect")
    if not args.state_only and not args.target:
        ap.error("target is required unless --state-only")
    if not args.screenshot and not args.live:
        ap.error("screenshot file is required unless --live")

    t_start = time.time()
    key = get_key()
    workdir = args.workdir or (os.path.dirname(os.path.abspath(args.screenshot)) if args.screenshot else os.getcwd())
    os.makedirs(workdir, exist_ok=True)
    if args.live:
        stem = "live"
        shot = os.path.join(workdir, "live.png")
        adb_shot(args.adb, shot)
        src = Image.open(shot).convert("RGB")
    else:
        stem = os.path.splitext(os.path.basename(args.screenshot))[0]
        src = Image.open(args.screenshot).convert("RGB")
    work = to_work(src)
    ww, wh = work.size
    debug = {}

    # state guard: verify the screenshot is the screen the locate step
    # expects; recover with Back / jump-home, or fail closed (no tap point).
    state_check = None
    state_tokens_total = 0
    if args.expect or args.state_only:
        flow = STATE_SETS[args.flow]
        depth = flow["depth"]
        actions = []
        ok = False
        observed = None
        for rnd in range(args.max_state_rounds + 1):
            sc = classify_state(key, work, args.flow)
            observed = sc["label"]
            state_tokens_total += sc["tokens"]
            state_check = {"expected": args.expect, "observed": observed,
                           "observed_conf": sc.get("confidence"),
                           "raw": sc.get("raw"),
                           "actions": list(actions), "rounds": rnd,
                           "seconds": sc["seconds"], "tokens": sc["tokens"]}
            if observed == args.expect:
                ok = True
                break
            if observed in depth and args.expect in depth and depth[observed] > depth[args.expect]:
                act = "back"
            elif observed in depth and args.expect in depth:
                state_check["fail_reason"] = ("shallower: on %s but expected %s; "
                    "enter it first (e.g. tap the row), the guard cannot do that" % (observed, args.expect))
                break
            else:
                act = "home"
            if not args.adb:
                state_check["fail_reason"] = "no --adb given, cannot recover from %s" % observed
                break
            if act == "back":
                adb_cmd(args.adb, "shell", "input", "keyevent", "4")
            else:
                adb_cmd(args.adb, "shell", *shlex.split(args.home_cmd or flow["home_cmd"]))
            actions.append(act)
            time.sleep(1)
            fresh = os.path.join(workdir, "%s_state_r%d.png" % (stem, rnd + 1))
            adb_shot(args.adb, fresh)
            stem = os.path.splitext(os.path.basename(fresh))[0]
            work = to_work(Image.open(fresh).convert("RGB"))
            ww, wh = work.size
        state_check["ok"] = ok
        if args.state_only:
            print(json.dumps({"state_check": state_check}, indent=2))
            return 0 if ok else 1
        if not ok:
            print(json.dumps({"state_check": state_check}, indent=2))
            print("STATE GUARD FAILED: expected %s, observed %s (%s)" % (
                args.expect, observed, state_check.get("fail_reason", "recovery exhausted")), file=sys.stderr)
            return 1

    # stage 1: coarse grid over the whole screenshot
    grid1 = draw_grid(work, 40, 25)
    if not args.no_debug:
        p1 = os.path.join(workdir, stem + "_stage1_grid.jpg")
        grid1.save(p1, quality=92)
        debug["stage1_image"] = p1
    intro1 = ("This is a phone screenshot with a red grid overlay. "
              "The grid has 40 columns numbered 0 to 39 along the top edge and "
              "25 rows numbered 0 to 24 along the left edge. Each cell is one grid "
              "square. Column 0 is the leftmost, row 0 is the topmost.")
    s1 = ask(key, grid1, intro1, args.target, 40, 25, row_only=args.row_only)
    cw, ch = ww / 40, wh / 25
    cx = (s1["col"] + 0.5) * cw if "col" in s1 else args.x_frac * ww
    cy = (s1["row"] + 0.5) * ch

    # stage 2: crop around the coarse pick, fine grid
    size = min(args.crop, ww, wh)
    x0 = int(max(0, min(ww - size, cx - size / 2)))
    y0 = int(max(0, min(wh - size, cy - size / 2)))
    crop = work.crop((x0, y0, x0 + size, y0 + size))
    grid2 = draw_grid(crop, 10, 10)
    if not args.no_debug:
        p2 = os.path.join(workdir, stem + "_stage2_crop.jpg")
        grid2.save(p2, quality=92)
        debug["stage2_image"] = p2
    intro2 = ("This is a cropped part of a phone screenshot, with a red grid overlay. "
              "The grid has 10 columns numbered 0 to 9 along the top edge and "
              "10 rows numbered 0 to 9 along the left edge. Each cell is one grid "
              "square. Column 0 is the leftmost, row 0 is the topmost.")
    s2 = ask(key, grid2, intro2, args.target, 10, 10, row_only=args.row_only)
    chosen = {"s": s2, "x0": x0, "y0": y0, "size": size}
    # Guard: a low-confidence pick, or a pick on the crop edge, may mean the
    # target is cut off or confused with a neighbour (round 4 test: the icon
    # pick landed on the "+" sliver at the crop's right edge). Retry once with
    # a 1.5x crop around the same centre for more context, keep the better.
    def min_conf(s):
        cs = [v for k, v in s.items() if k.endswith("_conf") and v is not None]
        return min(cs) if cs else 0.0
    def on_edge(s):
        if args.row_only:
            return s.get("row") in (0, 9)
        return s.get("col") in (0, 9) or s.get("row") in (0, 9)
    retry = None
    if min_conf(s2) < 0.45 or on_edge(s2):
        size2 = min(round(size * 1.5), ww, wh)
        x02 = int(max(0, min(ww - size2, cx - size2 / 2)))
        y02 = int(max(0, min(wh - size2, cy - size2 / 2)))
        crop2 = work.crop((x02, y02, x02 + size2, y02 + size2))
        grid2b = draw_grid(crop2, 10, 10)
        if not args.no_debug:
            p2b = os.path.join(workdir, stem + "_stage2_retry.jpg")
            grid2b.save(p2b, quality=92)
            debug["stage2_retry_image"] = p2b
        s2b = ask(key, grid2b, intro2, args.target, 10, 10, row_only=args.row_only)
        retry = {"s": s2b, "x0": x02, "y0": y02, "size": size2,
                 "reason": "low_conf" if min_conf(s2) < 0.45 else "edge"}
        if min_conf(s2b) > min_conf(s2):
            chosen = retry
    s2 = chosen["s"]
    x0, y0, size = chosen["x0"], chosen["y0"], chosen["size"]
    cell = size / 10
    if args.row_only:
        ix = args.x_frac * ww
    else:
        ix = x0 + (s2["col"] + 0.5) * cell
    iy = y0 + (s2["row"] + 0.5) * cell
    px = round(ix * PHONE_W / ww)
    py = round(iy * PHONE_H / wh)

    total_tokens = s1["tokens"] + s2["tokens"] + (retry["s"]["tokens"] if retry else 0) + state_tokens_total
    result = {
        "target": args.target,
        "mode": "row" if args.row_only else "point",
        "phone": [px, py],
        "stage1": s1,
        "stage2": s2,
        "stage2_retry": retry["s"] if retry else None,
        "retried": bool(retry),
        "state_check": state_check,
        "seconds": round(time.time() - t_start, 2),
        "tokens": total_tokens,
        "cost_usd": round(total_tokens * PRICE_PER_MTOK / 1_000_000, 6),
        "debug": debug,
    }
    print(json.dumps(result, indent=2))
    if not args.json:
        print("TAP phone=(%d,%d) stage1=(%s,%s) stage2=(%s,%s)%s %.1fs $%.6f" % (
            px, py,
            s1.get("col", "-"), s1.get("row", "-"),
            s2.get("col", "-"), s2.get("row", "-"),
            " [retried: %s]" % retry["reason"] if retry else "",
            result["seconds"], result["cost_usd"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
