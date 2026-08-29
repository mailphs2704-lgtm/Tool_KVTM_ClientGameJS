# AUTO KVTM PRO clean packaging bundle

`BUILD_CLEAN_BUNDLE.bat` creates a fresh `AUTO_KVTM_PRO_CLEAN` directory from a whitelist of the currently active runtime files.

The clean bundle includes:

- recovered Python/PyInstaller runtime: `_internal`, `runtime`
- AUTO assets and icon: `assets`
- bundled ADB: `platform-tools`
- launcher support files: `launchers`, `patches`
- active AUTO launcher: `local_launcher.py`, `local_launcher_v10.py`
- active local bridges: `local_bridge.py`, `local_options_bridge_v08.py`, `local_settings_bridge.py`, `local_function_actions_bridge_v5.py`
- local API replacement and branding helpers
- active Web stack only: `server.js`, `proxy_v10.js`, `public_gateway.js`, `function_catalog.json`, `public/`
- current RUN/STOP BAT launchers

It intentionally does not copy old launcher/bridge/proxy versions, recovery notes, diagnostics, Git metadata, user/session data, bridge tokens, local databases, logs, temporary files, or backups.

The builder verifies key runtime files, confirms recovered `.pyc` files exist, then writes `BUNDLE_MANIFEST.txt` and `BUNDLE_SHA256.txt` into the output directory.

## Run

From the repository root:

```bat
packaging\BUILD_CLEAN_BUNDLE.bat
```

Output:

```text
AUTO_KVTM_PRO_CLEAN\
```

## Packaging boundary

This clean directory is the input for the final Windows executable/installer build. At this stage the existing development launchers can still resolve Python 3.11 and Node.js from Windows. The final packaging phase must bundle/freeze those runtimes so another PC does not need to install them manually.

Do not put existing `local_data` or `web_control/data` from a working machine into a distributable package; they can contain machine/user-specific state.
