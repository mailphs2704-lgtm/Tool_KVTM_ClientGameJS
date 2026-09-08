from __future__ import annotations

"""Read-only AUTO PRO bytecode inspector for the machine-repair handoff.

This tool never imports or executes AUTO PRO business code.  It only loads the
archived marshal code object and prints candidate functions / disassembly so a
clean implementation can be derived from the original behavior.
"""

import dis
import marshal
import sys
import types
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARSHAL = (
    ROOT
    / "source-archive/auto-pro-reference/recovery_notes/raw_marshal/automation.marshal"
)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value)).lower()
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def walk(code: types.CodeType, path: tuple[str, ...] = ()):
    current = path + (code.co_name,)
    yield current, code
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            yield from walk(value, current)


def direct_strings(code: types.CodeType) -> list[str]:
    return [value for value in code.co_consts if isinstance(value, str)]


def score(code: types.CodeType) -> tuple[int, list[str]]:
    haystacks = [code.co_name, getattr(code, "co_qualname", code.co_name)]
    haystacks.extend(code.co_names)
    haystacks.extend(direct_strings(code))
    joined = "\n".join(norm(item) for item in haystacks)

    hits: list[str] = []
    weighted = (
        ("repair", 15),
        ("sua may", 15),
        ("suamay", 15),
        ("fix machine", 15),
        ("fixmachine", 15),
        ("maintenance", 12),
        ("maintain", 10),
        ("bao tri", 10),
        ("bao duong", 10),
        ("machine", 6),
        ("may", 2),
    )
    total = 0
    for needle, weight in weighted:
        if needle in joined:
            total += weight
            hits.append(needle)

    produce_names = [name for name in code.co_names if str(name).startswith("produceItems")]
    if produce_names:
        total += 20
        hits.append("caller:" + ",".join(produce_names))
    if code.co_name.startswith("produceItems"):
        total += 8
        hits.append("producer")
    return total, hits


def compact_instruction(item: dis.Instruction) -> str:
    location = f"{item.offset:>5}"
    return f"{location} {item.opname:<28} {item.argrepr}"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if not MARSHAL.is_file():
        raise SystemExit(f"Missing AUTO PRO marshal: {MARSHAL}")

    value = marshal.loads(MARSHAL.read_bytes())
    if not isinstance(value, types.CodeType):
        raise SystemExit("AUTO PRO automation.marshal is not a code object")

    rows = []
    all_codes = list(walk(value))
    for path, code in all_codes:
        points, hits = score(code)
        if points:
            rows.append((points, path, code, hits))
    rows.sort(key=lambda item: (-item[0], item[1]))

    print("AUTO_PRO_MACHINE_REPAIR_SCAN")
    print(f"marshal={MARSHAL}")
    print(f"code_objects={len(all_codes)} candidates={len(rows)}")

    for ordinal, (points, path, code, hits) in enumerate(rows[:30], start=1):
        print("\n" + "=" * 88)
        print(
            f"CANDIDATE {ordinal} score={points} path={' > '.join(path)} "
            f"first_line={code.co_firstlineno} hits={hits}"
        )
        print(f"args={code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]}")
        print(f"names={code.co_names}")
        strings = direct_strings(code)
        if strings:
            print("strings=")
            for text in strings[:30]:
                print("  " + repr(text))
        print("disassembly=")
        instructions = list(dis.get_instructions(code))
        for item in instructions[:700]:
            print(compact_instruction(item))
        if len(instructions) > 700:
            print(f"... truncated {len(instructions) - 700} instructions ...")

    producer_callers = [
        (path, code)
        for path, code in all_codes
        if any(str(name).startswith("produceItems") for name in code.co_names)
    ]
    print("\n" + "#" * 88)
    print(f"PRODUCE_CALLERS={len(producer_callers)}")
    for path, code in producer_callers[:40]:
        print(
            f"CALLER path={' > '.join(path)} first_line={code.co_firstlineno} "
            f"produce_names={[n for n in code.co_names if str(n).startswith('produceItems')]}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
