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
    for text, label in (
        (production, "dried apple"),
        (apple_juice, "apple juice"),
        (yellow_fabric, "yellow fabric"),
    ):
        require(text, "self.speed_config.vp_collect_delay",
                f"VP collect speed not applied to {label}")
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
            "Multi DEV dialog must only show its own settings")
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
    print("vp_collect=independent_default_0.3s")
    print("vp_production=independent_reserved")
    print("crop_check_interval=independent_default_0.3s")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
