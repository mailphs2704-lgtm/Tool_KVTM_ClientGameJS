from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KVTM Dọn quầy standalone full-resale worker")
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--profile-file", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    parser.add_argument("--stall-id", type=int, required=True)
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--max-stall-passes", type=int, default=10)
    parser.add_argument("--allowed-items-json", default="[]")
    parser.add_argument("--drag-speed", type=float, default=0.35)
    parser.add_argument("--work-dir", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    runtime_root = Path(args.runtime_root).resolve()
    worker_dir = runtime_root / "components" / "clientjs-auto" / "worker"
    component_dir = runtime_root / "components" / "clientjs-auto"
    auto_root = runtime_root / "AUTO_PRO"
    for path in (worker_dir, component_dir, auto_root):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)

    os.environ["KVTM_MULTI_PROFILE_FILE"] = str(Path(args.profile_file).resolve())

    from clean_worker_support import StopChannel, configure_utf8_stdio, emit
    from clear_stall_probe_runtime import ProbeConfig, run_probe

    configure_utf8_stdio()
    try:
        allowed = json.loads(args.allowed_items_json)
        if not isinstance(allowed, list):
            raise ValueError("allowed-items-json phải là list")
    except (json.JSONDecodeError, ValueError) as exc:
        emit("probe_error", error=str(exc))
        return 2

    quantity = int(args.quantity)
    if quantity < 10 or quantity > 1000 or quantity % 10:
        emit("probe_error", error="Số lượng Dọn quầy phải là bội số 10 trong 10..1000")
        return 2
    purchase_limit = quantity // 10

    channel = StopChannel()
    channel.start()
    config = ProbeConfig(
        auto_root=auto_root,
        pid=int(args.pid),
        profile_id=str(args.profile_id),
        profile_name=str(args.profile_name),
        friend_ordinal=int(args.friend_ordinal),
        resale_storage_id=int(args.stall_id),
        buy_quantity=quantity,
        work_dir=Path(args.work_dir),
        purchase_limit=purchase_limit,
        max_stall_passes=int(args.max_stall_passes),
        resale_batch_limit=purchase_limit,
        allowed_item_ids=tuple(str(x) for x in allowed),
        clear_stall_drag_speed=float(args.drag_speed),
    )
    return run_probe(
        config,
        emit_event=lambda payload: emit(
            str(payload.get("event") or "probe_progress"),
            **{key: value for key, value in payload.items() if key != "event"},
        ),
        stop_event=channel.event,
        image_runtime_ready=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
