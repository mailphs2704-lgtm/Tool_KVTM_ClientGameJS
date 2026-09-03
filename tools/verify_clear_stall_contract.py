from __future__ import annotations

"""Static safety contract for the clean ClientJS clear-stall workflow."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/workflow.py"
CONFIG = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/config.py"
WORKER = ROOT / "components/clientjs-auto/worker/clear_stall_worker.py"
PROBE = ROOT / "components/clientjs-auto/worker/clear_stall_probe_runtime.py"
BUYING = ROOT / "components/clientjs-auto/kvtm_automation/actions/buying.py"
SELLING = ROOT / "components/clientjs-auto/kvtm_automation/actions/selling.py"
STALL = ROOT / "components/clientjs-auto/kvtm_automation/actions/stall.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
MULTI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
BUILDER = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"
CONTROL = ROOT / "KVTM_DEV_CONTROL.bat"
BACKUP = ROOT / "tools/KVTM_CREATE_LOCAL_BACKUP.ps1"
HANDOFF = ROOT / "docs/CLEAR_STALL_AUTO_HANDOFF.md"


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def forbid(source: str, needle: str, message: str) -> None:
    if needle in source:
        raise AssertionError(message)


def main() -> int:
    sources = {}
    for path in (WORKFLOW, CONFIG, WORKER, PROBE, BUYING, SELLING, STALL, DEV_ENTRY, MULTI):
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        sources[path] = text

    workflow = sources[WORKFLOW]
    config = sources[CONFIG]
    worker = sources[WORKER]
    probe = sources[PROBE]
    buying = sources[BUYING]
    selling = sources[SELLING]
    stall = sources[STALL]
    dev_entry = sources[DEV_ENTRY]
    multi = sources[MULTI]
    builder = BUILDER.read_text(encoding="utf-8")
    control = CONTROL.read_text(encoding="utf-8")
    backup = BACKUP.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")

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
    require(probe, "if purchase_limit > 0:", "transaction probes must require a positive hard limit")
    require(probe, "maximum=1", "each purchase call must buy at most one listing")
    require(probe, '"PURCHASE_TARGET_MULTI_HOUSE"', "Gate 3B target mode missing")
    require(probe, "range(1, int(config.friend_ordinal) + 1)", "Gate 3B must visit friends 1..N")
    require(probe, "first_pass = 2 if friend_index == 1 else 1", "Gate 3B first-house reload policy missing")
    require(probe, "int(config.max_stall_passes) + 1", "Gate 3B bounded stall reload loop missing")
    require(probe, "remaining_quantity", "Gate 3B remaining x10 counter missing")
    require(probe, "automation.stall.close_friend_stall()", "Gate 3B must close before reload/house change")
    require(probe, "purchase_evidence", "Gate 3 must save per-listing evidence")
    require(probe, '"SCAN_BUY_THEN_SWIPE"', "Gate 3B must buy each view before swiping")
    require(probe, '"REOPEN_CURRENT_STALL"', "same-friend stall reload must stay in place")
    require(
        stall,
        "return tuple(range(1, 9))",
        "every stall view must scan both visible rows",
    )
    require(probe, "skip_unbuyable=(purchase_limit > 1)", "Gate 3B must skip level-locked listings")
    require(buying, "if not self.listing_matches(observation)", "purchase must verify listing disappearance")
    require(buying, "không cộng 10 VP", "unverified click must not increment quantity")
    require(
        stall,
        "listing_is_available",
        "sold listings must be excluded before purchase planning",
    )
    require(
        stall,
        "((495, 530) if slot <= 4 else (685, 720))",
        "top/bottom price-band mapping missing",
    )
    require(dev_entry, "askyesno", "Gate 2 requires explicit user consent")
    require(probe, '"COLLECT_GOLD_RESELL_ONE_EXACT"', "Gate 4 transaction mode missing")
    require(probe, "purchased-icons", "Gate 4 must freeze purchased icons")
    require(probe, "VisualFingerprint.from_image(", "Gate 4 normalized fingerprint missing")
    require(probe, "ITEM_CORE_NO_PRICE_OR_PEDESTAL", "Gate 4 must remove stall context")
    require(probe, '"VERIFIED_PURCHASE_THIS_RUN"', "Gate 4 provenance marker missing")
    require(probe, "resale_batch_limit", "Gate 4 hard resale limit missing")
    require(stall, "collect_own_stall_gold", "Gate 4 must collect own-stall gold first")
    require(
        selling,
        "sell_one_of_exact_purchases",
        "Gate 4 exact purchased-fingerprint selector missing",
    )
    require(
        selling,
        "The empty stall slot is opened before scanning the inventory",
        "Gate 4 inventory must be scanned only after opening a stall slot",
    )
    require(
        selling,
        "best_fingerprint_match",
        "Gate 4 must record candidate scores before exact selection",
    )
    require(
        selling,
        "PLACE_BUTTON",
        "Gate 4 must reuse the existing sale placement flow",
    )
    require(
        selling,
        "EXACT_PURCHASE_MATCH_THRESHOLD = 0.60",
        "Live-calibrated exact resale threshold missing",
    )
    require(
        selling,
        "score < self.EXACT_PURCHASE_MATCH_THRESHOLD",
        "Exact resale selector must use the calibrated named threshold",
    )
    forbid(
        selling,
        "score < 0.62",
        "Obsolete threshold rejects live-verified exact purchases",
    )
    forbid(selling, "price_changed = True", "Gate 4 must never alter price")
    require(dev_entry, "_start_clear_stall_resale_probe", "Gate 4 DEV action missing")
    require(dev_entry, "_clear_stall_gate4_profiles", "Gate 4 state tracking missing")
    require(
        probe,
        '"COLLECT_GOLD_RESELL_TARGET_EXACT"',
        "Gate 5 transaction mode missing",
    )
    require(
        probe,
        "for batch_index in range(1, resale_batch_limit + 1)",
        "Gate 5 bounded per-x10 resale loop missing",
    )
    require(
        probe,
        "remaining_fingerprints.pop(index)",
        "Gate 5 must consume each verified purchase token once",
    )
    require(
        probe,
        "sold_quantity != resale_batch_limit * 10",
        "Gate 5 exact accounting assertion missing",
    )
    require(dev_entry, "_start_clear_stall_full_resale_probe", "Gate 5 DEV action missing")
    require(dev_entry, "_clear_stall_gate5_profiles", "Gate 5 state tracking missing")
    require(
        multi,
        "Dọn quầy: Mua đủ + thu vàng + treo lại toàn bộ",
        "Full clear-stall button missing",
    )
    forbid(multi, "▶ GATE 1: Kiểm tra quầy", "Passed Gate 1 button must be removed")
    forbid(multi, "▶ GATE 2: Mua thử", "Passed Gate 2 button must be removed")
    forbid(multi, "▶ GATE 3: Mua đủ", "Passed Gate 3 button must be removed")
    forbid(multi, "▶ GATE 4: Thu vàng", "Passed Gate 4 button must be removed")
    require(
        probe,
        "except NoEmptyStallSlot:",
        "Full resale must detect a full visible own-stall view",
    )
    require(
        probe,
        "automation.stall.next_view()",
        "Full resale must drag the own stall to later views",
    )
    require(
        probe,
        "swipe_pulses=2",
        "Own-stall transition must document the proven two-pulse drag",
    )
    require(
        probe,
        '"SCAN_COLLECT_RESELL_THEN_SWIPE"',
        "Own-stall per-view transaction order missing",
    )
    require(
        probe,
        "collected_gold_slots += scan_and_collect_own_view(",
        "Each newly revealed view must collect gold before resale",
    )
    forbid(
        probe,
        "automation.stall.rewind_to_first(STALL_VIEW_COUNT)",
        "Gate 5 must not pre-scan all views then rewind before resale",
    )
    forbid(workflow, "CarryoverStore", "Dọn quầy must not carry inventory across cycles")
    require(builder, "carryover purged", "builder must purge stale carryover state")
    forbid(builder, "4 views / 20 physical slots", "builder must not claim fixed stall capacity")

    require(
        multi,
        "self.auto_clear_stall_start_button = (",
        "Production entry compatibility anchor missing",
    )
    require(
        dev_entry,
        "legacy_probe.destroy()",
        "DEV must hide the legacy passed-probe button",
    )
    require(
        dev_entry,
        "self.auto_clear_stall_probe_button = full_action",
        "DEV compatibility alias must point to the one full-action button",
    )
    require(
        dev_entry,
        "def _start_scheduled_full_clear_stall",
        "Due full-cycle scheduler entry missing",
    )
    require(
        dev_entry,
        "requested <= 0 or purchased != requested or sold != requested",
        "Completion accounting guard missing",
    )
    require(
        dev_entry,
        'job["next_run_at"] = (',
        "Successful cycle must reset its countdown",
    )
    require(
        dev_entry,
        "proc.terminate()",
        "Successful cycle must support closing its ClientJS",
    )
    require(
        dev_entry,
        "for _due, profile_id in sorted(due_jobs):",
        "Due accounts must keep deterministic queue order",
    )
    require(
        control,
        'if /I "%CHOICE%"=="B" goto local_backup',
        "One-click backup menu action missing",
    )
    require(backup, "git bundle create", "Backup must snapshot source")
    require(backup, "private_data_local_only", "Backup privacy marker missing")
    require(handoff, "requested_quantity == purchased_quantity == sold_quantity", "AI handoff lifecycle contract missing")

    print("CLEAR STALL STATIC CONTRACT VERIFIED")
    print("gate=READ_ONLY_SCAN")
    print("quantity_unit=10")
    print("stall_capacity=dynamic")
    print("friend_order=1..N")
    print("account_concurrency=1")
    print("carryover=disabled")
    print("gate2_limit=one_x10_listing")
    print("purchase_verification=listing_disappearance")
    print("sold_listing_filter=coin_price_marker")
    print("gate3_limit=configured_x10_target")
    print("gate3_reload=bounded_per_house")
    print("gate3_friend_order=1..N")
    print("gate3_view_order=scan_buy_then_swipe_both_rows")
    print("gate3_same_friend_reload=in_place")
    print("gate3_unbuyable=skip_without_accounting")
    print("gate3_resale=disabled")
    print("gate4_limit=one_exact_purchased_x10_batch")
    print("gate4_gold=collect_before_resale")
    print("gate4_inventory_scan=after_empty_slot_open")
    print("gate4_price=unchanged")
    print("gate5_limit=all_verified_purchases_up_to_20_batches")
    print("gate5_accounting=one_token_per_x10_sale")
    print("gate5_wrong_item=provenance_only_threshold_0.60")
    print("gate5_own_stall_views=scan_collect_resell_then_swipe_1..4")
    print("gate5_own_stall_drag=two_pulses_per_view")
    print("gui=single_full_clear_stall_action")
    print("cycle=pass_close_reset_countdown_release_queue")
    print("backup=one_click_local_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
