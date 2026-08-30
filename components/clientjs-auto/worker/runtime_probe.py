from __future__ import annotations

import argparse
import importlib
import inspect
import json
from pathlib import Path
import sys


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--function-id", type=int, default=136)
    args = parser.parse_args()

    auto_root = Path(args.auto_root).resolve()
    if not (auto_root / "local_launcher.py").is_file():
        emit("probe_error", error="Thiếu local_launcher.py", auto_root=str(auto_root))
        return 2

    sys.path.insert(0, str(auto_root))
    try:
        importlib.import_module("local_launcher")
        automation = importlib.import_module("automation")
        required_modules = (
            "adb_controller", "image_processor", "engine_driver",
            "pc_driver", "adaptive_cv", "clientjs_auto_patch",
        )
        for name in required_modules:
            importlib.import_module(name)

        entrypoint = f"produceItems_{args.function_id}"
        method = getattr(automation.FarmAutomation, entrypoint, None)
        if not callable(method):
            raise RuntimeError(f"Không tìm thấy FarmAutomation.{entrypoint}")

        emit(
            "probe_ok",
            function_id=args.function_id,
            entrypoint=f"FarmAutomation.{entrypoint}",
            automation_signature=str(inspect.signature(automation.FarmAutomation)),
            auto_root=str(auto_root),
        )
        return 0
    except Exception as exc:
        emit("probe_error", function_id=args.function_id, error=repr(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
