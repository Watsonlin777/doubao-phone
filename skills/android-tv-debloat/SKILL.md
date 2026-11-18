---
name: android-tv-debloat
description: "Turn your Android phone into an ADB debug server for your Android TV, then debloat the TV (disable its ad, telemetry and bloatware apps, reversible) and install a clean launcher, removing the TV's own home-screen ads. The phone relays the TV's ADB port to your server; the agent probes the TV, lists packages, asks you before disabling anything, and can restore it all with one command."
version: 1.0.17
author: Watsonlin777
license: MIT
platforms: [linux]
tags: [Android TV, Google TV, adb, debloat, adblock, launcher, Termux, relay]
permissions:
  shell: true
prerequisites:
  commands: [python3, ssh, git, docker, autossh]
  scripts: [scripts/phone/tv-relay.sh, scripts/server/tv-forward.sh]
---

# Debloat Your Android TV Through Your Phone

Your TV and your phone speak the same debug bridge (adb). This skill turns your
Android phone into the ADB debug server for your TV: the phone sits on the same
Wi-Fi as the TV and relays the TV's ADB port to your Linux server, so an AI
agent on the server can debloat the TV and install a clean launcher — without
a computer next to the TV, without root, and without uninstalling anything.

The debloat itself is `pm disable-user` (disable, not uninstall), so every step
is reversible with one restore command. A clean launcher replaces the ad-filled
home screen. The agent never disables anything without showing you the list and
getting your confirmation first.

## Read first — two parts, two sources

This skill has two parts from two sources. Do not confuse them.

- **The relay + operating spec (this package).** The phone-as-debug-server
  architecture, the relay and forwarding templates in `scripts/`, and the
  step-by-step rules in this file (backup first, confirm before disabling,
  never leave the TV without a Home app, verify after every step, restore on
  request). These are written by the author of this skill.
- **The debloat tooling (CleanYourTV, not in this package).** The pure-Python
  ADB client (`tools/tv.py`), the relay (`tools/relay.py`), the disable /
  restore scripts (`tools/disable.sh`, `tools/restore.sh`), the per-model
  debloat lists (`examples/`), and the launcher source come from
  CleanYourTV (Gathin23/cleanyourtv, https://github.com/Gathin23/cleanyourtv).
  Clone that repo separately and read its LICENSE; this skill does not bundle
  its code. Pin the version this skill was written against — commit
  `c2d6e79381add9daa83e116882f6d6b130dc4a73` (`git clone` then
  `cd cleanyourtv` then `git checkout
  c2d6e79381add9daa83e116882f6d6b130dc4a73`) — so an upstream
  change to a tool's command line does not break this skill. The stock
  `adb` binary is only needed for the Wireless-debugging pairing fallback
  (Part 1 step 5); the main flow uses tv.py (pure Python) and `ssh` for
  the server forward. This skill is the agent-operated workflow around it:
  it tells the agent how to drive those tools through the phone relay,
  what to ask you, and what never to touch.

## When to use this

- You have an Android TV or Google TV that shows sponsored rows, ads, or
  preloaded apps you never asked for, and you want a clean home screen.
- You have an Android phone on the same Wi-Fi as the TV, and a Linux server
  or machine (the agent runs there; the phone is the bridge, not the brain).
- You want the debloat done by an agent, but with you confirming the exact
  list before anything is disabled, and a one-command restore if you change
  your mind.

## When NOT to use this

- On a TV you do not own, or a TV whose owner has not consented. Every adb
  command here targets only the TV you configure.
- On a Samsung (Tizen), LG (webOS), Roku, Vizio, or Hisense VIDAA TV. They
  have no ADB, so this skill cannot run there at all.
- As a way to keep ADB debugging switched on unattended. When the run is
  done, turn debugging off on the TV and verify the port is closed
  (CleanYourTV ships `tools/adb-closed.py` for that check).
- As a substitute for the TV's own security: the "Allow USB debugging?"
  prompt on the TV authorises one adb key. Accept it only for your own
  server's key (the tv.py client on the server), and revoke it from
  Developer options if you stop using this skill.

## How it works

```
TV (Android TV / Google TV, ADB debugging on, same Wi-Fi)
  <- ADB port 5555 (or the Wireless-debugging port) ->
Phone (Termux + Python 3, same Wi-Fi)
  runs the relay: a local port on the phone forwards to the TV's ADB port
  <- reverse SSH tunnel (phone dials out, server connects back) ->
Linux server
  forwards the phone's relay port to server localhost
    -> the agent runs CleanYourTV tools/tv.py against server localhost
      -> probe, list packages, disable, install launcher, verify
```

Why the phone is the bridge: the TV sits on your home LAN, and the server
cannot reach it directly. The phone is already on that LAN, so it relays.
No port forwarding on your router, nothing exposed to the internet. The
phone only forwards TCP; the debloat logic and the launcher build run on
the server, where Python and Docker live.

## Part 1 — TV side: enable debugging and authorise once

1. On the TV: Settings -> Device Preferences -> About -> press OK on **Build**
   seven times to enable Developer options.
2. Back to Developer options -> turn on **USB debugging**. If the TV shows a
   **Network debugging** or **Wireless debugging** toggle, turn that on too.
   Keep the TV on.
3. Note the TV's IP address (Settings -> Network, or the Wireless-debugging
   screen). This IP goes into the phone's relay template as `TV_HOST`
   (Part 2 step 2) — it is the TV's address on your home LAN. The server's
   tv.py never uses this IP directly; it always connects to the local
   forward as `TV_HOST=127.0.0.1` (Part 3). Do not confuse the two.
4. The first time the agent connects, the TV shows **"Allow USB debugging?"**
   with the ADB client's key fingerprint. The key belongs to the ADB client
   on the server (CleanYourTV `tools/tv.py`); the phone relay only forwards
   the connection and has no key of its own. Accept it on the TV with the
   remote (tick "Always allow from this computer" only for your own
   server's key). This is a one-time manual step; the agent cannot click it
   for you. If you later run the tools from a different machine, its key is
   different and the TV will ask again.
5. If the TV only offers Wireless debugging with a pairing code (some
   Chromecast / Google TV Streamer sets do), pair it once with the stock
   `adb` from the phone or server (if `adb` is not installed, install it
   first: `pkg install android-tools` in Termux, `apt install adb` on the
   server), then either run `adb tcpip 5555` (lasts until the TV reboots)
   or point the tools at the Wireless-debugging port the TV screen shows.
   CleanYourTV documents both in `tools/native-adb.md` and Troubleshooting.

## Part 2 — Phone side: the debug server (relay)

Template: `scripts/phone/tv-relay.sh` (placeholders only).

1. On the phone in Termux, install Python 3 and git if they are not there
   (`pkg install python git`), then clone CleanYourTV and check out the
   pinned commit from "Read first" (`git clone
   https://github.com/Gathin23/cleanyourtv && cd cleanyourtv && git checkout
   c2d6e79381add9daa83e116882f6d6b130dc4a73`) or copy its `tools/` folder
   to the phone.
2. Fill in the template's placeholders: the TV's IP (`TV_HOST`) and ADB
   port. Usually this is `5555`, but many Google TV sets keep 5555 closed
   and only offer Wireless debugging with a pairing code (see Part 1
   step 5) — then the port is the one the Wireless-debugging screen shows,
   and the relay forwards to that port instead. The relay forwards to
   whatever port you put here, so get this right before starting it.
3. Run the template. It starts the relay (CleanYourTV `tools/relay.py`)
   listening on the phone's localhost (e.g. `127.0.0.1:15555`) and forwarding
   to the TV's ADB port. It prints the relay port; the server needs it.
4. The relay is a lightweight TCP forward. Keep it running in Termux (with a
   wake lock, the same way you keep a reverse tunnel alive). Also exempt
   Termux from battery optimization (Settings -> Apps -> Termux -> Battery
   -> Unrestricted, or allow background activity), otherwise Android may
   kill the relay while it sits in the background. If the phone
   reboots or changes network, restart the relay and re-check the TV's IP.
5. The phone also needs its reverse SSH tunnel to the server running (the
   same tunnel you use for remote adb to the phone). The server reaches the
   relay through that tunnel; nothing else needs to be open on the phone.
   If you do not have such a tunnel yet, set one up first: on the phone
   in Termux, install `openssh` and `autossh` (`pkg install openssh
   autossh`), start the phone's sshd (`sshd`, port 8022), generate an SSH
   key and add its public key to the server, then run (with
   `termux-wake-lock` first) `autossh -M 0 -N
   -o ServerAliveInterval=30 -o ServerAliveCountMax=3
   -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new
   -i ~/.ssh/<your-key> -R <TUNNEL_PORT>:localhost:8022
   <SERVER_USER>@<SERVER_HOST>`. The tunnel alone is not enough: the
   server also needs its own SSH key whose public key is in the phone's
   `~/.ssh/authorized_keys` — that is the key the server template's
   `PHONE_KEY` points to, and without it the server cannot SSH back
   through the tunnel to reach the relay. The `<TUNNEL_PORT>` here is
   the same port the server template's `TUNNEL_PORT` expects.

## Part 3 — Server side: forward the relay and probe the TV

Template: `scripts/server/tv-forward.sh` (placeholders only).

1. On the server, confirm the phone's reverse tunnel is up (the
   tv-forward.sh script checks this in its step 1). The relay itself is
   verified by the probe in step 5 — if the probe returns the TV's model,
   the relay is up and reachable; do not try to check the relay's
   listener separately.
2. Forward the phone's relay port to server localhost. **Bind localhost
   only — never bind this forward to a public interface.** The template
   does this through the existing reverse tunnel. The template's
   `PHONE_RELAY_PORT` must equal the phone relay's `RELAY_PORT`
   (both default to 15555); if you change one, change the other.
3. Export the connection settings in the server shell you run all
   CleanYourTV tools from:
   `export TV_HOST=127.0.0.1 TV_PORT=15555`
   (`TV_PORT` is the template's `SERVER_LOCAL_PORT`, default 15555.)
   Every CleanYourTV tool reads these from the environment — tv.py
   directly, and disable.sh, restore.sh, check.py, adb-closed.py and
   build-and-install.sh through their internal tv.py calls. The export is
   a convenience so you do not have to repeat the prefix on every
   command: every CleanYourTV command in this skill also carries the same
   values as a prefix, so each one works even in a fresh shell where the
   export was never run.
4. Set up CleanYourTV on the server. Clone the repo and check out the
   pinned commit from "Read first" (`git clone
   https://github.com/Gathin23/cleanyourtv && cd cleanyourtv && git checkout
   c2d6e79381add9daa83e116882f6d6b130dc4a73`), then create a virtual
   environment and install the tools' dependencies (`python3 -m venv
   tools/venv && tools/venv/bin/pip install -r tools/requirements.txt`).
   If `python3 -m venv` fails with "ensurepip is not available", the
   system is missing `python3-venv`: install it first (Debian/Ubuntu:
   `apt install python3-venv`), then re-run the venv command.
   The probe and every later CleanYourTV command run from this checkout,
   using its venv Python (`tools/venv/bin/python`). The commands in this
   skill use relative paths (`tools/...`, `launcher/...`), so if you open
   a new shell, `cd` into this checkout (`cleanyourtv/`) first.
5. Probe the TV through the forward. With the tools set up in step 4:
   `TV_HOST=127.0.0.1 TV_PORT=15555 tools/tv.py --probe` (model, Android
   version, firmware). `TV_PORT` must be the server's local forward port
   (the template's `SERVER_LOCAL_PORT`, default 15555) — tv.py defaults
   to port 5555, so without `TV_PORT` the probe would connect to the
   wrong port and fail. If the probe fails, stop and find out why before
   doing anything else. Check in this order: the TV is on; the reverse
   tunnel is up and the server forward is established (re-run the
   tv-forward.sh script — its step 1 checks the tunnel and its step 2
   checks the forward; the tunnel and forward can drop after they were
   first set up); the relay is running
   on the phone (check the Termux session on the phone, or ask the user —
   the probe itself is the test: if the probe succeeds, the relay is
   running); the TV's IP has not changed. If those are all fine and
   the probe still fails with "cannot reach", the TV's port 5555 is
   probably closed — many Google TV sets keep it closed. Fall back to the
   Wireless-debugging pairing flow in Part 1 step 5: pair once with the
   stock `adb`, then either run `adb tcpip 5555` (lasts until the TV
   reboots) or point the relay at the Wireless-debugging port the TV
   screen shows and re-run the probe. Do not proceed to disabling
   anything on a failed probe.
6. List the TV's packages: `TV_HOST=127.0.0.1 TV_PORT=15555 tools/tv.py 'pm list packages'` (same `TV_PORT` as the probe). Save the
   output as the backup (see "Safety rules"). This list is also what the
   agent matches against the per-model debloat lists in
   CleanYourTV `examples/` to propose what to disable.

## Part 4 — Debloat: propose, confirm, disable, install, verify

Do these in order, and do not skip the confirmation step.

1. **Backup.** Before disabling anything, save the package list and the
   TV's relevant settings (the `tools/tv.py` probe output and the full
   `pm list packages` output) to a dated file on the server. This record
   is the reference for proposing the disable list and for auditing what
   changed; the restore step itself uses the recovery record that
   `tools/disable.sh` writes when it runs, not this file.
2. **Propose.** Match the TV's package list against the per-model lists in
   CleanYourTV `examples/` (or run `python3 tools/match.py <saved-list-file>`
   on the saved list, which reports for each package how many lists
   disable it and how many keep it). Build a proposed disable list, grouped
   by what each package
   does (ad service, telemetry, preloaded app, content row). Save the
   proposed list as a text file, one package per line, in the same format
   as the `examples/` debloat lists (`#` for a comment; a line starting
   with `#` means keep that package). Entries must be bare package names —
   when you take a package from the `pm list packages` output, strip the
   `package:` prefix (the disable script refuses the whole list if an
   entry is not a bare package name). Mark anything
   the agent is unsure about as "ask the user", not "disable".
3. **Confirm.** Show the user the proposed list (package id + what it is +
   why it is proposed) and wait for their confirmation. The user may
   remove items or add "keep" items. **Nothing is disabled before this
   confirmation.** If the user does not confirm, stop the run.
4. **Disable.** Save the confirmed list to a file (same format as step 2)
   and apply it with CleanYourTV
   `TV_HOST=127.0.0.1 TV_PORT=15555 tools/disable.sh <list-file>` (or the
   equivalent `pm disable-user` calls through `tools/tv.py`). Use
   `pm disable-user` only — never uninstall a system package, never
   `pm uninstall` a preloaded app. The disable script refuses to leave
   the TV without a Home app (see "Safety rules").
5. **Install the launcher.** First check CleanYourTV's Releases page for a
   prebuilt launcher APK — if one is attached, use it and skip the build.
   The APK is a standalone app and does not need to match the pinned
   tools version; if you want a matched set, build the launcher from the
   pinned commit's source instead. Otherwise build the clean launcher on
   the server
   (`tools/docker-build.sh launcher` builds it in Docker, so the server needs
   only Docker; or build with a local JDK 17-22 + Android SDK platform 34).
   The Docker build downloads the Android SDK (several GB) and runs a
   Gradle build, so the server needs enough free disk and memory for it —
   a small 2 vCPU / 2 GiB server is tight; if the build fails for lack of
   memory or disk, use the prebuilt APK instead. Whichever way you got the
   APK (prebuilt download, or `tools/docker-build.sh launcher`), it must be at
   `launcher/app/build/outputs/apk/release/app-release.apk` (the Docker
   build puts it there; a downloaded APK must be placed there by hand),
   and install it with `SKIP_BUILD=1` — that tells
   `launcher/build-and-install.sh` to use the APK you already have instead
   of rebuilding it with Gradle (which would need a local JDK + Android
   SDK on the server): `SKIP_BUILD=1 TV_HOST=127.0.0.1 TV_PORT=15555 launcher/build-and-install.sh`.
   Only if you are building natively with Gradle do you run
   `build-and-install.sh` without `SKIP_BUILD=1`, letting it build the APK
   itself. The script rolls back if Home does not land on the new launcher.
6. **Verify.** After the install, confirm: the new launcher answers HOME
   (press Home and check the screen), the disabled packages stay disabled
   (`TV_HOST=127.0.0.1 TV_PORT=15555 tools/tv.py 'pm list packages -d'`),
   and a screenshot of the home screen shows the clean launcher. If any
   check fails, stop and restore.
7. **Restore (on request or on failure).** `TV_HOST=127.0.0.1 TV_PORT=15555 tools/restore.sh <list-file>`
   (the same list file used for the disable) undoes the disable, using the
   recovery record `tools/disable.sh` wrote, and returns the stock
   launcher. One command, no re-flashing. If the user changes their mind
   later, run it and the TV goes back.

## Safety rules (read before any disable)

- **Backup first, disable second.** No disable runs without a saved package
  list and probe output from this same run. If the backup is missing, stop.
- **Never leave the TV without a Home app.** Only disable a stock launcher
  the tools recognise, and only after another launcher answers HOME. If the
  disable list contains the app that owns Home and no other app on the TV
  answers HOME, skip that entry and say why. This is CleanYourTV's own
  Home guard; the agent must not bypass it (no `FORCE_HOME=1` without the
  user explicitly asking for it after the new launcher is Home).
- **Confirm before disabling.** The user confirms the exact list. A list
  the user has not seen is never applied. If the TV's model has no
  per-model list in `examples/`, the agent discovers the bloat itself and
  asks the user about each item before touching it.
- **`pm disable-user` only.** Never uninstall a system or preloaded package.
  Disabling is reversible; uninstalling a system package is not reliably
  reversible without a factory reset.
- **Never disable a package `match.py` marks as `never`.** Android core
  packages show as `never` in `tools/match.py` — they are not bloat and
  must never be disabled. The same goes for the TV's Settings app, its
  input method, and its system UI components. If a package looks like
  bloat but you cannot tell what it does, ask the user; do not guess.
- **One run, one list.** Do not re-run the disable step on a TV that was
  already debloated without re-probing and re-confirming first. After a
  firmware update, re-probe and use `TV_HOST=127.0.0.1 TV_PORT=15555 tools/check.py --fix` to re-apply only
  what the update undid, after showing the user what changed.
- **Only your own TV.** Every adb command targets the TV the user
  configured (the one whose IP went into the phone relay). Never probe,
  list, or disable on a TV that is not theirs.
- **Turn debugging off when done.** After the run, turn off USB / Network
  debugging on the TV and verify the ADB port is closed
  (`TV_HOST=127.0.0.1 TV_PORT=15555 tools/adb-closed.py`). The TV should not sit with debugging open.
- **Fail closed.** A failed probe, a failed install, or a Home check that
  does not land on the new launcher stops the run. Do not retry a disable
  or an install blindly; report the failure and the last verified state.
- **If the connection drops mid-run, reconcile before continuing.** The
  chain has two hops (server -> phone tunnel -> relay -> TV), and the
  phone tunnel can drop. If the relay, tunnel, or forward drops while a
  disable is in progress, do not re-run the disable blindly. First
  re-establish the connection, re-probe the TV, and run
  `TV_HOST=127.0.0.1 TV_PORT=15555 tools/tv.py 'pm list packages -d'` to
  see which packages are actually disabled.
  Compare that against the backup record and the confirmed list. Only then
  decide: resume disabling the remaining items, or run
  `TV_HOST=127.0.0.1 TV_PORT=15555 tools/restore.sh` first and start over. Resuming the remaining items
  from the list the user already confirmed needs no fresh confirmation;
  if the reconciliation shows the TV's actual state has diverged from
  that confirmed list, show the user the corrected list and re-confirm
  before disabling anything more. A half-applied list must be
  reconciled, not re-applied on top of an unknown state.

## Verification checklist

- [ ] TV is Android TV / Google TV (model confirmed, not Tizen / webOS /
      Roku / VIDAA)
- [ ] TV and phone on the same Wi-Fi; TV's IP recorded
- [ ] "Allow USB debugging?" accepted on the TV (one-time, on the TV)
- [ ] Relay running on the phone (Termux) — verified by the probe below
- [ ] TV_HOST=127.0.0.1 and TV_PORT=15555 exported in the server shell
      (Part 3 step 3), or each command carries the prefix
- [ ] CleanYourTV set up on the server (repo cloned, pinned commit
      checked out, venv created, requirements installed — Part 3 step 4)
- [ ] Server forward binds localhost only; probe returns model + Android
      version + firmware
- [ ] Backup saved (package list + probe output, dated)
- [ ] Disable list shown to the user and confirmed (nothing disabled before
      this)
- [ ] `pm disable-user` only; no uninstall; Home guard not bypassed
- [ ] New launcher installed and answers HOME; screenshot shows the clean
      home screen
- [ ] Disabled packages still disabled (`TV_HOST=127.0.0.1 TV_PORT=15555 tools/tv.py 'pm list packages -d'`)
- [ ] Debugging turned off on the TV; ADB port verified closed

## Scope and limits (read before buying)

- **Supported TVs:** Android TV and Google TV only. Fire TV gets the
  debloat half only (Fire OS will not hand Home to a third-party launcher).
  A few China-market TCL sets refuse to install any launcher at all; their
  lists say so in the header.
- **Not supported:** Samsung (Tizen), LG (webOS), Roku, Vizio, Hisense
  VIDAA — no ADB, so this skill cannot run there.
- **Per-model lists:** the debloat list differs by brand and model. If your
  model has no list in CleanYourTV `examples/`, the agent discovers the
  bloat from your TV's package list and asks you about each item; that
  takes longer and needs your answers.
- **Firmware updates:** an update can re-enable disabled packages. Re-probe
  and re-apply with `TV_HOST=127.0.0.1 TV_PORT=15555 tools/check.py --fix` after an update.
- **Verification scope (honest):** the relay architecture in this skill is
  built on the author's own working phone-agent setup (a Linux server
  driving a real Android phone over adb through a reverse tunnel, live
  since 2026-10-25) and on CleanYourTV's published tooling, which is
  tested across hundreds of TV models by its contributors. That setup
  proves the server-to-phone hop; **the phone-to-TV relay hop in this
  skill specifically — the phone forwarding the TV's ADB port — has not
  been run yet.** **The end-to-end run of this exact skill — phone relay
  to a real TV, debloat list applied, launcher installed — has not been
  run yet.** Treat the first run on your TV as the verification run:
  follow the checklist, confirm the list, and keep the restore command
  ready. Do not treat this skill as a guarantee that every TV model will
  debloat cleanly.
- **What this skill does not do:** it does not remove ads inside
  third-party apps (it disables the TV's own ad/telemetry services and
  replaces the home screen); it does not block network ads (no DNS
  filtering); it does not root the TV or flash firmware.
- The adb / shell commands in this skill are its intended functionality:
  all commands target only the TV and phone you configure. No external
  network calls from this package; no secrets included. CleanYourTV's own
  tools are fetched from its repo under its own license — read it there.

## Attribution

Built on CleanYourTV (Gathin23/cleanyourtv,
https://github.com/Gathin23/cleanyourtv) for the ADB tooling, the debloat
lists, and the launcher. The phone-as-debug-server relay architecture and
the agent operating spec in this file are the author's own work. If you use
the CleanYourTV launcher and lists, credit that project and follow its
license for its code.
