# AUTO PRO uploaded clean boundary

This directory contains only the source-written boundary for the operator-owned
upload `autoproreal.zip`.

Authoritative upload SHA256:

`d3366f3e687fc3a3e2ecbc848ac160ed2452c39187e8009eb8b1d3d09de78328`

The package builder creates `AUTO_PRO_ORIGINAL` from a strict allowlist:

- recovered original `runtime/pyc`, `_internal`, and `assets`;
- this stateless offline/no-key adapter;
- Bridge V3 driver/loader/DLL.

It deliberately excludes the old AUTO_PRO sidecar launchers, Web Control,
platform-tools/ADB, clientjs_auto_patch, clean Multi workflows, profiles,
settings, logs, and telemetry databases.
