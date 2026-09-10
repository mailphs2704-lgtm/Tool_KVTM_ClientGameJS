from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any


__all__ = [
    "LOGICAL_REFERENCE_SIZE",
    "PRODUCTION_CLIENT_SIZE",
    "SUPPORTED_CLIENT_SIZES",
    "ClientResolutionContract",
    "NativeCaptureDriver",
    "classify_client_size",
    "detect_client_resolution",
    "disable_legacy_adaptive_matching",
]

FILE_FUNCTIONS = (
    "Giữ source AUTO ở hệ logical 1000x1000",
    "Chỉ đọc kích thước CAPTURE3 hiện tại; AUTO tuyệt đối không resize ClientJS",
    "Chọn contract 500x500 hoặc 1000x1000 theo đúng kích thước client đang chạy",
    "Giữ CAPTURE3 ở kích thước render thật thay vì bị EngineDriver phóng về reference 1000",
    "Fail-close nếu kích thước native đổi giữa lúc AUTO đang chạy",
    "Gỡ monkeypatch adaptive_cv cũ trong isolated worker để tránh scale template/frame lần hai",
)

LOGICAL_REFERENCE_SIZE = (1000, 1000)
# Compatibility marker only. AUTO no longer normalizes toward this value.
PRODUCTION_CLIENT_SIZE = (500, 500)
SUPPORTED_CLIENT_SIZES = ((500, 500), (1000, 1000))


@dataclass(frozen=True)
class ClientResolutionContract:
    """Passive AUTO contract selected from the ClientJS size that already exists."""

    name: str
    native_size: tuple[int, int]
    table_size: tuple[int, int]
    logical_reference_size: tuple[int, int] = LOGICAL_REFERENCE_SIZE

    @property
    def is_native_500(self) -> bool:
        return self.native_size == (500, 500)

    @property
    def is_native_1000(self) -> bool:
        return self.native_size == (1000, 1000)


def classify_client_size(size: tuple[int, int]) -> ClientResolutionContract:
    """Map an already-running ClientJS size to its recognition table.

    No resize is permitted here. Unsupported sizes stop before any AUTO click so
    a wrong table can never be applied to a different render geometry.
    """
    actual = tuple(map(int, size))
    if actual == (500, 500):
        return ClientResolutionContract(
            name="native-500",
            native_size=actual,
            table_size=(500, 500),
        )
    if actual == (1000, 1000):
        return ClientResolutionContract(
            name="native-1000",
            native_size=actual,
            table_size=(1000, 1000),
        )
    raise RuntimeError(
        "AUTO MULTI DEV chỉ có bảng nhận diện đã kiểm chứng cho ClientJS "
        "500x500 hoặc 1000x1000; actual="
        f"{actual[0]}x{actual[1]}. AUTO không resize ClientJS; "
        "hãy chọn kích thước trong GUI trước khi Bắt đầu AUTO."
    )


def disable_legacy_adaptive_matching() -> bool:
    """Restore native ``cv2.matchTemplate`` inside the isolated clean worker."""
    module = sys.modules.get("adaptive_cv")
    if module is None:
        return False
    original = getattr(module, "_ORIGINAL", None)
    installed = bool(getattr(module, "_INSTALLED", False))
    if not installed or original is None:
        return False

    import cv2

    cv2.matchTemplate = original
    try:
        module._INSTALLED = False
        module._ORIGINAL = None
    except Exception:
        pass
    return True


def _raw_capture(driver: Any):
    refresh = getattr(driver, "_refresh_profile_pid", None)
    if callable(refresh):
        refresh()
    capture = getattr(driver, "_capture_shared_bgra", None)
    if not callable(capture):
        raise RuntimeError(
            "Bridge V3 driver thiếu raw CAPTURE3 API; không thể đọc native resolution"
        )
    raw, width, height = capture()
    return raw, int(width), int(height)


def detect_client_resolution(driver: Any) -> ClientResolutionContract:
    """Read CAPTURE3 once and choose 500/1000 contract without touching HWND size."""
    _raw, width, height = _raw_capture(driver)
    return classify_client_size((width, height))


class NativeCaptureDriver:
    """Expose CAPTURE3 at its real size while preserving logical-1000 input.

    ``EngineDriver.screenshot()`` historically expands raw CAPTURE3 to its
    reference size. AUTO installs this adapter after Bridge construction so
    VisionEngine receives the true frame: 500 stays 500, 1000 stays 1000.

    The selected size is immutable for one worker run. If ClientJS changes size
    after AUTO starts, capture fails closed before the next click instead of
    silently switching recognition tables mid-transaction.
    """

    def __init__(
        self,
        driver: Any,
        *,
        contract: ClientResolutionContract,
    ) -> None:
        self._driver = driver
        self.contract = contract
        self.expected_size = tuple(map(int, contract.native_size))
        self.native_size = self.expected_size
        self.table_size = tuple(map(int, contract.table_size))
        self.resolution_name = str(contract.name)
        self.reference_size = tuple(
            map(int, getattr(driver, "reference_size", LOGICAL_REFERENCE_SIZE))
        )

    def __getattr__(self, name: str):
        return getattr(self._driver, name)

    def screenshot(self, format: str | None = None):
        raw, width, height = _raw_capture(self._driver)
        actual = (width, height)
        if actual != self.expected_size:
            raise RuntimeError(
                "AUTO MULTI DEV native CAPTURE3 đã đổi kích thước trong lúc chạy: "
                f"start={self.expected_size[0]}x{self.expected_size[1]}, "
                f"actual={actual[0]}x{actual[1]}. Dừng trước khi click để tránh "
                "dùng sai bảng nhận diện; AUTO không tự resize ClientJS."
            )

        # Keep legacy capture-scale observers coherent even though the adaptive
        # matcher itself is disabled. No image resizing is performed here.
        try:
            from adaptive_cv import set_capture_scale

            set_capture_scale(min(
                actual[0] / float(self.reference_size[0]),
                actual[1] / float(self.reference_size[1]),
                1.0,
            ))
        except Exception:
            pass

        if format == "opencv":
            import numpy as np

            return np.frombuffer(raw, dtype=np.uint8).reshape(
                (actual[1], actual[0], 4)
            )[:, :, :3].copy()

        from PIL import Image

        return Image.frombuffer(
            "RGBA", actual, raw, "raw", "BGRA", 0, 1
        ).convert("RGB")
