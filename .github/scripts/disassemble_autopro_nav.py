from __future__ import annotations

import dis
import marshal
from pathlib import Path
import types


ROOT = Path(__file__).resolve().parents[2]
PYC = ROOT / "source-archive" / "auto-pro-reference" / "runtime" / "pyc" / "adb_controller.pyc"
TARGETS = {
    "GoFiendHome",
    "GoFriendHome",
    "goKho",
    "GoKho",
    "goHome",
    "GoHome",
    "eventgame",
    "makeBuyItems",
    "sellItems",
}


def walk(code: types.CodeType):
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from walk(const)


def main() -> None:
    raw = PYC.read_bytes()
    root = marshal.loads(raw[16:])
    found = []
    for code in walk(root):
        if code.co_name not in TARGETS:
            continue
        found.append(code.co_name)
        print("\n" + "=" * 100)
        print(f"FUNCTION {code.co_name} line={code.co_firstlineno}")
        print(f"ARGS={code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]}")
        print(f"NAMES={code.co_names}")
        print("CONSTANTS:")
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                continue
            if isinstance(value, (str, int, float, tuple, list, dict, type(None), bool)):
                print(repr(value))
        print("DISASSEMBLY:")
        dis.dis(code)
    print("\nFOUND", sorted(set(found)))


if __name__ == "__main__":
    main()
