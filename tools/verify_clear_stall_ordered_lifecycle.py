from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "components" / "clear_stall_tool"


def load(name: str) -> str:
    path = TOOL / name
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
    return source


def require(source: str, token: str, label: str) -> None:
    if token not in source:
        raise AssertionError(f"{label}: missing {token!r}")


def main() -> int:
    policy = load("runtime_policy.py")
    entry = load("main.py")
    integration = load("runtime_integration.py")

    require(policy, "class OrderedSafeClearStallController", "ordered controller")
    require(policy, "_issue_start_ticket", "FIFO ticket issue")
    require(policy, "_wait_start_turn", "FIFO turn wait")
    require(policy, "_finish_start_ticket", "FIFO turn release")
    require(policy, '"start_order_queued"', "queue evidence")
    require(policy, '"start_order_enter"', "start-order evidence")
    require(policy, '"cycle_paused_after_error"', "hard-error pause")
    require(policy, "self._enabled.discard(profile_id)", "disable retry after hard error")
    require(policy, '"client_preserved_after_error"', "preserve failed client")
    require(policy, '"client_reused_after_error"', "reuse preserved client")
    require(policy, 'self._close_client(profile_id, "cycle_completed")', "close after success")
    require(policy, 'self._close_client(pid, "explicit_stop")', "close on explicit stop")

    require(
        integration,
        "for row in list(self.accounts):\n            self.runtime_controller.start(row.account_id)",
        "Start All follows visible account-list order",
    )
    require(entry, "OrderedSafeClearStallController", "entrypoint policy wiring")
    require(entry, "MAX_CONCURRENCY = 1", "serialized transactional run")

    if "HWND fallback" in policy or "CAPTURE3" in policy:
        raise AssertionError(
            "Lifecycle policy must not bypass or redefine strict Bridge V3 capture"
        )

    print("CLEAR STALL ORDERED LIFECYCLE CONTRACT PASS")
    print("start_all=VISIBLE_LIST_FIFO")
    print("hard_error=PAUSE_ACCOUNT+PRESERVE_CLIENT")
    print("success=CLIENT_CLOSE")
    print("explicit_stop=CLIENT_CLOSE")
    print("bridge_capture=UNCHANGED_STRICT_V3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
