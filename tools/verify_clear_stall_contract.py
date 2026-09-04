from __future__ import annotations

"""Static safety contract for the clean ClientJS clear-stall workflow."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/workflow.py"
CONFIG = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/config.py"
WORKER = ROOT / "components/clientjs-auto/worker/clear_stall_worker.py"
AUTO_WORKER = ROOT / "components/clientjs-auto/worker/auto_worker.py"
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
CLIENT_PATCH = ROOT / "test-candidates/auto-pro-clientjs-temp/clientjs_auto_patch.py"
DESIGNER = ROOT / "source-archive/multi-current/kvtm_multi_tool/clear_stall_designer.py"


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def forbid(source: str, needle: str, message: str) -> None:
    if needle in source:
        raise AssertionError(message)


def main() -> int:
    sources = {}
    for path in (WORKFLOW, CONFIG, WORKER, AUTO_WORKER, PROBE, BUYING, SELLING, STALL, DEV_ENTRY, MULTI):
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        sources[path] = text

    workflow = sources[WORKFLOW]
    config = sources[CONFIG]
    worker = sources[WORKER]
    auto_worker = sources[AUTO_WORKER]
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
    client_patch = CLIENT_PATCH.read_text(encoding="utf-8")
    ast.parse(client_patch, filename=str(CLIENT_PATCH))
    designer = DESIGNER.read_text(encoding="utf-8")
    ast.parse(designer, filename=str(DESIGNER))

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
    require(probe, "while purchased_quantity < expected_quantity:", "Gate 3B must repeat until target or Stop")
    require(probe, "for local_pass in range(1, int(config.max_stall_passes) + 1)", "Gate 3B per-visit reload loop missing")
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
        "while pending_resale_fingerprints:",
        "Gate 5 pending verified-purchase resale loop missing",
    )
    require(
        probe,
        "pending_resale_fingerprints.pop(index)",
        "Gate 5 must consume each verified purchase token once",
    )
    require(
        probe,
        "if pending_resale_fingerprints:",
        "Gate 5 final pending inventory flush missing",
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
        "Each logical stall step must contain exactly two swipes",
    )
    require(
        probe,
        '"TWO_SWIPES_THEN_SCAN_COLLECT_RESELL"',
        "Two-swipes then scan/collect/resell order missing",
    )
    require(
        probe,
        "except InventoryFull:",
        "Full clone inventory recovery missing",
    )
    require(
        probe,
        "flush_pending_inventory(",
        "Verified-purchase inventory flush missing",
    )
    require(
        probe,
        "RestartFriendScanAfterInventoryFlush",
        "Purchase scan must restart after inventory flush",
    )
    require(
        stall,
        "swipe {swipe_index}/2 trong một nhịp",
        "Stall logical step must execute both swipes",
    )
    require(
        probe,
        '"stall-step-finished-scan-required"',
        "Every completed stall step must force the next view scan",
    )
    forbid(
        probe,
        "automation.stall.rewind_to_first(STALL_VIEW_COUNT)",
        "Gate 5 must not pre-scan all views then rewind before resale",
    )
    forbid(workflow, "CarryoverStore", "Dọn quầy must not carry inventory across cycles")
    require(builder, "carryover purged", "builder must purge stale carryover state")
    require(builder, "$BridgeInUse", "Builder bridge lock target missing")
    require(builder, "running_clients.json", "Builder DEV PID map cleanup missing")
    require(builder, "$LoadedModule.FileName", "Builder exact loaded bridge detection missing")
    require(builder, "[System.IO.FileShare]::None", "Builder bridge release verification missing")
    require(
        builder,
        '$Candidate.ProcessName -eq "GameClientJS"',
        "Builder must restrict PID cleanup to GameClientJS",
    )
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
    require(backup, "bundle create $bundle HEAD", "Backup must snapshot source")
    require(backup, "private_data_local_only", "Backup privacy marker missing")
    require(handoff, "requested_quantity == purchased_quantity == sold_quantity", "AI handoff lifecycle contract missing")
    require(
        probe,
        'policy="UNTIL_TARGET_OR_STOP"',
        "Dọn quầy stock polling policy missing",
    )
    forbid(
        probe,
        "đã duyệt hết giới hạn nhưng chưa đủ target",
        "Dọn quầy must not fail only because one configured round is exhausted",
    )
    for item_id in ("nuoc_hoa_hong", "tinh_dau_hh", "vai_vang", "tao_say", "tra_da"):
        require(probe, f'"{item_id}"', f"Missing selected-item template: {item_id}")
        require(multi, f'"{item_id}"', f"Missing selected-item GUI option: {item_id}")
    require(probe, "eligible_observations", "Purchase whitelist filter missing")
    require(dev_entry, "allowed_item_ids=allowed_item_ids", "Selected items not passed to resident runtime")
    require(
        dev_entry,
        "allowed_item_ids: tuple[str, ...]",
        "Gate 5 worker thread must receive selected items explicitly",
    )
    require(auto_worker, '"client_pid_changed"', "Worker PID replacement event missing")
    require(multi, 'event == "client_pid_changed"', "Multi PID replacement handler missing")
    require(multi, "RunningProcessRef(new_pid)", "Multi must adopt exact worker PID")
    require(
        client_patch,
        'if name == "mo_ruong" and find_kwargs.get("click")',
        "Chest probe-only template lookup missing",
    )
    forbid(
        client_patch,
        "score >= 8.0 or not prompt_visible",
        "Chest must not report success from an absent LD template",
    )
    require(client_patch, "clientjs_game_ready_by_live_capture", "PID reset live-frame readiness missing")
    require(client_patch, '"clientjs_reopen_popup_probe"', "ClientJS reopen popup probe missing")
    require(client_patch, '"clientjs_post_reset_cleanup"', "Post-reset popup cleanup missing")
    require(
        client_patch,
        "post_popup_frame_streak >= 3",
        "AUTO must resume after stable post-popup game frames",
    )
    require(
        client_patch,
        '"clientjs_post_reset_ready"',
        "Post-reset AUTO resume trace missing",
    )
    forbid(
        client_patch,
        "clicked_intermediate = True\n            rendered_streak = 0\n            try:",
        "Popup click must not reset the readiness streak forever",
    )
    require(client_patch, "stable_frames >= 3", "Chest adaptive render wait missing")
    require(client_patch, "cls.VongQuay = vong_quay", "ClientJS wheel exit wrapper missing")
    require(client_patch, "clientjs_wheel_exit_probe", "Wheel exit verification trace missing")

    require(multi, '("clear_stall_designer", "Thiết kế")', "Designer tab missing")
    require(designer, "DEFAULT_STEPS", "Designer default workflow missing")
    require(designer, "self.tree.bind(\"<ButtonRelease-1>\"", "Designer drag reorder missing")
    require(designer, "self.canvas.bind(\"<Button-1>\"", "Designer coordinate drag missing")
    require(designer, "clear-stall-workflow-designer.json", "Designer persistence missing")

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
    print("gate3_reload=per_visit_bound_repeat_until_target_or_stop")
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
    print("gate5_own_stall_views=scan_collect_resell_one_swipe_repeat")
    print("gate5_own_stall_drag=two_swipes_one_step_then_scan")
    print("gui=single_full_clear_stall_action")
    print("cycle=pass_close_reset_countdown_release_queue")
    print("backup=one_click_local_only")
    print("selected_items=rose_water,rose_oil,yellow_fabric,dried_apple,iced_tea")
    print("clientjs_reset=live_capture_ready")
    print("chest=adaptive_render_wait")
    print("wheel=verified_exit_cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
