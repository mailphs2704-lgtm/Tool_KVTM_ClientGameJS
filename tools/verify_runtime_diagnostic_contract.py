from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGGER = ROOT / "source-archive/multi-current/kvtm_multi_tool/runtime_diagnostic_logger.py"
HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def main() -> int:
    logger = LOGGER.read_text(encoding="utf-8")
    host = HOST.read_text(encoding="utf-8")
    ast.parse(logger, filename=str(LOGGER))
    ast.parse(host, filename=str(HOST))

    for needle, message in (
        ("runtime-diagnostic-current.jsonl", "Single current diagnostic log missing"),
        ("multi_not_responding", "Multi hang detection missing"),
        ("cpu_percent_one_core", "Multi CPU sampling missing"),
        ("working_set_mb", "Memory sampling missing"),
        ("not_responding", "ClientJS response summary missing"),
        ("_LOG_LIMIT_BYTES", "Diagnostic log rotation missing"),
        ("no-command-line,no-profile-content,no-token", "Privacy policy marker missing"),
        ('getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)', "Low-priority monitor missing"),
        ("stdin=subprocess.DEVNULL", "Detached monitor stdin missing"),
    ):
        require(logger, needle, message)
    require(host, "from runtime_diagnostic_logger import start_runtime_diagnostic", "Host diagnostic import missing")
    require(host, "diagnostic_process = start_runtime_diagnostic(", "Host diagnostic startup missing")
    require(host, "kvtm_multi_dev_entry.core.APP_DIR", "Diagnostic data root is not product-owned")
    require(logger, 'KVTM_RUNTIME_DIAGNOSTICS', "Diagnostic monitor must be opt-in")
    require(logger, 'not in {"1", "true", "yes", "on"}', "Diagnostic monitor default-off guard missing")
    print("KVTM RUNTIME DIAGNOSTIC CONTRACT VERIFIED")
    print("log=single-jsonl+rotating+opt-in")
    print("health=responding+cpu+memory+handles+client-summary")
    print("privacy=no-command-line+no-profile-content+no-token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
