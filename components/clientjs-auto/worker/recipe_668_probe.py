from __future__ import annotations

import argparse
import dis
import importlib
import inspect
import json
from pathlib import Path
import sys


METHODS = (
    "plantTrees",
    "makeItems",
    "harvestTrees",
    "sellItems_10",
    "sellItems_318",
    "produceItems_97",
    "produceItems_98",
    "produceItems_136",
    "produceItems_318",
)


def code_report(method) -> dict:
    code = getattr(method, "__code__", None)
    if code is None:
        return {}
    instructions = []
    for item in dis.get_instructions(method):
        instructions.append({
            "offset": item.offset,
            "opname": item.opname,
            "argrepr": item.argrepr,
            "starts_line": item.starts_line,
        })
    return {
        "argument_names": list(code.co_varnames[: code.co_argcount]),
        "referenced_names": list(code.co_names),
        "string_constants": [
            value for value in code.co_consts
            if isinstance(value, str) and 0 < len(value) <= 160
        ][:200],
        "integer_constants": [
            value for value in code.co_consts
            if isinstance(value, int) and not isinstance(value, bool)
        ][:200],
        "instructions": instructions[:5000],
    }


def safe_method_report(owner, name: str) -> dict:
    method = getattr(owner, name, None)
    if not callable(method):
        return {"name": name, "found": False}
    return {
        "name": name,
        "found": True,
        "signature": str(inspect.signature(method)),
        **code_report(method),
    }


def owner_report(label: str, owner) -> dict:
    return {
        "owner": label,
        "methods": [safe_method_report(owner, name) for name in METHODS],
    }


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
    adb_controller = importlib.import_module("adb_controller")

    farm = automation.FarmAutomation
    produce_methods = sorted(
        name for name, value in vars(farm).items()
        if name.startswith("produceItems_") and callable(value)
    )
    produce_reports = [
        safe_method_report(farm, name) for name in produce_methods
    ]
    candidate_reports = []
    required_tokens = {"tinh_dau_hh", "vai_vang", "tao_say"}
    for report in produce_reports:
        strings = set(report.get("string_constants") or [])
        integers = set(report.get("integer_constants") or [])
        matched_tokens = sorted(required_tokens & strings)
        score = len(matched_tokens) * 10
        if 6 in integers:
            score += 2
        if 8 in integers:
            score += 2
        if score:
            candidate_reports.append({
                "name": report["name"],
                "signature": report.get("signature"),
                "matched_tokens": matched_tokens,
                "has_integer_6": 6 in integers,
                "has_integer_8": 8 in integers,
                "score": score,
                "string_constants": report.get("string_constants", []),
                "integer_constants": report.get("integer_constants", []),
            })
    candidate_reports.sort(key=lambda row: (-row["score"], row["name"]))

    owners = [owner_report("automation.FarmAutomation", farm)]
    for name, value in vars(adb_controller).items():
        if inspect.isclass(value) and any(
            callable(getattr(value, method_name, None))
            for method_name in ("plantTrees", "makeItems", "harvestTrees")
        ):
            owners.append(owner_report(f"adb_controller.{name}", value))

    payload = {
        "probe": "recipe_6_tinh_dau_6_vai_vang_8_tao_say_v4",
        "read_only": True,
        "game_input_sent": False,
        "produce_entrypoints": produce_methods,
        "recipe_candidates": candidate_reports,
        "owners": owners,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("RECIPE 6-6-8 READ-ONLY PROBE V4 COMPLETE")
    print(f"Report: {output}")
    print(f"produce_entrypoints={len(produce_methods)}")
    for row in candidate_reports[:20]:
        print(
            f"candidate={row['name']} score={row['score']} "
            f"tokens={','.join(row['matched_tokens'])} "
            f"has6={row['has_integer_6']} has8={row['has_integer_8']}"
        )
    for owner in owners:
        print(f"[{owner['owner']}]")
        for row in owner["methods"]:
            if row["found"]:
                print(f"  {row['name']}=FOUND {row.get('signature', '')}")
    print("game_input_sent=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
