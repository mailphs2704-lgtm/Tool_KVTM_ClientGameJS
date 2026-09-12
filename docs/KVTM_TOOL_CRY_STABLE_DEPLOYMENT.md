# Kvtm_tool_Cry — Stable deployment

## Product identity

- Product: `Kvtm_tool_Cry`
- Stable install root: `%LOCALAPPDATA%\Programs\Kvtm_tool_Cry`
- Stable persistent data: `%APPDATA%\Kvtm_tool_Cry`
- DEV repository/runtime stays independent: `D:\Tool_KVTM_Multi_DEV`
- DEV persistent data stays independent: `%APPDATA%\KVTM Multi DEV`

`Kvtm_tool_Cry` is the final/main product identity. `Stable` is an update channel, not part of the visible product name.

## Isolation contract

A normal DEV pull/build must not stop or modify an installed `Kvtm_tool_Cry` runtime.

The authoritative DEV builder writes under repo `dist\...`. The Stable product executes from `%LOCALAPPDATA%\Programs\Kvtm_tool_Cry\versions\<version>` and keeps settings/logs outside the repo.

Stable updates never overwrite the files of a running version. Update is checked before launch. If Stable is already running, updater exits without changing `current.json` or any version directory.

## First local Stable build

From repo root on branch `develop/multi-auto-dev`:

```bat
Kvtm_tool_Cry_RELEASE.bat
```

Default version is read from:

```text
packaging\kvtm-tool-cry\VERSION
```

The build reuses the authoritative full package builder and creates:

```text
dist\Kvtm_tool_Cry_Setup_<version>.exe
dist\Kvtm_tool_Cry-channel\Kvtm_tool_Cry-<version>.zip
dist\Kvtm_tool_Cry-channel\stable-manifest.json
dist\Kvtm_tool_Cry-channel\latest-build.json
```

The release build output is separate from both DEV runtime and installed Stable runtime.

## First install

Run:

```text
Kvtm_tool_Cry_Setup_<version>.exe
```

No administrator rights are required because the app installs per-user.

On first install only, these files may be copied from `%APPDATA%\KVTM Multi DEV` if Stable does not already own them:

- `profiles.json`
- `settings.json`
- `clear-stall-history.jsonl`

Runtime/process state such as `running_clients.json` is never migrated.

Desktop and Start Menu shortcuts are named:

```text
Kvtm_tool_Cry
```

## Local auto-update channel

Because the source repository is private, the updater must not embed a GitHub PAT/token.

The first installer built on the DEV PC configures a local file-provider channel pointing to:

```text
<repo>\dist\Kvtm_tool_Cry-channel\stable-manifest.json
```

Publishing a new approved Stable version means:

1. bump `packaging\kvtm-tool-cry\VERSION`;
2. pull/build/test DEV as usual;
3. run `Kvtm_tool_Cry_RELEASE.bat`;
4. leave the installed Stable runtime running if desired;
5. on the next Stable launch, updater sees the new manifest, verifies SHA-256, extracts into a new version directory, then atomically switches `current.json`.

The currently running Stable process is never forced to update or restart.

## HTTPS update channel later

Updater already supports provider `https`, but the manifest/package must be hosted at an HTTPS endpoint that does not require embedding a private repository credential.

A remote stable manifest must keep schema 1 and provide at least:

```json
{
  "schema": 1,
  "product": "Kvtm_tool_Cry",
  "channel": "stable",
  "version": "0.1.1",
  "source_head": "<git sha>",
  "package_url": "https://.../Kvtm_tool_Cry-0.1.1.zip",
  "package_sha256": "<64 lowercase hex chars>"
}
```

## Rollback model

Updater keeps the newly selected version plus the previously selected version. `current.json` is only replaced after the new archive passes SHA-256 and `.product.json` product/version verification.

If update check/download/verification fails during normal launch, launcher records the error and starts the last verified installed version.

## Release version rule

Never publish different source HEADs under the same Stable version. The release builder rejects that condition. Bump `VERSION` before publishing a new Stable build.
