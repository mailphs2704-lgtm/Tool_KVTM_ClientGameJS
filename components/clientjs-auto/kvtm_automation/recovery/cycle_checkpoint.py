from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar, cast


_T = TypeVar("_T")
_MISSING = object()


class CycleCheckpoint:
    """In-memory side-effect locks for one in-flight Function cycle.

    A lock survives scheduler/global-recovery retries because the owning
    Function workflow is retained until its completion gate passes.  It is
    deliberately cleared only by ``commit_cycle`` at that boundary.
    """

    def __init__(self, context, *, function_id: str) -> None:
        self.context = context
        self.function_id = str(function_id)
        self._completed: dict[str, object] = {}

    def has(self, key: str) -> bool:
        return str(key) in self._completed

    def get(self, key: str) -> object:
        value = self._completed.get(str(key), _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def run_once(
        self,
        key: str,
        *,
        label: str,
        runner: Callable[[], _T],
        on_replay: Callable[[], None] | None = None,
    ) -> _T:
        normalized = str(key)
        value = self._completed.get(normalized, _MISSING)
        if value is not _MISSING:
            self.context.stage(
                f"auto-cycle-lock-{self.function_id}-{normalized}-replay"
            )
            self.context.log(
                f"AUTO khóa giai đoạn • {label} đã PASS • bỏ qua thao tác lặp"
            )
            if on_replay is not None:
                on_replay()
            return cast(_T, value)

        result = runner()
        self._completed[normalized] = result
        self.context.stage(
            f"auto-cycle-lock-{self.function_id}-{normalized}-completed"
        )
        self.context.log(
            f"AUTO khóa giai đoạn • {label} PASS • khóa tới khi Function hoàn tất"
        )
        return result

    def commit_cycle(self) -> None:
        count = len(self._completed)
        self._completed.clear()
        self.context.stage(f"auto-cycle-lock-{self.function_id}-committed")
        self.context.log(
            f"AUTO khóa giai đoạn • Function completion gate PASS • "
            f"xóa {count} khóa để bắt đầu vòng mới"
        )
