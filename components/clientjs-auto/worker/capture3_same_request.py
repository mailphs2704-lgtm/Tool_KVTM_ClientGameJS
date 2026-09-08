from __future__ import annotations

import ctypes
import struct
import time


__all__ = ["install_capture3_same_request_wait"]

_HEADER_FORMAT = "<4s9IQ"
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)
_FILE_MAP_READ = 0x0004
_MAX_CAPTURE_BYTES = 64 * 1024 * 1024
_POLL_ATTEMPTS = 30
_POLL_DELAY_SECONDS = 0.01


def install_capture3_same_request_wait(engine_driver_module) -> None:
    """Keep one CAPTURE response fixed while waiting for its shared frame.

    The legacy retry loop re-issued CAPTURE after a transient stale-header read.
    That advances the response frame id again before the reader has proved that
    the previous response was published, so a lag can turn into a moving target
    (for example expected=23 while shared memory is still frame 12).

    AUTO MULTI DEV instead sends exactly one CAPTURE command, then polls the
    lifetime-fixed CAPTURE3 mapping for that same expected frame. The stale-frame
    guard remains strict: no older frame is accepted, no HWND fallback is added,
    and a frame that never reaches the response id still fails closed.
    """

    driver_class = engine_driver_module.EngineDriver
    if getattr(driver_class, "_kvtm_capture3_same_request_wait", False):
        return

    kernel32 = engine_driver_module.kernel32

    def _capture_shared_bgra(self):
        with self._pipe_lock:
            response = self._pipe("CAPTURE\n", 3000)
            parts = response.split()
            if len(parts) != 6 or parts[:2] != ["OK", "FRAME"]:
                raise RuntimeError(f"Phản hồi capture không hợp lệ: {response}")
            expected_frame, expected_width, expected_height, expected_stride = map(
                int, parts[2:]
            )

            handle = kernel32.OpenFileMappingW(
                _FILE_MAP_READ, False, self.capture_mapping_name
            )
            if not handle:
                raise ctypes.WinError()

            view = None
            last_error: Exception | None = None
            try:
                view = kernel32.MapViewOfFile(
                    handle, _FILE_MAP_READ, 0, 0, 0
                )
                if not view:
                    raise ctypes.WinError()

                for poll in range(1, _POLL_ATTEMPTS + 1):
                    values = struct.unpack(
                        _HEADER_FORMAT,
                        ctypes.string_at(view, _HEADER_SIZE),
                    )
                    (
                        magic,
                        version,
                        mapped_header_size,
                        width,
                        height,
                        stride,
                        pixel_format,
                        buffer_size,
                        frame_id,
                        status,
                        _timestamp_ms,
                    ) = values

                    if (
                        magic != b"KCAP"
                        or version != 3
                        or mapped_header_size < _HEADER_SIZE
                    ):
                        raise RuntimeError("Shared capture header không hợp lệ")

                    if status != 2 or frame_id < expected_frame:
                        last_error = RuntimeError(
                            "Shared capture frame chưa hoàn tất hoặc cũ hơn phản hồi "
                            f"(expected={expected_frame}, actual={frame_id}, status={status})"
                        )
                    elif frame_id == expected_frame and (
                        width,
                        height,
                        stride,
                    ) != (
                        expected_width,
                        expected_height,
                        expected_stride,
                    ):
                        last_error = RuntimeError(
                            "Kích thước shared capture không khớp phản hồi "
                            f"(frame={frame_id}, response={expected_width}x{expected_height} "
                            f"stride={expected_stride}, shared={width}x{height} stride={stride})"
                        )
                    elif (
                        pixel_format != 2
                        or stride != width * 4
                        or buffer_size != stride * height
                        or buffer_size > _MAX_CAPTURE_BYTES
                    ):
                        raise RuntimeError(
                            "Định dạng shared capture không được hỗ trợ"
                        )
                    else:
                        snapshot_key = (
                            version,
                            mapped_header_size,
                            width,
                            height,
                            stride,
                            pixel_format,
                            buffer_size,
                            frame_id,
                            status,
                        )
                        raw = ctypes.string_at(
                            int(view) + mapped_header_size,
                            buffer_size,
                        )
                        verified = struct.unpack(
                            _HEADER_FORMAT,
                            ctypes.string_at(view, _HEADER_SIZE),
                        )
                        verified_key = tuple(verified[1:10])
                        if verified_key == snapshot_key and verified[9] == 2:
                            return raw, width, height
                        last_error = RuntimeError(
                            "Shared capture frame thay đổi trong lúc sao chép"
                        )

                    self._trace(
                        "v3_capture_same_request_wait",
                        poll=poll,
                        max_polls=_POLL_ATTEMPTS,
                        expected_frame=expected_frame,
                        actual_frame=frame_id,
                        status=status,
                        error=str(last_error),
                    )
                    if poll < _POLL_ATTEMPTS:
                        time.sleep(_POLL_DELAY_SECONDS)

                raise RuntimeError(
                    "Shared capture không ổn định sau "
                    f"{_POLL_ATTEMPTS} lần đọc cùng CAPTURE; "
                    "không phát CAPTURE mới khi chờ publish: "
                    f"{last_error}"
                )
            finally:
                if view:
                    kernel32.UnmapViewOfFile(view)
                kernel32.CloseHandle(handle)

    driver_class._capture_shared_bgra = _capture_shared_bgra
    driver_class._kvtm_capture3_same_request_wait = True
