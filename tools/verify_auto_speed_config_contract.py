from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "components/clientjs-auto/kvtm_automation/runtime/auto_speed_config.py"
PLANTING_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
FLOOR_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/floor_navigation.py"
APPLE_SUPPLY_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/apple_supply.py"
PRODUCTION_PANEL_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/production_panel.py"
DRIED_APPLE_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/production.py"
APPLE_JUICE_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/apple_juice_production.py"
YELLOW_FABRIC_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/yellow_fabric_production.py"
AUTOMATION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
DEV_ENTRY_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
AUTO_MULTI_WORKER_PATH = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
GUI_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
INTEGRATION_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py"
STALL_SPEED_INTEGRATION_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/stall_speed_integration.py"
CLEAR_STALL_PROBE_PATH = ROOT / "components/clientjs-auto/worker/clear_stall_probe_runtime.py"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def forbid(text: str, needle: str, message: str) -> None:
    if needle in text:
        raise AssertionError(message)


def check_python(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing speed contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def method_section(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start))
    if start_index < 0 or end_index < 0:
        raise AssertionError(f"Cannot isolate method section: {start} -> {end}")
    return text[start_index:end_index]


def init_section(text: str) -> str:
    start = text.find("    def __init__(")
    if start < 0:
        raise AssertionError("Cannot isolate __init__ section")
    next_method = text.find("\n    def ", start + len("    def __init__("))
    if next_method < 0:
        return text[start:]
    return text[start:next_method]


def main() -> int:
    config = check_python(CONFIG_PATH)
    planting = check_python(PLANTING_PATH)
    floor = check_python(FLOOR_PATH)
    apple_supply = check_python(APPLE_SUPPLY_PATH)
    panel = check_python(PRODUCTION_PANEL_PATH)
    dried = check_python(DRIED_APPLE_PATH)
    apple_juice = check_python(APPLE_JUICE_PATH)
    yellow_fabric = check_python(YELLOW_FABRIC_PATH)
    automation = check_python(AUTOMATION_PATH)
    dev = check_python(DEV_ENTRY_PATH)
    worker = check_python(AUTO_MULTI_WORKER_PATH)
    gui = check_python(GUI_PATH)
    integration = check_python(INTEGRATION_PATH)
    stall_speed_integration = check_python(STALL_SPEED_INTEGRATION_PATH)
    clear_stall_probe = check_python(CLEAR_STALL_PROBE_PATH)

    keys = (
        "floor_swipe_duration",
        "plant_harvest_duration",
        "vp_collect_delay",
        "vp_production_delay",
        "crop_check_interval",
    )
    for key in keys:
        require(config, key, f"Config key missing: {key}")
    for key in (
        "floor_swipe_duration",
        "plant_harvest_duration",
        "vp_production_delay",
        "crop_check_interval",
    ):
        require(gui, f'"{key}"', f"Core GUI key missing: {key}")

    require(integration, '"vp_collect_delay"', "VP collect GUI extension key missing")
    require(integration, '"Thu VP (giây/click)"', "VP collect GUI label missing")
    require(integration, "core.MULTI_DEV_TUNING_KEYS = keys", "VP collect key is not injected into native Multi DEV tuning group")
    require(integration, "_install_vp_collect_speed_control(core)", "VP collect speed control is not installed before app construction")

    require(worker, "speed_config=speed_values", "Isolated worker speed injection missing")
    require(worker, "Tốc độ MULTI DEV |", "Worker speed audit log missing")
    require(worker, "thu VP={speed.vp_collect_delay:.3f}s", "Worker VP collect speed audit missing")
    require(dev, '"--speed-json"', "GUI speed JSON handoff missing")
    require(
        stall_speed_integration,
        '"clear_stall_drag_speed", 0.35',
        "Clear-stall drag speed default missing",
    )
    require(
        stall_speed_integration,
        '"Kéo quầy Dọn quầy (giây/swipe)"',
        "Clear-stall drag speed GUI label missing",
    )
    require(
        dev,
        'self._collect_auto_tuning().get("clear_stall_drag_speed", 0.35)',
        "Per-profile clear-stall drag speed snapshot missing",
    )
    require(
        dev,
        "clear_stall_drag_speed=float(clear_stall_drag_speed)",
        "Resident clear-stall drag speed handoff missing",
    )
    require(
        clear_stall_probe,
        "clear_stall_drag_speed: float = 0.35",
        "Clear-stall runtime speed field missing",
    )
    require(
        clear_stall_probe,
        "swipe_duration=clear_stall_drag_speed",
        "Clear-stall drag speed is not applied to the runtime policy",
    )
    require(
        clear_stall_probe,
        "2 swipe liên tiếp",
        "Clear-stall two-swipe audit log missing",
    )
    require(floor, "duration=self.speed_config.plant_harvest_duration", "Navigation primitive speed binding missing")
    require(planting, "duration=self.speed_config.plant_harvest_duration", "Plant/harvest speed not applied")
    require(apple_supply, "self.speed_config.crop_check_interval", "Crop check interval not applied")

    # VP collection is centralized in ProductionPanelActions for every product.
    # The x5/four-burst minimum remains, but a fresh-frame full-warehouse guard
    # now runs before every click so a blinking modal cannot be clicked away and
    # hidden until the end of the old twenty-click block.
    require(panel, "class ProductionPanelActions", "Shared production panel engine missing")
    require(panel, "def collect_vp_before_machine_panel(", "Canonical shared VP collector missing")
    require(panel, "def _click_until_panel_open(", "Shared panel-open helper missing")
    require(panel, "COLLECT_CLICK_BURST = 5", "Five-click VP collect burst contract missing")
    require(panel, "COLLECT_MIN_BURSTS = 4", "Minimum four VP collect bursts contract missing")
    require(
        panel,
        "COLLECT_MIN_CLICKS = COLLECT_CLICK_BURST * COLLECT_MIN_BURSTS",
        "Minimum twenty-click VP collect contract missing",
    )

    shared_collect = method_section(
        panel,
        "    def collect_vp_before_machine_panel(",
        "    def _click_until_panel_open(",
    )
    require(
        shared_collect,
        "for burst in range(1, self.COLLECT_MIN_BURSTS + 1):",
        "Shared VP collector does not enforce the minimum burst count",
    )
    require(
        shared_collect,
        "for click_ordinal in range(1, self.COLLECT_CLICK_BURST + 1):",
        "Shared VP collector does not preserve exactly x5 clicks per burst",
    )
    require(
        shared_collect,
        "warehouse_full, _empty_ready = self._panel_state(",
        "Shared VP collector lacks per-click full-warehouse guard",
    )
    require(
        shared_collect,
        "frame=self.vision.frame()",
        "Shared VP collector full-warehouse guard is not based on a fresh frame",
    )
    require(
        shared_collect,
        "self._raise_inventory_full(label)",
        "Shared VP collector does not hand full warehouse to typed recovery",
    )
    require(
        shared_collect,
        "self.vision.driver.click(*machine_point)",
        "Shared VP collector machine click missing",
    )
    require(
        shared_collect,
        "self.waiter.sleep(self.speed_config.vp_collect_delay)",
        "Shared VP collector post-burst settle delay missing",
    )
    require(shared_collect, "click_count += 1", "Shared VP click counter missing")
    require(shared_collect, "return click_count", "Shared VP collector does not report its click count")
    if shared_collect.count("self.waiter.sleep(") != 1:
        raise AssertionError("Shared VP collector may only sleep after each completed x5 burst")

    guard = shared_collect.index("warehouse_full, _empty_ready = self._panel_state(")
    click = shared_collect.index("self.vision.driver.click(*machine_point)")
    settle = shared_collect.index("self.waiter.sleep(self.speed_config.vp_collect_delay)")
    if not guard < click < settle:
        raise AssertionError(
            "Each shared VP burst must be fresh-frame guard -> click x5 -> settle"
        )

    collect = method_section(
        panel,
        "    def _click_until_panel_open(",
        "    def _wait_for_idle_open_panel(",
    )
    require(
        collect,
        "self.collect_vp_before_machine_panel(",
        "Panel-open helper bypasses the canonical >=20-click VP collector",
    )
    forbid(
        collect,
        "self._send_collect_burst(machine_point=machine_point)",
        "Panel-open helper regressed to a private raw x5 burst",
    )
    require(collect, "frame = self.vision.frame()", "VP collect fresh-frame capture missing after shared collection")
    require(collect, "warehouse_full, empty_ready = self._panel_state(frame=frame)", "VP collect panel check must reuse fresh frame")
    require(collect, "self._find_wrong_product_match(", "VP collect wrong-machine scan missing")
    shared_call = collect.index("self.collect_vp_before_machine_panel(")
    fresh_frame = collect.index("frame = self.vision.frame()")
    panel_check = collect.index("warehouse_full, empty_ready = self._panel_state(frame=frame)")
    if not shared_call < fresh_frame < panel_check:
        raise AssertionError("VP collect order must be shared >=20 clicks -> fresh frame -> panel check")

    # Product queue gesture timing stays product-owned while collection/panel proof
    # stays shared. Constructor formatting is intentionally irrelevant: verify the
    # semantic wiring inside __init__ rather than one exact source-code line.
    require(dried, "self.speed_config.vp_production_delay", "VP production speed not applied to dried apple")
    for text, label in ((apple_juice, "apple juice"), (yellow_fabric, "yellow fabric")):
        ctor = init_section(text)
        require(ctor, "self.speed_config = speed_config or AutoSpeedConfig()", f"{label} speed config normalization missing")
        require(ctor, "self.slots = ProductionPanelActions(", f"{label} does not construct shared panel helper")
        require(ctor, "self.speed_config,", f"Shared speed config not delegated to {label} panel helper")
        require(text, "self.slots._click_until_panel_open(", f"Shared VP collect helper not used by {label}")
        require(text, "self.speed_config.vp_production_delay", f"VP production speed not applied to {label}")
        forbid(text, "self.slots = ProductionActions(", f"{label} regressed to Dried Apple helper")

    # Floor-6 immediate-empty behavior is semantic, not source formatting. The
    # call is intentionally multiline in AppleSupplyActions after standardization.
    require(apple_supply, "def harvest_and_replant_floor_6_row(self) -> int:", "Floor-6 apple supply action missing")
    require(apple_supply, "allow_empty=True,", "Floor 6 must allow immediate planting on empty pots")
    require(apple_supply, 'label="hàng dưới cùng tầng 6",', "Floor-6 empty/ripe state label missing")
    require(automation, "AutoSpeedConfig.from_mapping", "Speed normalization missing")
    require(gui, "MULTI_DEV_TUNING_KEYS = (", "Dedicated Multi DEV tuning key group missing")
    require(gui, "AUTO_LEGACY_TUNING_KEYS = tuple(", "Legacy AUTO tuning key group missing")
    require(gui, "def _auto_multi_dev_configure", "Dedicated Multi DEV speed dialog missing")
    require(gui, "keys=MULTI_DEV_TUNING_KEYS", "Multi Dev dialog must only show its own settings")
    require(gui, "keys=AUTO_LEGACY_TUNING_KEYS", "Legacy AUTO dialog must use separate setting group")
    require(gui, "command=self._auto_multi_dev_configure", "Multi DEV settings button wiring missing")
    require(gui, 'style="Panel.TLabelframe"', "Speed dialog must reuse GUI panel theme")
    require(gui, "ttk.Spinbox(", "Speed dialog controls must reuse ttk GUI theme")
    if "AUTO PRO cũ" in gui:
        raise AssertionError("Obsolete AUTO PRO label still leaks into Multi DEV settings")

    print("AUTO MULTI DEV SPEED CONFIG STATIC CONTRACT VERIFIED")
    print("floor_navigation=semantic-action-speed")
    print("plant_harvest=independent")
    print("vp_collect=shared-panel-min4x5=20+per-click-full-warehouse-guard+post-burst-settle")
    print("vp_production=product-owned")
    print("panel_speed_wiring=format-insensitive")
    print("floor6_empty_planting=format-insensitive")
    print("crop_check_interval=independent")
    print("clear_stall_drag_speed=per-profile+resident-runtime+two-swipes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
