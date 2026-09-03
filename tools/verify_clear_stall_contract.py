from __future__ import annotations

"""Static safety contract for the clean ClientJS clear-stall workflow."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/workflow.py"
CONFIG = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/config.py"
WORKER = ROOT / "components/clientjs-auto/worker/clear_stall_worker.py"
MULTI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
BUILDER = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def forbid(source: str, needle: str, message: str) -> None:
    if needle in source:
        raise AssertionError(message)


def main() -> int:
    sources = {}
    for path in (WORKFLOW, CONFIG, WORKER, MULTI, BUILDER):
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        sources[path] = text

    workflow = sources[WORKFLOW]
    config = sources[CONFIG]
    worker = sources[WORKER]
    multi = sources[MULTI]
    builder = sources[BUILDER]

    require(worker, 'EXECUTION_GATE = "READ_ONLY_SCAN"', "transaction gate must stay read-only")
    require(worker, "probe_only=True", "worker must not enable purchase/resale")
    require(workflow, "record.record_purchase(LISTING_QUANTITY)", "one verified listing must add ten VP")
    require(workflow, "remaining_listings = remaining_quantity // LISTING_QUANTITY", "target must convert VP to listing count")
    require(workflow, "range(1, self.request.friend_ordinal + 1)", "friend houses must run sequentially")
    require(workflow, "range(1, self.request.max_stall_passes + 1)", "stall refresh loop missing")
    require(workflow, "self.automation.stall.close_friend_stall()", "refresh must close the current stall")
    require(config, "max_stall_passes: int = 10", "bounded refresh setting missing")
    require(multi, "busy_profiles", "machine-wide account serialization missing")
    require(multi, "Đang xếp hàng", "queued-account status missing")
    forbid(workflow, "CarryoverStore", "Dọn quầy must not carry inventory across cycles")
    require(builder, "carryover purged", "builder must purge stale carryover state")
    forbid(builder, "4 views / 20 physical slots", "builder must not claim fixed stall capacity")

    print("CLEAR STALL STATIC CONTRACT VERIFIED")
    print("gate=READ_ONLY_SCAN")
    print("quantity_unit=10")
    print("stall_capacity=dynamic")
    print("friend_order=1..N")
    print("account_concurrency=1")
    print("carryover=disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
