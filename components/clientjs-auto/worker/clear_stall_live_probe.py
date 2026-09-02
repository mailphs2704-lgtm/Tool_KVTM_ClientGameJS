from __future__ import annotations

import argparse
from pathlib import Path

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)
from clear_stall_probe_runtime import ProbeConfig, run_probe


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only clean ClientJS Dọn quầy DLL probe"
    )
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    parser.add_argument("--stall-id", dest="resale_storage_id", type=int, required=True)
    parser.add_argument("--quantity", type=int, default=10)
    parser.add_argument("--work-dir", required=True)
    return parser


def main() -> int:
    configure_utf8_stdio()
    install_component_path()
    args = _parser().parse_args()

    channel = StopChannel()
    channel.start()

    config = ProbeConfig(
        auto_root=Path(args.auto_root),
        pid=int(args.pid),
        profile_id=str(args.profile_id),
        profile_name=str(args.profile_name),
        friend_ordinal=int(args.friend_ordinal),
        resale_storage_id=int(args.resale_storage_id),
        buy_quantity=int(args.quantity),
        work_dir=Path(args.work_dir),
    )

    return run_probe(
        config,
        emit_event=lambda payload: emit(
            str(payload.get("event") or "probe_progress"),
            **{k: v for k, v in payload.items() if k != "event"},
        ),
        stop_event=channel.event,
        image_runtime_ready=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
