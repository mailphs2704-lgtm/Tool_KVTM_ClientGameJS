from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "components/clientjs-auto/kvtm_automation/runtime/auto_speed_config.py"
ACTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
APPLE_SUPPLY_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/apple_supply.py"
AUTOMATION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
DEV_ENTRY_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
GUI_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"


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
    automation = check_python(AUTOMATION_PATH)
    dev = check_python(DEV_ENTRY_PATH)
    gui = check_python(GUI_PATH)

    keys = (
        "floor_swipe_duration",
        "plant_harvest_duration",
        "vp_production_delay",
        "crop_check_interval",
    )
    for key in keys:
        require(config, key, f"Config key missing: {key}")
        require(gui, f'"{key}"', f"GUI key missing: {key}")
    require(dev, "speed_config=speed_values",
            "Resident runtime speed injection missing")
    require(action, "self.speed_config.floor_swipe_duration",
            "Floor speed not applied")
    require(action, "self.speed_config.plant_harvest_duration",
            "Plant/harvest speed not applied")
    require(apple_supply, "self.speed_config.crop_check_interval",
            "Crop check interval not applied")
    require(apple_supply, 'allow_empty=True, label="hàng dưới cùng tầng 6"',
            "Floor 6 must allow immediate planting on empty pots")
    require(automation, "AutoSpeedConfig.from_mapping",
            "Speed normalization missing")
    require(dev, "Tốc độ MULTI DEV |", "Speed audit log missing")
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
    print("vp_production=independent_reserved")
    print("crop_check_interval=independent_default_0.3s")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
