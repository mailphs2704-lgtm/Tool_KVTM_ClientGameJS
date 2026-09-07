from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / "components/clientjs-auto/kvtm_automation/runtime/driver.py"
ENGINE = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"
NATIVE = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
PACKAGE = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    texts = {}
    for path in (FACTORY, ENGINE, NATIVE, PACKAGE):
        if not path.is_file():
            raise AssertionError(f"Missing Bridge V3 contract file: {path}")
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            ast.parse(source, filename=str(path))
        texts[path] = source

    factory = texts[FACTORY]
    engine = texts[ENGINE]
    native = texts[NATIVE]
    package = texts[PACKAGE]

    require(factory, '_load_module("engine_driver")',
            "Multi Dev does not select EngineDriver V3")
    require(factory, 'driver._pipe("PING\\n", 1000)',
            "Strict V3 PING gate missing")
    for token in ("KVTM_BRIDGE_V3", "CAPTURE3", "INPUT4",
                  "BATCH_SWIPE", "NO_LAYOUT"):
        require(factory, token, f"Factory V3 capability gate missing: {token}")
        require(native, token, f"Native V3 capability missing: {token}")

    if "CocosBridgeDriver(" in factory or "kvtm_bridge.dll" in factory:
        raise AssertionError("AUTO MULTI DEV still wires the legacy CAPTURE1 bridge")

    require(engine, 'command = f"SWIPE {segment_steps}',
            "EngineDriver native batch command missing")
    require(engine, 'pipe_mode="single_batch"',
            "Single-batch timing evidence missing")
    require(package, '"kvtm_loader_v3.exe", "kvtm_bridge_v3.dll"',
            "V3 binaries are not packaged")

    print("AUTO MULTI DEV BRIDGE V3 CONTRACT VERIFIED")
    print("protocol=KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT")
    print("legacy_capture1_fallback=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
