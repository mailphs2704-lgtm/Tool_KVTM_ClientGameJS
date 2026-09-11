from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, TypeVar

from .events import RecoveryEvent, RecoveryEventKind

if TYPE_CHECKING:
    from ..automation import KVAutomation


_T = TypeVar("_T")


@dataclass(frozen=True)
class ModuleCheckpoint:
    """Immutable checkpoint for one in-flight Function/Recipe module.

    The executor owns this checkpoint until the module returns successfully.
    Recoverable errors may move the game away from the work location, but they
    must not return control to the outer Function/scheduler as a completed step.
    """

    function_id: str
    module_id: str
    label: str
    floor: int | None = None
    interruption_count: int = 0
    last_error_type: str | None = None

    @property
    def key(self) -> str:
        floor = "unknown" if self.floor is None else str(self.floor)
        return f"{self.function_id}:{self.module_id}:floor={floor}"

    def interrupted(self, exc: Exception) -> "ModuleCheckpoint":
        return replace(
            self,
            interruption_count=self.interruption_count + 1,
            last_error_type=type(exc).__name__,
        )


ModuleErrorHandler = Callable[[ModuleCheckpoint, Exception], None]


class ModuleRecoveryExecutor:
    """Run one module behind a checkpoint until it completes or fails closed.

    Only exception types explicitly registered by the caller are recoverable.
    The same runner is retried after a handler restores the work location/state.
    Generic errors (including ScreenTimeout unless explicitly registered) escape
    immediately and therefore cannot be replayed blindly.
    """

    def __init__(
        self,
        automation: KVAutomation,
        *,
        function_id: str,
        emit: Callable[[RecoveryEvent], None],
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.function_id = str(function_id)
        self.emit = emit

    def _emit(
        self,
        kind: RecoveryEventKind,
        checkpoint: ModuleCheckpoint,
        *,
        error: Exception | None = None,
    ) -> None:
        self.emit(
            RecoveryEvent(
                kind,
                label=checkpoint.label,
                floor=checkpoint.floor,
                attempt=(
                    checkpoint.interruption_count
                    if checkpoint.interruption_count > 0
                    else None
                ),
                error=None if error is None else str(error),
                details={
                    "function_id": checkpoint.function_id,
                    "module_id": checkpoint.module_id,
                    "checkpoint": checkpoint.key,
                    "interruption_count": checkpoint.interruption_count,
                    "last_error_type": checkpoint.last_error_type,
                },
            )
        )

    @staticmethod
    def _select_handler(
        exc: Exception,
        handlers: Sequence[tuple[type[Exception], ModuleErrorHandler]],
    ) -> ModuleErrorHandler | None:
        for error_type, handler in handlers:
            if isinstance(exc, error_type):
                return handler
        return None

    def run(
        self,
        *,
        module_id: str,
        label: str,
        runner: Callable[[], _T],
        floor: int | None = None,
        handlers: Sequence[tuple[type[Exception], ModuleErrorHandler]] = (),
    ) -> _T:
        checkpoint = ModuleCheckpoint(
            function_id=self.function_id,
            module_id=str(module_id),
            label=str(label),
            floor=None if floor is None else int(floor),
        )
        self._emit(RecoveryEventKind.MODULE_STARTED, checkpoint)

        while True:
            self.context.ensure_running()
            try:
                result = runner()
            except Exception as exc:
                handler = self._select_handler(exc, handlers)
                if handler is None:
                    raise

                checkpoint = checkpoint.interrupted(exc)
                self.context.stage("auto-recovery-module-interrupted")
                self.context.log(
                    "AUTO recovery checkpoint • INTERRUPT • "
                    f"checkpoint={checkpoint.key} • "
                    f"error={checkpoint.last_error_type} • "
                    f"lần={checkpoint.interruption_count} • "
                    "GIỮ NGUYÊN module, chưa trả control về Function/AutoMain"
                )
                self._emit(
                    RecoveryEventKind.MODULE_INTERRUPTED,
                    checkpoint,
                    error=exc,
                )

                handler(checkpoint, exc)
                self.context.ensure_running()

                self.context.stage("auto-recovery-module-resume")
                self.context.log(
                    "AUTO recovery checkpoint • RESUME • "
                    f"checkpoint={checkpoint.key} • "
                    f"sau recovery lần={checkpoint.interruption_count} • "
                    "chạy tiếp cùng module trước khi cho phép vòng Function mới"
                )
                self._emit(RecoveryEventKind.MODULE_RESUMED, checkpoint)
                continue

            self.context.stage("auto-recovery-module-completed")
            self.context.detail(
                "AUTO recovery checkpoint | COMPLETED | "
                f"checkpoint={checkpoint.key} | "
                f"interruptions={checkpoint.interruption_count}"
            )
            self._emit(RecoveryEventKind.MODULE_COMPLETED, checkpoint)
            return result
