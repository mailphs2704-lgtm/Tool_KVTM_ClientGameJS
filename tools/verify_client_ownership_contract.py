from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MULTI = ROOT / "source-archive" / "multi-current" / "kvtm_multi_tool"
OWNERSHIP = MULTI / "client_ownership_integration.py"
OWNED_HOST = MULTI / "kvtm_multi_owned_host.py"
CORE = MULTI / "kvtm_multi.py"
DEV_START = ROOT / "packaging" / "suite-v0.15" / "START_MULTI_DEV_SILENT.ps1"
CRY_RUNTIME = ROOT / "packaging" / "kvtm-tool-cry" / "bootstrap" / "Kvtm_tool_Cry_Runtime.ps1"
CRY_UPDATE = ROOT / "packaging" / "kvtm-tool-cry" / "bootstrap" / "Kvtm_tool_Cry_Update.ps1"
VERSION = ROOT / "packaging" / "kvtm-tool-cry" / "VERSION"


def text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing ownership contract file: {path}")
    return path.read_text(encoding="utf-8-sig")


def require(body: str, token: str, message: str) -> None:
    if token not in body:
        raise AssertionError(message)


def forbid(body: str, token: str, message: str) -> None:
    if token in body:
        raise AssertionError(message)


def main() -> int:
    ownership = text(OWNERSHIP)
    owned_host = text(OWNED_HOST)
    core = text(CORE)
    dev_start = text(DEV_START)
    cry_runtime = text(CRY_RUNTIME)
    cry_update = text(CRY_UPDATE)

    ast.parse(ownership, filename=str(OWNERSHIP))
    ast.parse(owned_host, filename=str(OWNED_HOST))

    require(
        ownership,
        'REGISTRY_DIR = Path(os.environ.get("APPDATA", Path.home())) / "KVTM Client Ownership"',
        "Ownership registry is not in the shared APPDATA namespace",
    )
    require(ownership, 'MUTEX_NAME = r"Local\\KVTM_Client_Ownership_v1"', "Named ownership mutex missing")
    require(ownership, "REGISTRY_SCHEMA = 2", "Ownership registry schema was not upgraded for account identity")
    require(ownership, "os.replace(temp, REGISTRY_FILE)", "Ownership registry write is not atomic")
    require(ownership, "GetProcessTimes", "PID creation-token validation missing")
    require(ownership, '"creation_token"', "Registry creation token field missing")
    require(ownership, '"profile_id"', "Registry profile id field missing")
    require(ownership, '"account_key"', "Registry account fingerprint field missing")
    require(ownership, '"owner"', "Registry owner field missing")
    require(ownership, '"account_name"', "Registry account display name missing")

    require(ownership, "class ForeignOwnershipError", "Foreign ownership error type missing")
    require(ownership, "same_pid or same_profile or same_account or same_alias", "Account/PID/profile duplicate claim guard missing")
    require(ownership, "lookup_identity", "Pre-launch account identity lookup missing")
    require(ownership, "hashlib.sha256(payload).hexdigest()", "Account credential fingerprint is not hashed")
    require(ownership, "self._profile_signature(profile)", "Account identity is not derived from the saved launch signature")
    require(ownership, "process.terminate()", "Losing duplicate launch is not fail-close")
    require(ownership, "registry.self_owned", "Adoption is not owner-scoped")
    require(ownership, "owned_pids", "Foreign PID adoption filter missing")
    require(ownership, 'get("ProcessId")', "Ownership adoption does not read running_clients ProcessId")
    require(ownership, "Bỏ qua ClientJS thuộc tool khác", "Foreign stop protection marker missing")

    require(ownership, "• ONL • {entry['owner']}", "ONL owner label missing from account list")
    require(ownership, 'tree.heading("pid", text="PID • TOOL")', "Owner status column heading missing")
    require(ownership, 'width=155, minwidth=145', "Owner status column remains too narrow")
    require(ownership, "SetWindowTextW", "ClientJS account-name title update missing")
    require(ownership, 'entry["owner"] != registry.owner', "Window title is not owner-scoped")
    require(ownership, 'str(entry["account_name"])', "Window title does not use account display name")
    require(ownership, "attempt < 40", "ClientJS title retry window must remain bounded")
    require(
        ownership,
        "user32.GetWindowThreadProcessId.argtypes",
        "64-bit HWND signature missing from ownership title callback",
    )
    require(
        ownership,
        "except (ctypes.ArgumentError, OSError, OverflowError, ValueError)",
        "Native title callback must contain Python exceptions",
    )
    require(
        ownership,
        "title_retry_generation",
        "Window-title retry de-duplication missing",
    )

    forbid(ownership, 'profile["secret"]', "Ownership integration directly reads encrypted profile secret")
    forbid(ownership, "unprotect(", "Ownership integration directly decrypts account credentials")
    require(
        ownership,
        '"account_key": account_key',
        "Ownership registry does not publish the hashed account identity",
    )
    forbid(ownership, '"secret":', "Ownership registry must never publish account secrets")

    require(core, 'RUNNING_MAP_FILE = APP_DIR / "running_clients.json"', "Per-tool AUTO running map was moved/shared")

    require(owned_host, "install_client_ownership_integration(app_cls, core)", "Ownership wrapper does not install integration")
    require(owned_host, "kvtm_multi_dev_host.main()", "Ownership wrapper bypasses resident host")
    require(dev_start, '$HostScript = Join-Path $MultiRoot "kvtm_multi_owned_host.py"', "DEV does not launch ownership wrapper")
    require(dev_start, '$env:KVTM_CLIENT_OWNER = "DEV"', "DEV owner identity missing")
    require(dev_start, "$logBudget = 268435456L", "DEV redirected-log retention cap missing")
    require(cry_runtime, '$HostScript = Join-Path $MultiRoot "kvtm_multi_owned_host.py"', "Stable does not launch ownership wrapper")
    require(cry_runtime, '$env:KVTM_CLIENT_OWNER = "CRY"', "Stable owner identity missing")
    require(cry_runtime, "$logBudget = 268435456L", "Stable redirected-log retention cap missing")
    require(cry_update, 'kvtm_multi_owned_host.py', "Stable updater singleton check still targets old host")

    version = tuple(int(part) for part in text(VERSION).strip().split("."))
    if version < (0, 1, 4):
        raise AssertionError("Account-level ClientJS ownership release must be Kvtm_tool_Cry >= 0.1.4")

    print("CLIENTJS OWNERSHIP CONTRACT VERIFIED")
    print("registry=shared-appdata+named-mutex+atomic-json+schema2")
    print("identity=account-key+alias+profile+pid-creation-token")
    print("ui=wide-owner-column+account-window-title")
    print("control=foreign-read-only+owner-only-adopt-stop+fail-close")
    print("secrets=hashed-identity-only-not-published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
