from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import sys
import time


def _configure_console() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Follow the KVTM DEV clear-stall DLL probe activity log."
    )
    parser.add_argument("--log", required=True)
    parser.add_argument("--done", required=True)
    parser.add_argument("--title", default="KVTM DEV - Clear Stall DLL Probe")
    return parser


def _print_header(title: str, log_path: Path) -> None:
    line = "=" * 78
    print(line)
    print(title)
    print(f"LOG: {log_path}")
    print("CMD này mở ngay khi bấm probe và theo dõi UI/PID/DLL/worker.")
    print("Đóng CMD không làm dừng probe; dùng nút Dừng trong Multi để dừng.")
    print(line)
    print(flush=True)


def main() -> int:
    _configure_console()
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
            print(f"[console] Lỗi đọc log: {exc}", flush=True)

        if done_path.exists() and idle_after_done >= 4:
            print("\n" + "=" * 78)
            print("Probe đã kết thúc. Giữ cửa sổ này để đọc/chụp log.")
            print("Nhấn ENTER để đóng CMD.")
            print("=" * 78, flush=True)
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass
            return 0
        time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
