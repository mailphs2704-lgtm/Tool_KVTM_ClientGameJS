from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRY = ROOT / "packaging" / "kvtm-tool-cry"
BUILD = CRY / "BUILD_KVTM_TOOL_CRY_RELEASE.ps1"
VERSION = CRY / "VERSION"
LAUNCHER_CS = CRY / "Kvtm_tool_Cry_Launcher.cs"
UPDATER_CS = CRY / "Kvtm_tool_Cry_Updater.cs"
BOOTSTRAP = CRY / "bootstrap"
LAUNCH = BOOTSTRAP / "Kvtm_tool_Cry_Launch.ps1"
UPDATE = BOOTSTRAP / "Kvtm_tool_Cry_Update.ps1"
RUNTIME = BOOTSTRAP / "Kvtm_tool_Cry_Runtime.ps1"
INSTALL = BOOTSTRAP / "Install-KvtmToolCry.ps1"
DEV_START = ROOT / "packaging" / "suite-v0.15" / "START_MULTI_DEV_SILENT.ps1"


def text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing Kvtm_tool_Cry packaging file: {path}")
    return path.read_text(encoding="utf-8-sig")


def require(body: str, token: str, message: str) -> None:
    if token not in body:
        raise AssertionError(message)


def forbid(body: str, token: str, message: str) -> None:
    if token in body:
        raise AssertionError(message)


def main() -> int:
    version = text(VERSION).strip()
    parts = version.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts):
        raise AssertionError(f"Stable VERSION must be numeric dotted version: {version!r}")

    build = text(BUILD)
    launcher_cs = text(LAUNCHER_CS)
    updater_cs = text(UPDATER_CS)
    launch = text(LAUNCH)
    update = text(UPDATE)
    runtime = text(RUNTIME)
    install = text(INSTALL)
    dev_start = text(DEV_START)

    # Product identity is stable/final; DEV remains a separate product/data root.
    for body, label in ((runtime, "runtime"), (update, "updater"), (install, "installer")):
        require(body, '$ProductName = "Kvtm_tool_Cry"', f"{label} product identity missing")
    require(runtime, 'Join-Path $env:APPDATA $ProductName', "Stable APPDATA root missing")
    require(runtime, '$env:KVTM_MULTI_INSTANCE_NAME = $ProductName', "Stable instance name missing")
    require(runtime, '$env:KVTM_MULTI_ISOLATED = "1"', "Stable isolation flag missing")
    require(runtime, '$env:KVTM_PRODUCT_CHANNEL = "stable"', "Stable channel marker missing")
    forbid(runtime, '"KVTM Multi DEV"', "Stable runtime reuses DEV instance/data name")
    require(dev_start, '$DataRoot = Join-Path $env:APPDATA "KVTM Multi DEV"', "DEV data root unexpectedly changed")

    # Installed Stable is versioned outside repo/dist. Pull/build is allowed to
    # rebuild only dist/Kvtm_tool_Cry-Runtime-BUILD and must not kill Stable.
    require(install, 'Join-Path $env:LOCALAPPDATA "Programs\\Kvtm_tool_Cry"', "Per-user Stable install root missing")
    require(build, '$BuildOutputName = "Kvtm_tool_Cry-Runtime-BUILD"', "Release build output is not isolated")
    require(build, 'Stable installed app is NOT an input/output of this build.', "Release build isolation marker missing")
    require(build, 'Stable running install was not stopped or modified.', "Release build completion isolation marker missing")
    forbid(build, 'Stop-Process -Name', "Release builder contains broad process kill")
    forbid(build, 'taskkill', "Release builder contains broad taskkill")

    # Runtime uses current.json -> versions/<version>, so an update never replaces
    # the files currently executing. Stable singleton is tracked in APPDATA.
    require(runtime, '$CurrentPath = Join-Path $InstallRoot "current.json"', "Runtime current pointer missing")
    require(runtime, 'Join-Path (Join-Path $InstallRoot "versions") $version', "Versioned runtime root missing")
    require(runtime, '$RuntimePidPath = Join-Path $DataRoot "runtime.pid.json"', "Stable runtime PID ownership missing")
    require(runtime, 'Test-CryRuntimeRunning', "Stable singleton guard missing")

    # Updater supports the same-PC local release channel now and HTTPS later.
    # It must be atomic, hash-verified, rollback-safe and refuse live mutation.
    require(update, 'if (Test-CryRuntimeRunning)', "Updater does not protect active Stable runtime")
    require(update, 'SKIP runtime is active; current running version is never modified', "Updater live-mutation guard marker missing")
    require(update, 'provider -eq "file"', "Local update provider missing")
    require(update, 'provider -eq "https"', "HTTPS update provider missing")
    require(update, 'Get-FileHash -LiteralPath $zipPath -Algorithm SHA256', "Update SHA256 verification missing")
    require(update, 'Update package SHA256 mismatch', "SHA256 fail-close missing")
    require(update, '$StagingRoot = Join-Path $InstallRoot "staging"', "Update staging root missing")
    require(update, 'Move-Item -LiteralPath $temp -Destination $Path -Force', "Atomic pointer write missing")
    require(update, 'if ($nextVersion -le $currentVersion)', "Monotonic version gate missing")
    require(update, 'launching last verified version', "Launcher rollback/fail-open marker missing")
    forbid(update.lower(), "authorization: bearer", "Updater must not embed GitHub/private bearer auth")
    forbid(update.lower(), "github_pat_", "Updater must not contain a GitHub PAT")
    forbid(update.lower(), "ghp_", "Updater must not contain a legacy GitHub PAT")

    # Installer seeds profiles/settings once but never imports process/runtime state.
    require(install, '$DevDataRoot = Join-Path $env:APPDATA "KVTM Multi DEV"', "First-install DEV settings seed missing")
    require(install, '@("profiles.json", "settings.json", "clear-stall-history.jsonl")', "Stable seed allowlist changed")
    forbid(install, 'running_clients.json', "Installer must not migrate DEV running process map")
    require(install, 'Kvtm_tool_Cry.lnk', "Stable desktop/start-menu shortcut missing")

    # User-facing executables are thin wrappers around auditable bootstrap scripts.
    require(launcher_cs, 'Kvtm_tool_Cry_Launch.ps1', "Main EXE launcher target missing")
    require(updater_cs, 'Kvtm_tool_Cry_Update.ps1', "Updater EXE launcher target missing")
    require(build, '-OutputType WindowsApplication', "Windows EXE bootstrap compilation missing")
    require(build, 'iexpress.exe', "Single-file Setup.exe builder missing")
    require(build, 'Kvtm_tool_Cry_Setup_$Version.exe', "Versioned installer output missing")

    print("KVTM_TOOL_CRY PACKAGING CONTRACT VERIFIED")
    print("identity=Kvtm_tool_Cry+stable-appdata+isolated-instance")
    print("install=localappdata-programs+versioned-runtime+current-pointer")
    print("update=file-or-https+sha256+staging+atomic-switch+rollback")
    print("dev-isolation=stable-running-not-stopped-by-release-build")
    print("security=no-embedded-github-token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
