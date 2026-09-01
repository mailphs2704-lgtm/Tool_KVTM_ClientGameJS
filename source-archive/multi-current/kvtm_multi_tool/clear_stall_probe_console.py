from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Follow the KVTM DEV clear-stall probe activity log."
    )
    parser.add_argument("--log", required=True)
    parser.add_argument("--done", required=True)
    parser.add_argument("--title", default="KVTM DEV - Clear Stall Probe")
    return parser


def _print_header(title: str, log_path: Path) -> None:
    line = "=" * 78
    print(line)
    print(title)
    print(f"LOG: {log_path}")
    print("Cua so nay chi hien log. Dong cua so khong dung probe dang chay.")
    print(line)
    print(flush=True)


def main() -> int:
    args = _parser().parse_args()
    log_path = Path(args.log).resolve()
    done_path = Path(args.done).resolve()
    _print_header(str(args.title), log_path)

    position = 0
    idle_after_done = 0
    while True:
        try:
            if log_path.is_file():
                with log_path.open("r", encoding="utf-8", errors="replace") as stream:
                    stream.seek(position)
                    chunk = stream.read()
                    position = stream.tell()
                if chunk:
                    sys.stdout.write(chunk)
                    if not chunk.endswith("\n"):
                        sys.stdout.write("\n")
                    sys.stdout.flush()
                    idle_after_done = 0
                elif done_path.exists():
                    idle_after_done += 1
            elif done_path.exists():
                idle_after_done += 1
        except (OSError, ValueError) as exc:
            print(f"[console] Loi doc log: {exc}", flush=True)

        if done_path.exists() and idle_after_done >= 4:
            print("\n[console] Probe da ket thuc. Cua so se dong sau 2 giay.", flush=True)
            time.sleep(2.0)
            return 0
        time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
