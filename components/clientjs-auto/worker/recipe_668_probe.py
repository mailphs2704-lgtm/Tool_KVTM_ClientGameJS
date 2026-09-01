from __future__ import annotations

import argparse
import importlib
import inspect
import json
from pathlib import Path
import sys


METHODS = (
    "plantTrees",
    "makeItems",
    "harvestTrees",
    "produceItems_136",
    "produceItems_318",
)


def safe_method_report(owner, name: str) -> dict:
    method = getattr(owner, name, None)
    if not callable(method):
        return {"name": name, "found": False}
    report = {
        "name": name,
        "found": True,
        "signature": str(inspect.signature(method)),
    }
    code = getattr(method, "__code__", None)
    if code is not None:
        report["argument_names"] = list(code.co_varnames[: code.co_argcount])
        report["referenced_names"] = list(code.co_names)
        report["string_constants"] = [
            value for value in code.co_consts
            if isinstance(value, str) and 0 < len(value) <= 160
        ][:100]
        report["integer_constants"] = [
            value for value in code.co_consts
            if isinstance(value, int) and not isinstance(value, bool)
        ][:100]
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    auto_root = Path(args.auto_root).resolve()
    output = Path(args.output).resolve()
    if not (auto_root / "local_launcher.py").is_file():
        raise SystemExit(f"FAIL: missing {auto_root / 'local_launcher.py'}")

    sys.path.insert(0, str(auto_root))
    importlib.import_module("local_launcher")
    automation = importlib.import_module("automation")
    owner = automation.FarmAutomation

    payload = {
        "probe": "recipe_6_tinh_dau_6_vai_vang_8_tao_say",
        "read_only": True,
        "game_input_sent": False,
        "methods": [safe_method_report(owner, name) for name in METHODS],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"RECIPE 6-6-8 READ-ONLY PROBE COMPLETE")
    print(f"Report: {output}")
    for row in payload["methods"]:
        print(
            f"{row['name']}="
            f"{'FOUND ' + row.get('signature', '') if row['found'] else 'MISSING'}"
        )
    print("game_input_sent=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
