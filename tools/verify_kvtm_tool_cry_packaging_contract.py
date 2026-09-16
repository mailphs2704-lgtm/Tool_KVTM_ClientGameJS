from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRY = ROOT / "packaging" / "kvtm-tool-cry"
BUILD = CRY / "BUILD_KVTM_TOOL_CRY_RELEASE.ps1"
SUITE_BUILD = ROOT / "packaging" / "suite-v0.15" / "BUILD_FULL_PACKAGE.ps1"
VERSION = CRY / "VERSION"
LAUNCHER_CS = CRY / "Kvtm_tool_Cry_Launcher.cs"
UPDATER_CS = CRY / "Kvtm_tool_Cry_Updater.cs"
BOOTSTRAP = CRY / "bootstrap"
LAUNCH = BOOTSTRAP / "Kvtm_tool_Cry_Launch.ps1"
UPDATE = BOOTSTRAP / "Kvtm_tool_Cry_Update.ps1"
RUNTIME = BOOTSTRAP / "Kvtm_tool_Cry_Runtime.ps1"
INSTALL = BOOTSTRAP / "Install-KvtmToolCry.ps1"
DEV_START = ROOT / "packaging" / "suite-v0.15" / "START_MULTI_DEV_SILENT.ps1"
MULTI = ROOT / "source-archive" / "multi-current" / "kvtm_multi_tool"
OWNED_HOST = MULTI / "kvtm_multi_owned_host.py"
DEV_HOST = MULTI / "kvtm_multi_dev_host.py"
FPS_HARDCAP = MULTI / "fps_hardcap_integration.py"
WINDOW_POSITION = MULTI / "clear_stall_window_position.py"
ORIGINAL_AUTO_INTEGRATION = MULTI / "original_auto_pro_integration.py"
UPLOADED_AUTO = ROOT / "source-archive" / "auto-pro-uploaded-clean"
UPLOADED_LAUNCHER = UPLOADED_AUTO / "cry_original_launcher.py"
UPLOADED_OFFLINE_API = UPLOADED_AUTO / "offline_api.py"


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


def without_full_line_comments(body: str) -> str:
    """Ignore descriptive PowerShell comments while keeping executable lines."""
    return "\n".join(
        line for line in body.splitlines()
        if not line.lstrip().startswith("#")
    )


def main() -> int:
    version = text(VERSION).strip()
    parts = version.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts):
        raise AssertionError(f"Stable VERSION must be numeric dotted version: {version!r}")

    build = text(BUILD)
    suite_build = text(SUITE_BUILD)
    launcher_cs = text(LAUNCHER_CS)
    updater_cs = text(UPDATER_CS)
    launch = text(LAUNCH)
    update = text(UPDATE)
    runtime = text(RUNTIME)
    install = text(INSTALL)
    install_code = without_full_line_comments(install)
    dev_start = text(DEV_START)
    owned_host = text(OWNED_HOST)
    dev_host = text(DEV_HOST)
    fps_hardcap = text(FPS_HARDCAP)
    window_position = text(WINDOW_POSITION)
    original_auto_integration = text(ORIGINAL_AUTO_INTEGRATION)
    uploaded_launcher = text(UPLOADED_LAUNCHER)
    uploaded_offline_api = text(UPLOADED_OFFLINE_API)

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

    # Release branch gate must trust the normalized branch name itself, not an
    # unreliable/stale LASTEXITCODE produced by a native Git command in a PS5.1
    # pipeline. Detached HEAD or a real wrong branch still fails by name.
    require(build, '$expectedBranch = "develop/multi-auto-dev"', "Stable release expected branch marker missing")
    require(build, 'rev-parse --abbrev-ref HEAD', "Stable release branch probe is not canonical")
    require(build, '[System.StringComparison]::OrdinalIgnoreCase', "Stable release branch comparison is not normalized")
    forbid(build, '$branchExit', "Stable release branch gate must not depend on unreliable LASTEXITCODE")
    require(build, '$VersionWasExplicit', "Stable release automatic-version intent missing")
    require(build, '$requestedVersion -le $previousVersion', "Stable release does not compare published version")
    require(build, '$previousVersion.Build + 1', "Stable release does not auto-increment patch")
    require(build, 'Stable source HEAD changed; auto version bump', "Stable auto-version operator log missing")

    # Runtime uses current.json -> versions/<version>, so an update never replaces
    # the files currently executing. Stable singleton is tracked in APPDATA.
    require(runtime, '$CurrentPath = Join-Path $InstallRoot "current.json"', "Runtime current pointer missing")
    require(runtime, 'Join-Path (Join-Path $InstallRoot "versions") $version', "Versioned runtime root missing")
    require(runtime, '$RuntimePidPath = Join-Path $DataRoot "runtime.pid.json"', "Stable runtime PID ownership missing")
    require(runtime, 'Test-CryRuntimeRunning', "Stable singleton guard missing")

    # Stable Python stdout/stderr is redirected to files. Force UTF-8 in the
    # child process so Vietnamese logs can never crash startup under cp1252.
    require(runtime, '$env:PYTHONUTF8 = "1"', "Stable runtime does not force Python UTF-8 mode")
    require(runtime, '$env:PYTHONIOENCODING = "utf-8"', "Stable runtime Python IO encoding is not UTF-8")
    require(runtime, '$env:PYTHONUNBUFFERED = "1"', "Stable runtime Python logging is not unbuffered")
    require(runtime, 'RedirectStandardOutput = $stdout', "Stable runtime stdout redirection missing")
    require(runtime, 'RedirectStandardError = $stderr', "Stable runtime stderr redirection missing")

    # Updater supports the same-PC local release channel now and HTTPS later.
    # It must be atomic, hash-verified, rollback-safe and refuse live mutation.
    require(update, 'if (Test-CryRuntimeRunning)', "Updater does not protect active Stable runtime")
    require(update, 'SKIP runtime is active; current running version is never modified', "Updater live-mutation guard marker missing")
    require(update, 'provider -eq "file"', "Local update provider missing")
    require(update, 'provider -eq "https"', "HTTPS update provider missing")
    require(update, 'if ([string]$manifest.channel -ne "stable")', "Stable manifest channel guard missing")
    require(update, 'Get-FileHash -LiteralPath $zipPath -Algorithm SHA256', "Update SHA256 verification missing")
    require(update, 'Update package SHA256 mismatch', "SHA256 fail-close missing")
    require(update, '$StagingRoot = Join-Path $InstallRoot "staging"', "Update staging root missing")
    require(update, 'Remove-Item -LiteralPath $target -Recurse -Force', "Existing target version is trusted instead of replaced")
    require(update, 'Move-Item -LiteralPath $temp -Destination $Path -Force', "Atomic pointer write missing")
    require(update, 'if ($nextVersion -le $currentVersion)', "Monotonic version gate missing")

    # Hidden bootstrap failures must be persisted and surfaced to the operator.
    require(launch, 'launching last verified version', "Launcher rollback/fail-open marker missing")
    require(launch, 'function Invoke-CryBootstrapChild', "Launcher child-process bootstrap helper missing")
    require(launch, 'Start-Process -FilePath "powershell.exe"', "Launcher does not isolate child bootstrap processes")
    require(launch, '$updateResult = Invoke-CryBootstrapChild -Script $UpdateScript -Label "update"', "Updater is not run as isolated child")
    require(launch, '$runtimeResult = Invoke-CryBootstrapChild -Script $RuntimeScript -Label "runtime"', "Runtime is not run as isolated child")
    require(launch, '("bootstrap-" + $Label + ".err.log")', "Bootstrap stderr is not persisted with a per-child label")
    require(launch, 'Read-LogTail', "Launcher does not append hidden bootstrap stderr to launcher.log")
    require(launcher_cs, 'MessageBoxW(', "Main EXE does not surface launch failure")
    require(launcher_cs, 'Kvtm_tool_Cry - Launch failed', "Main EXE failure dialog identity missing")
    require(launcher_cs, 'launcher.log', "Main EXE failure dialog does not point to launcher log")
    forbid(launch, '& $UpdateScript', "Launcher directly invokes updater; updater exit could terminate parent")
    forbid(launch, '& $RuntimeScript', "Launcher directly invokes runtime; runtime exit could terminate parent")
    forbid(update.lower(), "authorization: bearer", "Updater must not embed GitHub/private bearer auth")
    forbid(update.lower(), "github_pat_", "Updater must not contain a GitHub PAT")
    forbid(update.lower(), "ghp_", "Updater must not contain a legacy GitHub PAT")

    # Setup and every successful Stable version switch snapshot the exact safe
    # DEV configuration allowlist. Process/PID/runtime state stays isolated.
    require(install, '$DevDataRoot = Join-Path $env:APPDATA "KVTM Multi DEV"', "Setup DEV configuration source missing")
    require(install, '@("profiles.json", "settings.json", "clear-stall-history.jsonl")', "Stable setup sync allowlist changed")
    require(install, 'Copy-Item -LiteralPath $devFile -Destination $stableFile -Force', "Setup does not refresh DEV configuration")
    require(update, 'function Sync-DevPersistentConfiguration', "Updater DEV configuration sync missing")
    require(update, '@("profiles.json", "settings.json", "clear-stall-history.jsonl")', "Stable updater sync allowlist changed")
    require(update, 'Sync-DevPersistentConfiguration', "Updater does not sync configuration after switch")
    forbid(install_code, '"running_clients.json"', "Installer executable code must not migrate DEV running process map")
    forbid(without_full_line_comments(update), '"running_clients.json"', "Updater must not migrate DEV running process map")

    # Stable must launch the same current DEV host capabilities while retaining
    # its own product/data identity.
    require(owned_host, "from kvtm_multi_dev_host import main", "Stable does not launch current DEV host")
    require(owned_host, "install_clear_stall_window_position", "Stable fixed ClientJS position integration missing")
    require(owned_host, "install_fps_hardcap_integration", "Stable FPS hard-cap integration missing")
    require(owned_host, "import auto_builder_integration", "Stable pre-UI integration hook missing")
    require(owned_host, "_ORIGINAL_BUILDER_INSTALL", "Stable original builder install handle missing")
    require(
        owned_host,
        "auto_builder_integration.install_auto_builder_integration = (",
        "Stable builder install is not wrapped before DEV UI setup",
    )
    pre_ui_start = owned_host.index("def _install_pre_ui_runtime_integrations")
    pre_ui_end = owned_host.index("def _install_runtime_integrations", pre_ui_start)
    pre_ui_body = owned_host[pre_ui_start:pre_ui_end]
    if pre_ui_body.index("install_stall_speed_integration") > pre_ui_body.index(
        "_ORIGINAL_BUILDER_INSTALL"
    ):
        raise AssertionError("Stable shop-drag speed schema is installed after UI builder")
    hook_pos = owned_host.index(
        "auto_builder_integration.install_auto_builder_integration = ("
    )
    host_import_pos = owned_host.index("from kvtm_multi_dev_host import main")
    if hook_pos > host_import_pos:
        raise AssertionError("Stable pre-UI hook is installed after DEV host import")
    require(dev_host, "DWM Live View=OFF", "Stable/DEV host does not disable DWM Live View")
    require(dev_host, "install_auto_main_profile_settings", "Stable/DEV speed/profile settings integration missing")
    require(fps_hardcap, "OpenGL present governor", "Bridge V3 FPS governor missing")
    require(window_position, "top-right work area", "Fixed ClientJS position contract missing")
    require(
        owned_host,
        "install_original_auto_pro_integration",
        "Stable does not install the separate original AUTO PRO entry",
    )
    require(
        original_auto_integration,
        'package_root / "AUTO_PRO_ORIGINAL"',
        "Stable launcher still targets the modified AUTO_PRO runtime",
    )
    require(
        uploaded_launcher,
        "d3366f3e687fc3a3e2ecbc848ac160ed2452c39187e8009eb8b1d3d09de78328",
        "Uploaded AUTO PRO source identity is missing",
    )
    require(uploaded_launcher, "EngineDriver", "Uploaded AUTO PRO does not use Bridge V3 driver")
    require(uploaded_launcher, 'DEVICE_PREFIX = "CRYPROFILE:"', "Uploaded AUTO PRO device identity is still PID-based")
    require(
        uploaded_launcher,
        "return EngineDriver(profile_id, reference_size=(1000, 1000))",
        "Uploaded AUTO PRO does not bind Bridge V3 by stable profile identity",
    )
    require(uploaded_launcher, "ADB đã tắt", "Uploaded AUTO PRO does not fail closed on ADB")
    require(
        uploaded_launcher,
        "adb_controller.ADBController.openGame = clientjs_open_game",
        "Uploaded AUTO PRO still uses the emulator account/icon startup gate",
    )
    require(
        uploaded_launcher,
        'find_image("friend_off", threshold=0.9)',
        "ClientJS startup does not prove the in-game screen",
    )
    require(
        uploaded_launcher,
        "deadline = time.monotonic() + 90.0",
        "ClientJS startup proof is not bounded",
    )
    forbid(
        uploaded_launcher,
        'find_image("icon_game"',
        "Clean ClientJS adapter must not search emulator icon_game",
    )
    forbid(
        uploaded_launcher,
        'find_image("tai_khoan"',
        "Clean ClientJS adapter must not search emulator account icon",
    )
    forbid(uploaded_launcher, "import local_launcher", "Uploaded AUTO PRO imports modified old launcher")
    forbid(uploaded_launcher, "import local_bridge", "Uploaded AUTO PRO imports tracking/web bridge")
    forbid(uploaded_launcher, "clientjs_auto_patch", "Uploaded AUTO PRO imports old behavior patch")
    forbid(uploaded_offline_api, "requests", "Offline API contains HTTP client")
    forbid(uploaded_offline_api, "sqlite", "Offline API records local tracking data")
    require(suite_build, '$OriginalAutoOut = Join-Path $OutputRoot "AUTO_PRO_ORIGINAL"', "Clean original runtime is not packaged")
    require(suite_build, '@("runtime", "_internal", "assets")', "Clean original payload allowlist changed")
    require(suite_build, '"clientjs_auto_patch.py"', "Clean original forbidden-sidecar gate missing")
    require(suite_build, '"platform-tools"', "Clean original ADB exclusion gate missing")
    require(build, '"AUTO_PRO_ORIGINAL\\cry_original_launcher.py"', "Stable release does not require clean launcher")
    require(runtime, '"AUTO_PRO_ORIGINAL\\cry_original_launcher.py"', "Stable runtime accepts missing clean launcher")
    require(build, '@("AUTO_PRO", "AUTO_PRO_ORIGINAL", "Multi", "components")', "Stable release omits clean original runtime")
    for required in (
        'AUTO_PRO\\bin\\kvtm_loader_v3.exe',
        'AUTO_PRO\\bin\\kvtm_bridge_v3.dll',
        'Multi\\kvtm_multi_owned_host.py',
        'Multi\\kvtm_multi_dev_host.py',
        'Multi\\fps_hardcap_integration.py',
        'Multi\\clear_stall_window_position.py',
        'Multi\\auto_main_profile_settings.py',
        'Multi\\auto_multi_dev_ui_integration.py',
        'Multi\\auto_multi_dev_ui_refinement.py',
    ):
        require(build, required, f"Stable release required runtime file missing: {required}")
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
    print("release-branch=normalized-name-no-LASTEXITCODE-dependency")
    print("runtime-io=utf8+unbuffered+redirect-safe")
    print("update=file-or-https+sha256+staging+atomic-switch+rollback")
    print("bootstrap=child-process-exit-isolation+stderr-persistence+visible-failure")
    print("version=automatic-patch-bump-per-new-source-head")
    print("seed=setup+update-current-dev-config+no-runtime-process-map-migration")
    print("parity=dev-host+dwm-off+fps-hardcap+fixed-position+pre-ui-shop-drag-speed+bridge-v3")
    print("dev-isolation=stable-running-not-stopped-by-release-build")
    print("security=no-embedded-github-token")
    print("original-auto-pro=uploaded-sha256+separate-gui+offline-stateless+stable-profile-id+clientjs-startup+bridge-v3+no-adb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
