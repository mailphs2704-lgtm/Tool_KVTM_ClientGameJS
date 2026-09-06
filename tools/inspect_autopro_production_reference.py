from __future__ import annotations

import dis
import json
import marshal
import sys
from pathlib import Path
import types


ROOT = Path(__file__).resolve().parents[1]
MARSHAL_FILE = (
    ROOT / "source-archive/auto-pro-reference/recovery_notes/raw_marshal/"
    "automation.marshal"
)
TARGETS = {"makeItems", "goUp", "goDownLast", "produceItems_293"}


def walk(code: types.CodeType):
    yield code
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            yield from walk(value)


def printable(value):
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, tuple):
        converted = [printable(item) for item in value]
        return converted if all(item is not None for item in converted) else None
    return None


def summarize(code: types.CodeType) -> dict:
    constants = []
    for value in code.co_consts:
        converted = printable(value)
        if converted is not None and converted not in constants:
            constants.append(converted)
    instructions = []
    for item in dis.get_instructions(code):
        if item.opname in {
            "LOAD_METHOD", "LOAD_ATTR", "LOAD_GLOBAL", "LOAD_CONST",
            "KW_NAMES", "CALL", "PRECALL",
        }:
            instructions.append(
                {
                    "offset": item.offset,
                    "op": item.opname,
                    "arg": item.argrepr,
                }
            )
    return {
        "name": code.co_name,
        "first_line": code.co_firstlineno,
        "args": list(code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]),
        "names": list(code.co_names),
        "constants": constants,
        "instructions": instructions,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    if not MARSHAL_FILE.is_file():
        raise SystemExit(f"Không tìm thấy AUTO PRO marshal: {MARSHAL_FILE}")
    root = marshal.loads(MARSHAL_FILE.read_bytes())
    found = [
        summarize(code)
        for code in walk(root)
        if code.co_name in TARGETS
    ]
    print(json.dumps(
        {
            "source": str(MARSHAL_FILE),
            "targets": sorted(TARGETS),
            "found": found,
        },
        ensure_ascii=True,
        indent=2,
    ))
    if not any(item["name"] == "makeItems" for item in found):
        raise SystemExit("Không tìm thấy makeItems trong AUTO PRO reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
