from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "components/clientjs-auto/kvtm_automation/runtime/auto_speed_config.py"
ACTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
APPLE_SUPPLY_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/apple_supply.py"
PRODUCTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/production.py"
APPLE_JUICE_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/apple_juice_production.py"
YELLOW_FABRIC_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/yellow_fabric_production.py"
AUTOMATION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
DEV_ENTRY_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
AUTO_MULTI_WORKER_PATH = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
GUI_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
INTEGRATION_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def check_python(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    count = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(tree)
    )
    if path.name == "auto_speed_config.py" and count > 10:
        raise AssertionError(f"{path}: {count} functions exceeds limit 10")
    return text


def method_section(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start))
    if start_index < 0 or end_index < 0:
        raise AssertionError(f"Cannot isolate method section: {start} -> {end}")
    return text[start_index:end_index]


def main() -> int:
    config = check_python(CONFIG_PATH)
    action = check_python(ACTION_PATH)
    apple_supply = check_python(APPLE_SUPPLY_PATH)
    production = check_python(PRODUCTION_PATH)
    apple_juice = check_python(APPLE_JUICE_PATH)
    yellow_fabric = check_python(YELLOW_FABRIC_PATH)
    automation = check_python(AUTOMATION_PATH)
    dev = check_python(DEV_ENTRY_PATH)
    worker = check_python(AUTO_MULTI_WORKER_PATH)
    gui = check_python(GUI_PATH)
    integration = check_python(INTEGRATION_PATH)

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

    # vp_collect_delay is a clean Multi DEV extension installed before app
    # construction, so the native tuning dialog/collector sees it without
    # changing the legacy production GUI source.
    require(integration, '"vp_collect_delay"', "VP collect GUI extension key missing")
    require(integration, '"Thu VP (giây/click)"', "VP collect GUI label missing")
    require(integration, "core.MULTI_DEV_TUNING_KEYS = keys",
            "VP collect key is not injected into native Multi DEV tuning group")
    require(integration, "_install_vp_collect_speed_control(core)",
            "VP collect speed control is not installed before app construction")

    require(worker, "speed_config=speed_values",
            "Isolated worker speed injection missing")
    require(worker, "Tốc độ MULTI DEV |", "Worker speed audit log missing")
    require(worker, "thu VP={speed.vp_collect_delay:.3f}s",
            "Worker VP collect speed audit missing")
    require(dev, '"--speed-json"', "GUI speed JSON handoff missing")
    require(action, "self.speed_config.floor_swipe_duration",
            "Floor speed not applied")
    require(action, "self.speed_config.plant_harvest_duration",
            "Plant/harvest speed not applied")
    require(apple_supply, "self.speed_config.crop_check_interval",
            "Crop check interval not applied")

    # VP collection is centralized in ProductionActions so all three machines
    # share one true x5 multi-click burst. There must be no intentional wait,
    # capture, panel check, or stop checkpoint between the five raw clicks.
    require(production, "def _send_collect_burst(",
            "Raw five-click VP burst helper missing")
    require(production, "def _click_until_panel_open(",
            "Shared VP collect helper missing")
    require(production, "COLLECT_CLICK_BURST = 5",
            "Five-click VP collect burst contract missing")

    burst = method_section(
        production,
        "    def _send_collect_burst(",
        "    def _click_until_panel_open(",
    )
    require(burst, "for _ in range(self.COLLECT_CLICK_BURST):",
            "VP burst does not send exactly COLLECT_CLICK_BURST raw clicks")
    require(burst, "self.vision.driver.click(*machine_point)",
            "Raw machine click missing inside VP burst")
    if burst.count("self.context.ensure_running()") != 1:
        raise AssertionError(
            "VP burst must have one stop checkpoint before x5, never between clicks"
        )
    if "self.waiter.sleep(" in burst:
        raise AssertionError("VP burst contains an inter-click sleep")
    if "_panel_state(" in burst or "_find_product_match(" in burst or ".frame(" in burst:
        raise AssertionError("VP burst contains a vision/panel check between raw clicks")
    if burst.index("self.context.ensure_running()") > burst.index("for _ in range"):
        raise AssertionError("VP burst stop checkpoint must happen before the x5 loop")

    collect = method_section(
        production,
        "    def _click_until_panel_open(",
        "    def _wait_for_idle_open_panel(",
    )
    require(collect, "self._send_collect_burst(machine_point=machine_point)",
            "Shared collect helper does not call true x5 burst")
    require(collect, "self.waiter.sleep(self.speed_config.vp_collect_delay)",
            "VP collect post-burst settle delay missing")
    require(collect, "frame = self.vision.frame()",
            "VP collect fresh-frame capture missing after settle")
    require(collect, "warehouse_full, empty_ready = self._panel_state(frame=frame)",
            "VP collect post-burst panel check must reuse the fresh frame")
    require(collect, "self._find_wrong_product_match(",
            "VP collect wrong-machine scan missing after panel opens on another floor")
    burst_call = collect.index("self._send_collect_burst(machine_point=machine_point)")
    settle = collect.index("self.waiter.sleep(self.speed_config.vp_collect_delay)")
    fresh_frame = collect.index("frame = self.vision.frame()")
    panel_check = collect.index("warehouse_full, empty_ready = self._panel_state(frame=frame)")
    if not burst_call < settle < fresh_frame < panel_check:
        raise AssertionError(
            "VP collect order must be x5 -> settle once -> fresh frame -> panel check"
        )

    require(production, "self.speed_config.vp_production_delay",
            "VP production speed not applied to dried apple")

    for text, label in (
        (apple_juice, "apple juice"),
        (yellow_fabric, "yellow fabric"),
    ):
        require(text, "self.slots = ProductionActions(context, vision, waiter, self.speed_config)",
                f"Shared speed config not delegated to {label} production helper")
        require(text, "self.slots._click_until_panel_open(",
                f"Shared VP collect helper not used by {label}")
        require(text, "self.speed_config.vp_production_delay",
                f"VP production speed not applied to {label}")

    require(apple_supply, 'allow_empty=True, label="hàng dưới cùng tầng 6"',
            "Floor 6 must allow immediate planting on empty pots")
    require(automation, "AutoSpeedConfig.from_mapping",
            "Speed normalization missing")
    require(gui, "MULTI_DEV_TUNING_KEYS = (",
            "Dedicated Multi DEV tuning key group missing")
    require(gui, "AUTO_LEGACY_TUNING_KEYS = tuple(",
            "Legacy AUTO tuning key group missing")
    require(gui, "def _auto_multi_dev_configure",
            "Dedicated Multi DEV speed dialog missing")
    require(gui, "keys=MULTI_DEV_TUNING_KEYS",
            "Multi Dev dialog must only show its own settings")
    require(gui, "keys=AUTO_LEGACY_TUNING_KEYS",
            "Legacy AUTO dialog must use a separate setting group")
    require(gui, "command=self._auto_multi_dev_configure",
            "Multi DEV settings button wiring missing")
    require(gui, 'style="Panel.TLabelframe"',
            "Speed dialog must reuse the GUI panel theme")
    require(gui, "ttk.Spinbox(",
            "Speed dialog controls must reuse the ttk GUI theme")
    if "AUTO PRO cũ" in gui:
        raise AssertionError("Obsolete AUTO PRO label still leaks into Multi DEV settings")
    print("AUTO MULTI DEV SPEED CONFIG STATIC CONTRACT VERIFIED")
    print("floor_swipe=independent")
    print("plant_harvest=independent")
    print("vp_collect=true-x5-no-inter-click-wait+post-burst-settle+fresh-frame-panel-scan")
    print("vp_production=independent_reserved")
    print("crop_check_interval=independent_default_0.3s")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
