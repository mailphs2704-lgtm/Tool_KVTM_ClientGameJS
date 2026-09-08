from __future__ import annotations

import ctypes
import re
import struct
import time


__all__ = ["install_capture3_same_request_wait"]

_HEADER_FORMAT = "<4s9IQ"
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)
_FILE_MAP_READ = 0x0004
_MAX_CAPTURE_BYTES = 64 * 1024 * 1024
_POLL_ATTEMPTS = 30
_POLL_DELAY_SECONDS = 0.01
_WRITER_ID_RE = re.compile(r"^[0-9A-Fa-f]{16}$")


def install_capture3_same_request_wait(engine_driver_module) -> None:
    """Read exactly the mapping owned by the native writer that answered CAPTUREW.

    The first CAPTURE3 repair stopped re-issuing CAPTURE while waiting for one
    response frame. Live evidence then exposed a deeper identity split: the same
    frame id could have coherent but different response/shared dimensions. That
    cannot be repaired safely by accepting either image or by extending retries.

    The WRITERMAP2 native contract gives every injected writer a unique mapping
    generation. AUTO MULTI DEV sends one CAPTUREW command, receives the writer id
    together with the expected frame, opens only that writer-specific mapping,
    and polls only that object. Stale frames, writer mismatch and HWND fallback
    remain forbidden.
    """

    driver_class = engine_driver_module.EngineDriver
    if getattr(driver_class, "_kvtm_capture3_same_request_wait", False):
        return

    kernel32 = engine_driver_module.kernel32

    def _capture_shared_bgra(self):
        with self._pipe_lock:
            response = self._pipe("CAPTUREW\n", 3000)
            parts = response.split()
            if len(parts) != 7 or parts[:2] != ["OK", "FRAMEW"]:
                raise RuntimeError(
                    "Phản hồi CAPTURE3 WRITERMAP2 không hợp lệ: " + response
                )
            try:
                expected_frame, expected_width, expected_height, expected_stride = map(
                    int, parts[2:6]
                )
            except ValueError as exc:
                raise RuntimeError(
                    "Metadata CAPTURE3 WRITERMAP2 không hợp lệ: " + response
                ) from exc
            writer_id = parts[6]
            if not _WRITER_ID_RE.fullmatch(writer_id):
                raise RuntimeError(
                    f"Writer id CAPTURE3 không hợp lệ: {writer_id!r}"
                )
            writer_id = writer_id.upper()
            mapping_name = (
                rf"Local\KVTM-CaptureV3-{int(self.pid)}-{writer_id}"
            )

            handle = kernel32.OpenFileMappingW(
                _FILE_MAP_READ, False, mapping_name
            )
            if not handle:
                raise RuntimeError(
                    "Không mở được shared mapping đúng writer CAPTURE3 "
                    f"(writer={writer_id}, mapping={mapping_name})"
                )

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
                        raise RuntimeError(
                            "Shared capture header WRITERMAP2 không hợp lệ "
                            f"(writer={writer_id})"
                        )

                    if status != 2 or frame_id < expected_frame:
                        last_error = RuntimeError(
                            "Shared capture frame chưa hoàn tất hoặc cũ hơn phản hồi "
                            f"(writer={writer_id}, expected={expected_frame}, "
                            f"actual={frame_id}, status={status})"
                        )
                    elif frame_id > expected_frame:
                        # CAPTUREW is serialized by one persistent pipe owner and
                        # this driver's RLock. A newer frame in the same writer map
                        # is evidence of a second consumer/command source, not a
                        # reason to silently accept a different screenshot.
                        raise RuntimeError(
                            "Shared capture WRITERMAP2 có frame ngoài request "
                            f"(writer={writer_id}, expected={expected_frame}, "
                            f"actual={frame_id})"
                        )
                    elif (width, height, stride) != (
                        expected_width,
                        expected_height,
                        expected_stride,
                    ):
                        last_error = RuntimeError(
                            "Kích thước shared capture không khớp phản hồi cùng writer "
                            f"(writer={writer_id}, frame={frame_id}, "
                            f"response={expected_width}x{expected_height} "
                            f"stride={expected_stride}, shared={width}x{height} "
                            f"stride={stride})"
                        )
                    elif (
                        pixel_format != 2
                        or stride != width * 4
                        or buffer_size != stride * height
                        or buffer_size > _MAX_CAPTURE_BYTES
                    ):
                        raise RuntimeError(
                            "Định dạng shared capture không được hỗ trợ "
                            f"(writer={writer_id})"
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
                            "Shared capture frame thay đổi trong lúc sao chép "
                            f"(writer={writer_id})"
                        )

                    self._trace(
                        "v3_capture_writer_map_wait",
                        poll=poll,
                        max_polls=_POLL_ATTEMPTS,
                        writer_id=writer_id,
                        expected_frame=expected_frame,
                        actual_frame=frame_id,
                        status=status,
                        error=str(last_error),
                    )
                    if poll < _POLL_ATTEMPTS:
                        time.sleep(_POLL_DELAY_SECONDS)

                raise RuntimeError(
                    "Shared capture WRITERMAP2 không ổn định sau "
                    f"{_POLL_ATTEMPTS} lần đọc cùng CAPTUREW; "
                    "không phát request mới và không đổi writer: "
                    f"{last_error}"
                )
            finally:
                if view:
                    kernel32.UnmapViewOfFile(view)
                kernel32.CloseHandle(handle)

    driver_class._capture_shared_bgra = _capture_shared_bgra
    driver_class._kvtm_capture3_same_request_wait = True
