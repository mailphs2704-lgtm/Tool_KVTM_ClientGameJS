# AUTO KVTM PRO — PROJECT HANDOFF

Updated: 2026-08-26 (Asia/Bangkok, UTC+7)

This file is the durable handoff for future AI sessions. Read it before changing this project.

## How to resume

Read this file from repo `mailphs2704-lgtm/Tool_KVTM_Pro_coverByCry`, inspect current `main`, and continue from the newest confirmed state. Do not assume chat memory is available.

## Repository and fixed local paths

- Repo: `mailphs2704-lgtm/Tool_KVTM_Pro_coverByCry`
- Active branch: `main`
- WORK/development folder:
  `C:\Users\15130\Desktop\AUTO_KVTM_PRO_recovered_local_FIXED2\AUTO_KVTM_PRO_recovered_local`
- MASTER/release-staging folder:
  `C:\Users\15130\Desktop\AUTO_KVTM_PRO_MASTER`

Whenever giving CMD instructions, ALWAYS show an explicit `cd /d "..."` first so commands are not run in the wrong folder.

## CRITICAL WORK -> MASTER POLICY

The user explicitly requires this workflow:

```text
WORK
  -> edit / optimize / test
  -> user confirms PASS
  -> only then copy/promote the confirmed files to MASTER
  -> after the whole project is complete, test MASTER as a whole
  -> only after that package/distribute as EXE/installer
```

Rules:

1. All future repairs, experiments, Web optimization, bridge changes, launcher changes, and tests happen in WORK first.
2. Do NOT edit experimental code directly in MASTER.
3. Do NOT automatically mirror every WORK change into MASTER.
4. A changed component enters MASTER only after the user explicitly confirms it works/PASS.
5. MASTER is the clean release-staging source, not a development workspace.
6. Do not copy logs, caches, sessions, tokens, VM images, probe output, test artifacts, old version files, or unrelated development debris into MASTER.
7. Preserve known working dependencies even if filenames contain older version numbers when the current frontend actually loads them.
8. Before promoting a file, identify what changed and which dependent files must move with it.
9. After promotion, MASTER should remain independently auditable and suitable for final packaging.
10. Final EXE/installer packaging is DEFERRED until the Web + AUTO PRO integration and other requested project work are complete.

## Packaging status — STOPPED/DEFERRED

PyInstaller 6.22.2 was installed under local Python 3.11.9 and a temporary onedir experiment was created in WORK, but the user then explicitly said packaging is not needed yet.

Do NOT continue PyInstaller/EXE/installer work unless the user later asks to resume packaging.

Temporary packaging experiment files in WORK are not approved release artifacts and must NOT be promoted to MASTER merely because they exist. Examples include:

- `local_launcher_package_v1.py`
- `local_launcher_package_core_v1.py`
- `dist\AUTO_KVTM_PRO_TEST\...`
- PyInstaller build/spec output

When packaging is eventually resumed, the goal is that another Windows machine should not need to manually install Python/Node/libraries. Packaging must be done only after functional work is complete and MASTER passes an overall test.

## Current MASTER staging structure

MASTER was manually created outside the repo on Desktop. Current intended structure is approximately:

```text
AUTO_KVTM_PRO_MASTER\
  _internal\
  assets\
  launchers\
  local_data\
  packaging\
  platform-tools\
  runtime\
    pyc\
  web_control\
  local_api.py
  local_bridge.py
  local_launcher.py
  local_launcher_v10.py
  local_options_bridge_v08.py
  local_settings_bridge.py
  local_function_actions_bridge_v5.py
  local_ui_branding.py
```

Important: `_internal` must currently be at MASTER root because `local_launcher.py` resolves it as `ROOT / "_internal"`. `runtime\pyc` is also resolved relative to root.

The MASTER currently contains a baseline copied from the known working project. From now on, do not replace MASTER files until the corresponding WORK changes are tested and explicitly PASS.

## What the project is

AUTO KVTM PRO is a recovered local automation runtime originally packaged with PyInstaller/Python 3.11. The recovered project runs locally and has a Node.js Web Control that controls the SAME real launcher/TaskManager instance.

Architecture:

```text
Browser
  -> Node Web / proxy
  -> localhost Python bridges inside the real launcher process
  -> original TaskManager / Tk GUI variables
  -> ADB / emulator
```

Never create a second AUTO engine/TaskManager just for Web.

## Current priority

Current priority is NOT packaging. It is optimizing and completing Web <-> AUTO PRO integration in WORK while preserving all proven behavior.

After each completed Web/AUTO change:

1. test it in WORK;
2. wait for explicit user PASS;
3. promote only the required confirmed files to MASTER;
4. continue to the next change.

## Ports and security boundaries

- Public/local Web proxy: `127.0.0.1:8080`
- Web core: `127.0.0.1:18080`
- Main launcher bridge: `127.0.0.1:8766`
- AUTO option bridge: `127.0.0.1:8767`
- Settings popup bridge: `127.0.0.1:8768`
- Main-function action bridge: `127.0.0.1:8769`
- Public gateway: `127.0.0.1:8081`
- ADB normally: `127.0.0.1:5037`

Python bridges are localhost-only and token-protected. Never expose ADB 5037 or Python bridge ports directly to the Internet.

## Current launcher

Main launcher: `local_launcher_v10.py`.

It starts the real AUTO and attaches:

- `local_bridge`
- `local_options_bridge_v08`
- `local_settings_bridge`
- `local_function_actions_bridge_v5`

Fatal errors go to `local_data\launcher_error.log`.

`local_launcher.py` loads recovered bytecode from `runtime\pyc`, native/package data from `_internal`, and adds platform-tools to PATH.

Branding is handled by `local_ui_branding.py` using:

- `assets\icon\app.ico`
- fallback `assets\icon\icon.png`

## Web stack

Frontend: HTML5 + CSS + vanilla JavaScript.
Backend: Node.js built-in HTTP, no Express requirement.

Current main files:

- `web_control\server.js`
- `web_control\proxy_v10.js`
- `web_control\public_gateway.js`
- `web_control\public\*`

Do not assume files named `v07`, `v08`, `v09`, `v11`, `v102` under `web_control\public` are obsolete: the current `index.html` loads multiple versioned CSS/JS files. Remove one only after verifying it is no longer referenced and the UI still passes.

## Live View — DO NOT BREAK

The proven smooth Live View uses:

- Android `screenrecord --output-format=h264`
- Node streaming H.264 bytes
- browser WebCodecs decoding
- very small jitter queue
- dropping old frames instead of accumulating latency
- active device/tab streaming only
- view-only behavior

The user already confirmed H.264 Live View is smooth. Do not casually rewrite/revert this pipeline while doing unrelated Web/UI optimization.

Expected emulator display remains about `1000 x 1000`, `240 DPI`; Live View downscaling must not change emulator display configuration.

## Real task state

Web must read/control the actual launcher TaskManager. START/STOP and running-function state must continue to target the real launcher instance.

The main function selector uses live launcher `FUNCTION_OPTIONS` and validates option index + function ID + label before START. Do not replace it with a fake/static-only engine.

## AUTO options/settings

`local_options_bridge_v08` discovers real Tk Checkbutton/Tcl variables.

`local_settings_bridge` mirrors original popup settings by using the original Tk widgets/callbacks. Preserve original AUTO behavior rather than reimplementing business logic independently on Web.

`local_function_actions_bridge_v5.py` handles right-click/main-function actions while suppressing visible Tk menu posting. Do not revert to physically opening context menus for Web probing because previous attempts caused freezes/visible menus.

## PowerShell 5 compatibility

Hidden launcher `.ps1` files must remain ASCII-safe unless deliberately saved with a PowerShell-5-compatible encoding/BOM. UTF-8 without BOM previously caused Vietnamese mojibake/parser errors on this Windows machine.

## Public Web

Current public test architecture uses Cloudflare Quick Tunnel + localhost gateway. The gateway exists to validate/rewrite public Host/Origin and avoid CSRF origin failures.

Quick Tunnel URLs are temporary. A stable hostname remains future work; do not confuse that with current completed behavior.

## Authentication warning

Current Web testing authentication uses a fixed admin credential in the existing implementation. This is testing/personal-use state only. Before real multi-user Internet release, authentication/session/rate-limit handling must be strengthened and test credentials must not be shipped as final release defaults.

Do not print credentials/tokens/session contents into handoff notes, logs, responses, or packaging manifests.

## User workflow expectations

- Keep responses practical and concise.
- Give copy-ready Windows commands.
- ALWAYS include explicit `cd /d "..."` before CMD command groups.
- Avoid repeating already explained theory.
- Inspect existing implementation before editing.
- Do not claim a GitHub file/commit/change exists unless the action actually succeeded.
- Work on `main` unless explicitly told otherwise.
- Keep VM/emulator experimental work separate unless explicitly requested.

## Separate older repo

`mailphs2704-lgtm/Tool_KVTM_v2_coverByCry` is an older separate JavaScript AUTO project. Do not mix it with this recovered AUTO KVTM PRO unless explicitly requested.

## Resume checklist for future AI

Before doing any work:

1. Read this `PROJECT_HANDOFF.md`.
2. Inspect current `main` for newer commits/files.
3. Remember WORK is development; MASTER is PASS-only release staging.
4. Do not resume packaging unless the user asks.
5. Current priority is Web <-> real AUTO PRO optimization.
6. Preserve real TaskManager, H.264 Live View, localhost bridge security, and PowerShell 5 compatibility.
7. For every manual CMD instruction, state the full `cd /d` path first.
8. After a feature passes in WORK, ask/confirm before promoting its files to MASTER.
