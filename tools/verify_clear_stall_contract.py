from __future__ import annotations

"""Static safety contract for the clean ClientJS clear-stall workflow."""

import ast
import json
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
INVENTORY = ROOT / "components/clientjs-auto/kvtm_automation/actions/inventory.py"
DESIGNER_POLICY = ROOT / "components/clientjs-auto/kvtm_automation/workflows/clear_stall/designer_policy.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
MULTI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
BUILDER = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"
CONTROL = ROOT / "KVTM_DEV_CONTROL.bat"
BACKUP = ROOT / "tools/KVTM_CREATE_LOCAL_BACKUP.ps1"
HANDOFF = ROOT / "docs/CLEAR_STALL_AUTO_HANDOFF.md"
CLIENT_PATCH = ROOT / "test-candidates/auto-pro-clientjs-temp/clientjs_auto_patch.py"
ENGINE_DRIVER = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"
DESIGNER = ROOT / "source-archive/multi-current/kvtm_multi_tool/clear_stall_designer.py"
AUTO_CATALOG = ROOT / "components/clientjs-auto/catalog/functions.json"
CLEAN_AUTO_WORKER = ROOT / "components/clientjs-auto/worker/clean_auto_worker.py"
GAME_SESSION = ROOT / "components/clientjs-auto/kvtm_automation/workflows/game_session/workflow.py"
CLEAN_CONTEXT = ROOT / "components/clientjs-auto/kvtm_automation/context.py"
CLEAN_AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
CLEAN_DRIVER = ROOT / "components/clientjs-auto/kvtm_automation/runtime/cocos_bridge.py"
PROFILE_PROCESS = ROOT / "components/clientjs-auto/kvtm_automation/runtime/profile_process.py"
POPUP_ACTIONS = ROOT / "components/clientjs-auto/kvtm_automation/actions/popup.py"
MAIN_LOG = ROOT / "components/clientjs-auto/kvtm_automation/runtime/main_log.py"
MAIN_LOG_VIEWER = ROOT / "source-archive/multi-current/kvtm_multi_tool/main_log_viewer.py"
VP_RECOGNITION = ROOT / "components/clientjs-auto/kvtm_automation/actions/item_recognition.py"
VP_WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/vp_recognition/workflow.py"


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def forbid(source: str, needle: str, message: str) -> None:
    if needle in source:
        raise AssertionError(message)


def main() -> int:
    sources = {}
    for path in (WORKFLOW, CONFIG, WORKER, AUTO_WORKER, PROBE, BUYING, SELLING, STALL, INVENTORY, DESIGNER_POLICY, DEV_ENTRY, MULTI):
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
    inventory = sources[INVENTORY]
    designer_policy = sources[DESIGNER_POLICY]
    dev_entry = sources[DEV_ENTRY]
    multi = sources[MULTI]
    builder = BUILDER.read_text(encoding="utf-8")
    control = CONTROL.read_text(encoding="utf-8")
    backup = BACKUP.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")
    client_patch = CLIENT_PATCH.read_text(encoding="utf-8")
    ast.parse(client_patch, filename=str(CLIENT_PATCH))
    engine_driver = ENGINE_DRIVER.read_text(encoding="utf-8")
    auto_catalog = json.loads(AUTO_CATALOG.read_text(encoding="utf-8"))
    clean_auto_worker = CLEAN_AUTO_WORKER.read_text(encoding="utf-8")
    game_session = GAME_SESSION.read_text(encoding="utf-8")
    clean_context = CLEAN_CONTEXT.read_text(encoding="utf-8")
    clean_automation = CLEAN_AUTOMATION.read_text(encoding="utf-8")
    clean_driver = CLEAN_DRIVER.read_text(encoding="utf-8")
    profile_process = PROFILE_PROCESS.read_text(encoding="utf-8")
    popup_actions = POPUP_ACTIONS.read_text(encoding="utf-8")
    main_log = MAIN_LOG.read_text(encoding="utf-8")
    main_log_viewer = MAIN_LOG_VIEWER.read_text(encoding="utf-8")
    vp_recognition = VP_RECOGNITION.read_text(encoding="utf-8")
    vp_workflow = VP_WORKFLOW.read_text(encoding="utf-8")
    for path, source in (
        (CLEAN_AUTO_WORKER, clean_auto_worker),
        (GAME_SESSION, game_session),
        (CLEAN_CONTEXT, clean_context),
        (CLEAN_AUTOMATION, clean_automation),
        (CLEAN_DRIVER, clean_driver),
        (PROFILE_PROCESS, profile_process),
        (POPUP_ACTIONS, popup_actions),
        (MAIN_LOG, main_log),
        (MAIN_LOG_VIEWER, main_log_viewer),
        (VP_RECOGNITION, vp_recognition),
        (VP_WORKFLOW, vp_workflow),
    ):
        ast.parse(source, filename=str(path))
    ast.parse(engine_driver, filename=str(ENGINE_DRIVER))
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
    require(multi, "Đang xếp hàng", "queued-account status missing")
    require(probe, "if purchase_limit > 0:", "transaction probes must require a positive hard limit")
    require(probe, "maximum=1", "each purchase call must buy at most one listing")
    require(probe, '"PURCHASE_TARGET_MULTI_HOUSE"', "Gate 3B target mode missing")
    require(probe, "range(1, int(config.friend_ordinal) + 1)", "Gate 3B must visit friends 1..N")
    require(probe, "while purchased_quantity < expected_quantity:", "Gate 3B must repeat until target or Stop")
    require(
        probe,
        'policy="ONE_SCAN_PER_HOUSE_THEN_NEXT_ROUND"',
        "Gate 3B one-scan-per-house round policy missing",
    )
    forbid(
        probe,
        "for local_pass in range(1, int(config.max_stall_passes) + 1)",
        "Gate 3B must not reload the same house inside one round",
    )
    require(probe, "remaining_quantity", "Gate 3B remaining x10 counter missing")
    require(probe, "automation.stall.close_friend_stall()", "Gate 3B must close before reload/house change")
    require(probe, "purchase_evidence", "Gate 3 must save per-listing evidence")
    require(probe, '"SCAN_BUY_THEN_SWIPE"', "Gate 3B must buy each view before swiping")
    require(probe, '"ONE_SCAN_PER_HOUSE"', "one-scan navigation marker missing")
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
    require(
        selling,
        '"not-required"',
        "Resale must not require the sl10 marker",
    )
    forbid(
        selling,
        'raise InsufficientBatch("Loại VP hiện không đủ 10 để treo bán")',
        "Resale must not block when the sl10 marker is absent",
    )
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
        "▶ Bắt đầu Dọn quầy",
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
        "OWN_STALL_RESALE_SCAN_LIMIT = STALL_VIEW_COUNT + 1",
        "Own-stall terminal alignment scan allowance missing",
    )
    require(
        probe,
        '"gate5-own-stall-post-swipe-scan-required"',
        "Final two-swipe movement must force another own-stall scan",
    )
    require(
        probe,
        "terminal_alignment=(next_sale_view > STALL_VIEW_COUNT)",
        "Terminal own-stall alignment evidence missing",
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
        "range(1, self.swipe_pulses + 1)",
        "Stall logical step must execute both swipes",
    )
    require(
        probe,
        '"stall-step-finished-scan-required"',
        "Every completed stall step must force the next view scan",
    )
    require(
        probe,
        "FRIEND_STALL_SCAN_COUNT = 5",
        "Every selected friend stall must have five scan-buy positions",
    )
    require(
        probe,
        "for view in range(1, FRIEND_STALL_SCAN_COUNT + 1):",
        "Friend-stall five-pass scan loop missing",
    )
    require(
        probe,
        "mapping_view = min(view, STALL_VIEW_COUNT)",
        "Terminal friend-stall scan must preserve the physical slot mapping",
    )
    require(
        probe,
        'order="BUY_THEN_TWO_SWIPES_THEN_SCAN"',
        "Friend-stall order must be scan-buy then two consecutive swipes",
    )
    require(
        probe,
        "automation.stall.next_view()",
        "Friend-stall movement must use the validated two-swipe operation",
    )
    forbid(
        probe,
        '"stall-intermediate-swipe-scan"',
        "Friend-stall must never scan between swipe pulse 1 and pulse 2",
    )
    forbid(
        probe,
        '"SWIPE_SCAN_BUY_THEN_SWIPE"',
        "Friend-stall must never buy between swipe pulse 1 and pulse 2",
    )
    require(
        probe,
        '"stall-view-recognition-retry"',
        "Post-swipe animated item recognition retries missing",
    )
    require(
        probe,
        "collect_own_stall_gold(maximum=designer_policy.collect_gold_maximum)",
        "Gold collection must use the validated designer policy",
    )
    forbid(
        probe,
        "collect_own_stall_gold(maximum=20)",
        "Twenty gold attempts per view cause unnecessary resale delay",
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
        'policy="ONE_SCAN_PER_HOUSE_THEN_NEXT_ROUND"',
        "Dọn quầy one-scan-per-house stock polling policy missing",
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
    require(
        auto_worker,
        "AUTO PRO owns its original retry/reset policy",
        "AUTO worker must preserve AUTO PRO reset ownership",
    )
    require(auto_worker, "automation.start()", "AUTO PRO entry call missing")
    require(auto_worker, "allowed_function_ids = {0, 98, 136, 170, 318}", "Star event Function 0 allow-list missing")
    require(auto_worker, "def get_wait_time(self, _default=0):", "Function 0 numeric wait adapter missing")
    event_functions = [
        item for item in auto_catalog.get("functions", [])
        if item.get("auto_pro_function_id") == 0
    ]
    if len(event_functions) != 1:
        raise AssertionError("Star event Function 0 catalog entry must be unique")
    if event_functions[0].get("entrypoint") != "FarmAutomation.produceItems_0":
        raise AssertionError("Star event catalog entrypoint mismatch")
    if event_functions[0].get("label") != "Cào Cây Event - Cây Sao":
        raise AssertionError("Star event Multi label mismatch")
    require(
        auto_worker,
        '"worker_resumed_after_client_restart"',
        "AUTO worker verified-restart resume event missing",
    )
    require(
        auto_worker,
        "if current_pid == supervised_pid:",
        "AUTO worker must resume only after a proven ClientJS PID change",
    )
    require(
        auto_worker,
        "if automation.stop_event.is_set():",
        "AUTO worker restart supervisor must honor user stop",
    )
    forbid(
        auto_worker,
        "friend_home_failures += 1",
        "Worker must not replace AUTO PRO's retry/reset policy",
    )
    require(
        dev_entry,
        "_CLEAR_STALL_MAX_CONCURRENCY = 2",
        "Dọn quầy two-client concurrency limit missing",
    )
    require(
        dev_entry,
        "len(active_profiles) >= _CLEAR_STALL_MAX_CONCURRENCY",
        "Dọn quầy active-profile concurrency gate missing",
    )
    require(auto_worker, "Bootstrap bundled dependencies, then lock every PC transport alias", "Bundled PC bootstrap missing")
    require(auto_worker, 'for alias in ("connect", "u2_connect", "uiautomator_connect")', "Recovered ADB connect-alias patch missing")
    require(auto_worker, "EngineDriver(str(profile_id)", "AUTO worker must bind EngineDriver by immutable profile")
    require(auto_worker, "profile_driver = EngineDriver(str(profile_id)", "Per-worker EngineDriver preflight missing")
    require(auto_worker, 'parser.add_argument("--profile-file", required=True)', "AUTO worker profile path argument missing")
    require(auto_worker, 'os.environ["KVTM_MULTI_PROFILE_FILE"] = str(profile_file)', "Active DEV profile path publication missing")
    require(multi, '"--profile-file", str(PROFILE_FILE)', "Multi must pass its active data-dev profile path")
    require(multi, '"☷ Danh sách hàng chờ"', "Clear-stall queue button missing")
    require(multi, '"≡ Log Dọn quầy"', "Clear-stall log button missing")
    require(multi, '"Nhật ký tổng"', "Persistent clear-stall history tab missing")
    require(multi, '"Acc đang dọn"', "Live clear-stall account tab missing")
    require(multi, 'CLEAR_STALL_HISTORY_FILE = APP_DIR / "clear-stall-history.jsonl"', "Separate clear-stall history file missing")
    require(multi, "def _record_clear_stall_activity", "Clear-stall checkpoint logger missing")
    require(multi, "def _refresh_clear_stall_log", "Live clear-stall log refresh missing")
    require(multi, "window.after(1000, self._refresh_clear_stall_log)", "Clear-stall log auto refresh missing")
    require(dev_entry, "self._record_clear_stall_activity(payload)", "Resident probe events must feed the clear-stall log")
    require(dev_entry, "def _watch_clear_stall_probe", "Temporary stalled-resale watchdog missing")
    require(dev_entry, "stalled_for < 300.0", "Watchdog must bound no-action wait to five minutes")
    require(dev_entry, '"temporary_pass": True', "Watchdog temporary-pass result missing")
    require(dev_entry, "stop_event.set()", "Watchdog must stop the resident worker")
    require(dev_entry, "proc.terminate()", "Watchdog must close only the stalled ClientJS")
    require(dev_entry, "finished_at + interval * 60", "Watchdog must reset the next cycle")
    require(dev_entry, "self._clear_stall_scheduled_profiles", "Scheduled clear-stall identity registry missing")
    forbid(dev_entry, "quantity = max(20, quantity)", "Scheduled run must never increase the configured buy target")
    forbid(probe, "Gate treo lại yêu cầu chạy mua target trước", "GATE 5 must allow one verified x10 target")
    require(dev_entry, "or profile_id in self._clear_stall_gate5_profiles", "Scheduled one-listing result must remain classified as GATE 5")
    require(dev_entry, '"scheduled_failure": True', "Scheduled failure accounting missing")
    require(dev_entry, "finished_at + interval * 60 if job.get(\"enabled\", False) else 0", "Scheduled failure must reset its cycle")
    require(dev_entry, "proc.terminate()", "Scheduled failure must close only its ClientJS")
    require(dev_entry, "elif profile_id == self._active_profile_id:", "Scheduled failure must not show a blocking Multi dialog")
    require(multi, 'style="AutoStart.TButton"', "Clear-stall start button must use the Multi AUTO theme")
    require(multi, 'style="AutoStop.TButton"', "Clear-stall stop button must use the Multi AUTO theme")
    require(multi, '"Queue.Treeview.Heading"', "Queue heading theme missing")
    require(multi, '("multi_dev", "AUTO MULTI DEV")', "Clean AUTO Multi DEV tab missing")
    require(multi, 'text="‹"', "AUTO tab left navigation arrow missing")
    require(multi, 'text="›"', "AUTO tab right navigation arrow missing")
    require(multi, "def _scroll_auto_tabs", "AUTO tab horizontal scroll handler missing")
    require(multi, "def _refresh_auto_tab_scroll", "AUTO tab arrow-state synchronization missing")
    require(multi, 'self.auto_tabs_canvas.xview_scroll', "AUTO center strip horizontal scroll missing")
    require(multi, 'text="AUTO MULTI DEV SẠCH"', "Clean AUTO scaffold header missing")
    require(multi, 'text="≡ Log hành động"', "Clean action-log button missing")
    require(multi, 'text="⌕ Log chi tiết"', "Clean detail-log button missing")
    require(multi, "def _open_clean_main_log", "Clean live-log viewer action missing")
    require(main_log, 'self.action_path = self.run_dir / "action.log"', "Action log file missing")
    require(main_log, 'self.detail_path = self.run_dir / "detail.log"', "Detail log file missing")
    require(main_log, "FILE_FUNCTIONS = (", "Log module function manifest missing")
    require(main_log_viewer, "FILE_FUNCTIONS = (", "Log viewer function manifest missing")
    require(main_log_viewer, 'bg="#202020"', "Console-style log viewer missing")
    require(multi, 'text="▶ Bắt đầu AUTO MULTI DEV"', "Consolidated AUTO Multi DEV start button missing")
    require(multi, "command=self._start_clean_auto_session", "Consolidated AUTO Multi DEV start wiring missing")
    require(multi, 'text="⚙ Cấu hình tốc độ"', "AUTO Multi DEV speed settings button missing")
    require(multi, "command=self._auto_multi_dev_configure", "AUTO Multi DEV speed settings wiring missing")
    for passed_button in (
        "▶ Vào game + đóng popup",
        "⌕ Kiểm tra nhận diện VP (READ-ONLY)",
        "▶ Bán VP AUTO",
        "▶ Trồng 27 Hoa hồng",
    ):
        forbid(multi, passed_button, f"Passed test button must stay removed: {passed_button}")
    require(vp_recognition, "FILE_FUNCTIONS = (", "VP recognizer function manifest missing")
    require(vp_workflow, "FILE_FUNCTIONS = (", "VP workflow function manifest missing")
    for item_id in ("tao_say", "vai_vang", "tinh_dau_hh"):
        require(vp_recognition, f'"{item_id}"', f"VP sample missing: {item_id}")
    require(vp_recognition, "click=False", "VP recognition probe must not click an item")
    require(vp_workflow, "read_only: bool = True", "VP workflow must declare READ-ONLY")
    require(
        vp_workflow,
        "for view in range(1, 5):",
        "VP probe must process all four own-stall views",
    )
    require(
        vp_workflow,
        "collect_own_stall_gold(",
        "Each VP probe view must collect own-stall gold first",
    )
    require(
        vp_workflow,
        "open_inventory_read_only(storage_id=2)",
        "Each VP probe view must inspect inventory after collecting gold",
    )
    require(
        vp_workflow,
        "if view < 4:",
        "VP probe must stop swiping after the final view",
    )
    require(
        vp_workflow,
        "self.auto.stall.next_view()",
        "VP probe must advance by the protected two-swipe stall step",
    )
    require(
        vp_workflow,
        "self.auto.stall.close_own_stall()",
        "VP probe must close its own stall after the per-view loop",
    )
    forbid(
        vp_workflow,
        "rewind_to_first",
        "VP probe must never use the rejected two-pass rewind flow",
    )
    require(stall, "def close_own_stall", "Verified own-stall close action missing")
    require(stall, "for local_slot in range(1, visible_limit + 1):", "Optional gold must be scanned once per visible slot")
    require(stall, "slot_zone = (cx - 58, cy - 70, 116, 100)", "Gold recognition must stay in the slot body above the price bar")
    require(selling, "scales=(0.85, 0.92, 1.0, 1.08, 1.15)", "Empty own-stall slot recognition must tolerate edge-swipe scale changes")
    require(selling, "threshold=0.66", "Calibrated empty-slot threshold missing")
    require(stall, 'threshold=0.82', "Gold recognition threshold must reject weak stall decorations")
    require(stall, "verify_deadline = time.monotonic() + 2.0", "Gold collection acknowledgement timeout missing")
    require(stall, "if not disappeared:", "Unresolved gold fail-closed guard missing")
    require(stall, "raise ScreenTimeout(", "Unresolved gold must stop before accounting")
    gold_method = stall.split("def collect_own_stall_gold", 1)[1].split("def next_view", 1)[0]
    if gold_method.index("raise ScreenTimeout(") > gold_method.index("collected += 1"):
        raise AssertionError("Gold accounting occurs before unresolved-gold failure")
    forbid(gold_method, "top = 480 if", "Gold collection must never scan the price-coin band")
    forbid(gold_method, "listing_is_available", "Collectible gold must not use the friend-stall price-coin filter")
    require(stall, "self.vision.driver.click(cx, cy)", "Gold collection slot-center retry missing")
    require(stall, "Có vàng nhưng không thu được; giữ nguyên view, không swipe", "Unresolved gold must block view advance")
    forbid(stall, "while collected < visible_limit", "Gold is optional; collector must not chase a target count")
    require(vp_workflow, "maximum=8", "VP probe gold collection must use visible-slot bound")
    require(selling, "zone=(930, 0, 70, 70)", "READ-ONLY inventory close must target only the top-right X")
    require(selling, "self.vision.driver.click(968, 28)", "READ-ONLY inventory fixed close fallback missing")
    require(selling, "Không đóng được kho READ-ONLY", "READ-ONLY inventory close verification missing")
    require(dev_entry, "VpRecognitionProbeWorkflow(automation).run", "Resident VP probe wiring missing")
    require(dev_entry, "detail_logger=log_writer.detail", "Detail logger not connected to Main context")
    require(clean_automation, "detail_logger=context.detail", "Vision detail logger not connected")
    require(multi, "def _start_clean_auto_session", "Clean AUTO start action missing")
    require(multi, '"clean_auto_worker.py"', "Clean AUTO worker launch missing")
    require(multi, '"--profile-file", str(PROFILE_FILE)', "Clean AUTO profile identity handoff missing")
    require(multi, "def _stop_clean_auto_session", "Clean AUTO stop action missing")
    require(
        dev_entry,
        "image_runtime_ready=True",
        "AUTO MULTI DEV must reuse the resident image runtime",
    )
    require(
        dev_entry,
        "speed_config=speed_values",
        "AUTO MULTI DEV speed configuration must preserve resident runtime wiring",
    )
    require(
        dev_entry,
        "Clean Runtime dùng chung READY • không import lại cv2/numpy/PIL",
        "Resident Main runtime status contract missing",
    )
    require(
        dev_entry,
        "self._clean_main_stop_events",
        "Resident AUTO task stop registry missing",
    )
    require(
        dev_entry,
        "self._probe_thread_alive(profile_id)",
        "AUTO MULTI DEV and Dọn quầy must be exclusive per profile",
    )
    require(clean_auto_worker, "legacy_pyc=False", "Clean AUTO must declare no legacy pyc")
    require(clean_auto_worker, "GameSessionWorkflow(automation).run", "Clean game session entry missing")
    require(game_session, "self.auto.ensure_main_screen", "Clean game entry/main-screen verification missing")
    require(clean_context, "profile_file: Path | None", "Clean context profile file missing")
    require(clean_automation, "profile_id=context.profile_id", "Clean driver immutable profile binding missing")
    require(clean_driver, "def _refresh_profile_pid", "Clean ClientJS PID rebind missing")
    require(clean_driver, "deadline = time.monotonic() + 120.0", "Clean restart wait bound missing")
    require(clean_driver, "self.ensure_bridge()", "Clean bridge reinjection after PID change missing")
    require(profile_process, "class ProfileProcessResolver", "Immutable profile resolver missing")
    require(profile_process, "args[2:] == secret_args", "Exact ClientJS secret-argument match missing")
    forbid(profile_process, "print(", "Profile resolver must never print decrypted secret")
    require(popup_actions, '"lv_up"', "Clean level-up popup guard missing")
    require(popup_actions, '"quay_hang_on"', "Clean stall-popup guard missing")
    require(
        popup_actions,
        "def _dismiss_unknown_center_modal",
        "Generic no-X popup dismissal missing",
    )
    require(
        popup_actions,
        "if self._blocking_modal_geometry(frame)[0]:",
        "Main-screen PASS must be blocked while an unknown modal remains",
    )
    require(
        popup_actions,
        "self.vision.driver.click(500, 185)",
        "Generic modal backdrop close point missing",
    )
    require(
        popup_actions,
        "if still_open:",
        "Generic modal close must be visually verified",
    )
    require(multi, 'style="Queue.Treeview"', "Queue table theme missing")
    require(multi, "def _refresh_clear_stall_queue", "Live clear-stall queue refresh missing")
    require(multi, "rows.sort(key=lambda row: (row[0]", "Queue must sort by least remaining time")
    require(multi, "window.after(1000, self._refresh_clear_stall_queue)", "Queue countdown refresh missing")
    require(multi, '"THỜI GIAN CÒN LẠI"', "Queue countdown column missing")
    require(multi, "item_row, item_label, variable, self._save_clear_stall_config", "Item theme-chip controls missing")
    forbid(multi, "self.auto_clear_stall_pages_spin = ttk.Spinbox", "Redundant clear-stall page control must stay hidden")
    forbid(multi, "self.auto_clear_stall_close_button = self._make_toggle_button", "Redundant close-clone control must stay hidden")
    require(multi, '"close_client_after_run": True', "Successful clear-stall cycle must still close its clone")
    require(engine_driver, 'os.environ.get("KVTM_MULTI_PROFILE_FILE")', "EngineDriver explicit DEV profile path missing")
    require(engine_driver, "def _capture_shared_bgra_once", "Bridge V3 atomic capture helper missing")
    require(engine_driver, "for attempt in range(12):", "Bridge V3 transient frame retry missing")
    require(engine_driver, '"v3_capture_frame_retry"', "Bridge V3 capture retry trace missing")
    require(engine_driver, "verified[8] != frame_id or verified[9] != 2", "Bridge V3 post-copy verification missing")
    require(auto_worker, '"pc_transport_ready"', "Verified PC transport event missing")
    require(auto_worker, "return profile_driver", "PC constructor must reuse its isolated verified driver")
    require(auto_worker, 'profile_storage="READ_ONLY"', "AUTO bootstrap profile read-only marker missing")
    client_runtime = auto_worker.split(
        "def install_clientjs_runtime", 1
    )[1].split("def install_headless_clientjs_runtime", 1)[0]
    if client_runtime.index('importlib.import_module("local_launcher")') > client_runtime.index(
        "import uiautomator2 as u2"
    ):
        raise AssertionError("Bundled dependency paths must load before uiautomator2")
    if client_runtime.index("u2.connect = pc_connect") > client_runtime.index(
        'importlib.import_module("pc_auto_launcher")'
    ):
        raise AssertionError("PC transport must be locked before pc_auto_launcher")
    require(client_runtime, "module_u2.connect = pc_connect", "Automation-local PC alias lock missing")
    forbid(client_runtime, "127.0.0.1:5555", "ClientJS runtime must not contain an ADB fallback target")
    require(multi, 'event == "client_pid_changed"', "Multi PID replacement handler missing")
    require(multi, "RunningProcessRef(new_pid)", "Multi must adopt exact worker PID")
    forbid(
        client_patch,
        "cls.openGame = open_game",
        "ClientJS patch must not replace AUTO PRO openGame/reset policy",
    )
    require(
        client_patch,
        "cls.openChests = _open_chests_auto_pro_reference",
        "ClientJS must install the supplied AUTO PRO openChests reconstruction",
    )
    reference_chest = client_patch.split(
        "def _open_chests_auto_pro_reference", 1
    )[1].split("def _install_controller_patch", 1)[0]
    for needle in (
        'tree_type="chest"',
        "search_zone=(320, 508, 128, 79)",
        "self.driver.click(371, 647)",
        'tree_type="ruong_go"',
        "search_zone=(163, 520, 190, 196)",
        "threshold=0.95",
        "timeout=1.0",
        'tree_type="check_mo_ruong"',
        "search_zone=(392, 649, 253, 103)",
        "self.driver.click(497, 575)",
        'tree_type="check_open_chest"',
        "search_zone=(69, 345, 164, 204)",
        "self.driver.click(143, 404)",
        'tree_type="mo_ruong"',
        "search_zone=(393, 505, 212, 96)",
        "self.driver.click(433, 557)",
        "self.press_back(stop_event)",
        "self.fixerr(stop_event)",
        "e0299c6df0f2da99abd82e740a7038f2026de314329085ac14cb7b1b64744f2e",
    ):
        require(reference_chest, needle, f"AUTO PRO chest reference missing: {needle}")
    forbid(
        reference_chest,
        "ruong_bac",
        "Supplied AUTO PRO bytecode does not use a ruong_bac template",
    )
    require(client_patch, "cls.VongQuay = vong_quay", "ClientJS wheel exit wrapper missing")
    require(client_patch, "clientjs_wheel_exit_probe", "Wheel exit verification trace missing")
    require(
        client_patch,
        "def dismiss_clientjs_level_up",
        "ClientJS level-up popup handler missing",
    )
    level_up = client_patch.split("def dismiss_clientjs_level_up", 1)[1].split(
        "def _blocking_game_overlay", 1
    )[0]
    require(level_up, '("len_cap", "lencap", "level_up")', "Level-up marker templates missing")
    require(level_up, '("nhan", "nhan_thuong")', "Level-up claim templates missing")
    require(level_up, 'coordinate_source="TEMPLATE_CENTER_1000X1000"', "Level-up must click a detected template center")
    forbid(level_up, "driver.click(", "Level-up handler must never use a blind coordinate")
    require(
        auto_worker,
        "dismiss_clientjs_level_up(controller)",
        "AUTO worker level-up monitor hook missing",
    )
    require(engine_driver, "natural_deadline = time.monotonic() + 8.0", "Graceful old-PID timeout missing")
    require(engine_driver, '["taskkill.exe", "/PID", str(old_pid), "/T", "/F"]', "Scoped process-tree termination missing")
    require(engine_driver, "forced_deadline = time.monotonic() + 5.0", "Forced-exit confirmation timeout missing")
    require(engine_driver, "hwnd_deadline = time.monotonic() + 60.0", "New ClientJS HWND timeout missing")
    require(engine_driver, '"pc_restart_runtime_ready"', "Restart READY publication missing")
    require(engine_driver, 'profile_storage="READ_ONLY"', "Profile read-only restart marker missing")
    forbid(engine_driver, "PROFILE_FILE.write_", "Restart driver must never rewrite profiles")

    require(multi, '("clear_stall_designer", "Thiết kế")', "Designer tab missing")
    require(designer, "default_document", "Designer default workflow missing")
    require(designer, "self.tree.bind(\"<ButtonRelease-1>\"", "Designer drag reorder missing")
    require(designer, "self.canvas.bind(\"<Button-1>\"", "Designer coordinate drag missing")
    require(designer, "clear-stall-workflow-designer.json", "Designer persistence missing")
    require(designer, "Mở bảng tạo / chỉnh sửa chức năng", "Detailed designer launcher missing")
    require(designer, "tk.Toplevel", "Detailed designer window missing")
    require(designer, '".designer.bak"', "Python source backup missing")
    require(designer, "ast.parse", "Python source validation missing")
    require(designer_policy, "class ClearStallRuntimePolicy", "Runtime designer policy missing")
    require(designer_policy, "REQUIRED_ORDER", "Protected transaction order missing")
    require(designer_policy, "swipe_pulses != 2", "Two-swipe safety validation missing")
    require(designer_policy, "def validate_document", "Designer document validation missing")
    require(designer_policy, "def save_document", "Designer persistence API missing")
    require(probe, "pending_before_flush = len(pending_resale_fingerprints)", "Inventory-full flush must freeze the purchased VP count")
    require(probe, "required_resale_quantity=pending_before_flush * 10", "Inventory-full flush required resale quantity missing")
    require(probe, "flushed_quantity = sold_quantity - sold_before_flush", "Inventory-full resale accounting delta missing")
    require(probe, "if flushed_quantity != required_flush_quantity:", "Inventory-full flush must block return until every purchased VP is resold")
    require(probe, "pending_batches=0", "Inventory-full flush completion must prove no pending purchase remains")
    require(probe, "load_runtime_policy", "Resident runtime must load designer policy")
    require(probe, "designer_config_path(config.work_dir.parents[2])", "Runtime must load policy from active data-dev")
    require(probe, '"clear-stall-designer-policy-applied"', "Runtime policy trace missing")
    require(stall, "def apply_runtime_policy", "Stall action policy hook missing")
    require(inventory, "self.storage_open_wait", "Storage wait policy hook missing")
    require(builder, "designer_policy.py", "Builder must package runtime designer policy")
    require(
        builder,
        "function Copy-PreservedDirectory",
        "Bounded diagnostic preservation helper missing",
    )
    require(builder, '"/MT:8"', "Diagnostic preservation must use bounded multithreaded robocopy")
    require(builder, "[int]$TimeoutSeconds = 600", "Diagnostic preservation timeout missing")
    require(builder, "$copyProcess.Kill()", "Timed-out diagnostic copy must be stopped")
    require(builder, "Dang bao toan $Label", "Diagnostic preservation heartbeat missing")
    require(
        builder,
        "function Copy-BoundedDiagnosticDirectory",
        "Bounded clear-stall-probe preservation helper missing",
    )
    require(
        builder,
        "[long]$MaxBytes = 134217728",
        "clear-stall-probe preservation must be capped at 128 MiB",
    )
    require(
        builder,
        '(".log", ".json", ".jsonl", ".txt", ".csv")',
        "clear-stall-probe must prioritize logs and reports",
    )
    require(
        builder,
        "Sort-Object LastWriteTime -Descending",
        "Newest diagnostic evidence must be preserved first",
    )
    require(
        builder,
        "Copy-BoundedDiagnosticDirectory -Source $CurrentClearStallProbe",
        "clear-stall-probe must use bounded diagnostic preservation",
    )
    require(
        builder,
        'Get-ChildItem -LiteralPath $DistRoot -Directory -Filter ".kvtm-dev-data-*"',
        "Failed-build temporary copy cleanup missing",
    )
    require(
        builder,
        "Test-Path -LiteralPath $preflightProfiles -PathType Leaf",
        "Pre-build cleanup must require authoritative profiles",
    )
    require(
        builder,
        "Test-Path -LiteralPath $preflightSettings -PathType Leaf",
        "Pre-build cleanup must require authoritative settings",
    )
    forbid(
        builder,
        "Copy-Item -LiteralPath $CurrentClearStallProbe",
        "Silent recursive clear-stall-probe copy can look permanently hung",
    )

    print("CLEAR STALL STATIC CONTRACT VERIFIED")
    print("gate=READ_ONLY_SCAN")
    print("quantity_unit=10")
    print("stall_capacity=dynamic")
    print("friend_order=1..N")
    print("account_concurrency=2")
    print("carryover=disabled")
    print("gate2_limit=one_x10_listing")
    print("purchase_verification=listing_disappearance")
    print("sold_listing_filter=coin_price_marker")
    print("gate3_limit=configured_x10_target")
    print("gate3_reload=one_scan_per_house_then_next_round")
    print("gate3_friend_order=1..N")
    print("gate3_view_order=five_scan_buy_positions_with_two_swipes_between")
    print("gate3_same_friend_reload=disabled")
    print("gate3_unbuyable=skip_without_accounting")
    print("gate3_resale=disabled")
    print("gate4_limit=one_exact_purchased_x10_batch")
    print("gate4_gold=collect_before_resale")
    print("gate4_inventory_scan=after_empty_slot_open")
    print("gate4_price=unchanged")
    print("gate5_limit=all_verified_purchases_up_to_20_batches")
    print("gate5_accounting=verified_purchase_token;sl10_marker_not_required")
    print("gate5_wrong_item=provenance_only_threshold_0.60")
    print("gate5_own_stall_views=scan_collect_resell_one_swipe_repeat")
    print("gate5_own_stall_drag=two_swipes_one_step_then_scan")
    print("gui=single_full_clear_stall_action")
    print("cycle=pass_close_reset_countdown_release_queue")
    print("backup=one_click_local_only")
    print("diagnostic_preservation=logs_reports_plus_newest_images_max128mib")
    print("selected_items=rose_water,rose_oil,yellow_fabric,dried_apple,iced_tea")
    print("clientjs_reset=live_capture_ready")
    print("chest=supplied_auto_pro_bytecode_exact")
    print("level_up=template_only_no_blind_coordinate")
    print("wheel=verified_exit_cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
