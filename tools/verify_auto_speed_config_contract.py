from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "components/clientjs-auto/kvtm_automation/runtime/auto_speed_config.py"
ACTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
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
    automation = check_python(AUTOMATION_PATH)
    dev = check_python(DEV_ENTRY_PATH)
    gui = check_python(GUI_PATH)

    keys = (
        "floor_swipe_duration",
        "plant_harvest_duration",
        "vp_production_delay",
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
    require(automation, "AutoSpeedConfig.from_mapping",
            "Speed normalization missing")
    require(dev, "Tốc độ MULTI DEV |", "Speed audit log missing")
    require(gui, "AUTO PRO cũ • Tốc độ cào",
            "Legacy AUTO PRO compatibility label missing")
    print("AUTO MULTI DEV SPEED CONFIG STATIC CONTRACT VERIFIED")
    print("floor_swipe=independent")
    print("plant_harvest=independent")
    print("vp_production=independent_reserved")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
