from __future__ import annotations

import dis
import json
import marshal
import sys
from pathlib import Path
import types


ROOT = Path(__file__).resolve().parents[1]
MARSHAL_ROOT = ROOT / "source-archive/auto-pro-reference/recovery_notes/raw_marshal"
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


def summarize(code: types.CodeType, source: Path) -> dict:
    constants = []
    for value in code.co_consts:
        converted = printable(value)
        if converted is not None and converted not in constants:
            constants.append(converted)
    instructions = []
    for item in dis.get_instructions(code):
        if item.opname in {
            "LOAD_METHOD", "LOAD_ATTR", "LOAD_GLOBAL", "LOAD_CONST",
            "STORE_FAST", "LOAD_FAST", "COMPARE_OP", "BINARY_OP",
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
        "source": source.name,
        "name": code.co_name,
        "first_line": code.co_firstlineno,
        "args": list(code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]),
        "names": list(code.co_names),
        "constants": constants,
        "instructions": instructions,
    }


def load_marshaled_code(path: Path) -> types.CodeType | None:
    try:
        value = marshal.loads(path.read_bytes())
    except (EOFError, ValueError, TypeError):
        return None
    return value if isinstance(value, types.CodeType) else None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    if not MARSHAL_ROOT.is_dir():
        raise SystemExit(f"Không tìm thấy AUTO PRO marshal folder: {MARSHAL_ROOT}")

    found = []
    scanned = []
    for source in sorted(MARSHAL_ROOT.glob("*.marshal")):
        root = load_marshaled_code(source)
        if root is None:
            continue
        scanned.append(source.name)
        for code in walk(root):
            if code.co_name in TARGETS:
                found.append(summarize(code, source))

    present = {item["name"] for item in found}
    missing = sorted(TARGETS - present)
    print(json.dumps(
        {
            "source_root": str(MARSHAL_ROOT),
            "scanned": scanned,
            "targets": sorted(TARGETS),
            "missing": missing,
            "found": found,
        },
        ensure_ascii=True,
        indent=2,
    ))
    if missing:
        raise SystemExit(
            "Thiếu code object AUTO PRO: " + ", ".join(missing)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
