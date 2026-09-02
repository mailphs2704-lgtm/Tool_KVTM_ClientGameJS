from __future__ import annotations

import argparse
import dis
import importlib
import json
from pathlib import Path
import sys
import types


TOKENS = (
    "harvest", "thu_hoach", "thuhoach", "gieo", "plant", "crop",
    "swipe", "next_gieo", "harvest_speed", "go_up", "production",
)


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        fn = getattr(stream, "reconfigure", None)
        if callable(fn):
            fn(encoding="utf-8", errors="replace")


def walk_code(code: types.CodeType):
    yield code
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            yield from walk_code(value)


def inspect_class(owner: str, cls) -> list[dict]:
    found = []
    for method_name in sorted(dir(cls)):
        try:
            value = getattr(cls, method_name)
        except Exception:
            continue
        code = getattr(value, "__code__", None)
        if not isinstance(code, types.CodeType):
            continue
        chunks = []
        instructions = []
        for nested in walk_code(code):
            names = [str(item) for item in nested.co_names]
            strings = [item for item in nested.co_consts if isinstance(item, str)]
            chunks.extend(names)
            chunks.extend(strings)
            for item in dis.get_instructions(nested):
                if item.opname in {
                    "LOAD_ATTR", "STORE_ATTR", "LOAD_METHOD", "LOAD_GLOBAL",
                    "LOAD_FAST", "CALL", "CALL_FUNCTION", "CALL_METHOD",
                }:
                    instructions.append({
                        "code": nested.co_name,
                        "op": item.opname,
                        "arg": item.argrepr,
                    })
        searchable = " ".join(chunks).lower()
        matched = sorted(token for token in TOKENS if token in searchable)
        if not matched:
            continue
        found.append({
            "owner": owner,
            "method": method_name,
            "matched": matched,
            "names": sorted(set(str(item) for item in chunks))[:160],
            "instructions": instructions[:240],
        })
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    auto_root = Path(args.auto_root).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(auto_root))
    importlib.import_module("local_launcher")
    automation = importlib.import_module("automation")
    adb_controller = importlib.import_module("adb_controller")

    report = {
        "probe": "speed-binding-bytecode-read-only",
        "auto_root": str(auto_root),
        "classes": [
            {
                "owner": "FarmAutomation",
                "matches": inspect_class("FarmAutomation", automation.FarmAutomation),
            },
            {
                "owner": "ADBController",
                "matches": inspect_class("ADBController", adb_controller.ADBController),
            },
        ],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = []
    for group in report["classes"]:
        for item in group["matches"]:
            summary.append({
                "owner": item["owner"],
                "method": item["method"],
                "matched": item["matched"],
                "speed_names": [
                    name for name in item["names"]
                    if any(token in name.lower() for token in (
                        "speed", "harvest", "gieo", "swipe", "duration", "wait"
                    ))
                ],
            })
    print(json.dumps({
        "event": "speed_binding_probe_pass",
        "match_count": len(summary),
        "matches": summary,
        "report": str(output),
        "read_only": True,
    }, ensure_ascii=False, indent=2))
    return 0


configure_utf8()
if __name__ == "__main__":
    raise SystemExit(main())
