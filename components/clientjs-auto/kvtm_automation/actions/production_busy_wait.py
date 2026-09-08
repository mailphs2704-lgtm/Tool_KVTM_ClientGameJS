from __future__ import annotations

from functools import wraps

from ..errors import ScreenTimeout
from .apple_juice_production import AppleJuiceProductionActions
from .production import ProductionActions
from .yellow_fabric_production import YellowFabricProductionActions


__all__ = ["install_production_busy_wait"]
FILE_FUNCTIONS = (
    "Chuyển riêng lỗi máy còn đang sản xuất thành WAIT + recheck thay vì kết thúc AUTO",
    "Chỉ retry các lỗi thiếu ô top/chưa đủ 9 ô trống đã xác định là trạng thái máy bận",
    "Giữ nguyên fail-close cho sai panel, sai vật phẩm, thiếu nguyên liệu và kho đầy",
    "Mọi vòng chờ đều stop-aware để nút Dừng AUTO sạch vẫn có hiệu lực",
)

_RECHECK_SECONDS = 1.0
_INSTALLED = False


def _log_wait(owner, label: str, reason: str, attempt: int) -> None:
    owner.context.stage("auto-production-machine-busy-wait")
    owner.context.log(
        f"AUTO {label} • máy còn đang sản xuất/chưa đủ 9 ô trống • "
        f"đợi {_RECHECK_SECONDS:.1f}s rồi kiểm tra lại • lần chờ={attempt} • {reason}"
    )


def _probe_product_after_reopen(owner, *, point: tuple[int, int], template: str) -> bool:
    """Disambiguate a combined product/top error after the original fail-close."""
    owner.context.ensure_running()
    owner.vision.driver.click(*point)
    owner.waiter.sleep(owner.speed_config.vp_collect_delay)
    product = owner.vision.find(
        template,
        threshold=0.70,
        zone=None,
        scales=(0.75, 0.90, 1.00, 1.10, 1.25),
        click=False,
    )
    # The previous transaction had already closed the verified panel. This
    # one-shot probe reopens only to decide busy-vs-wrong-panel; always close it
    # again before either retrying or propagating FAIL.
    owner.vision.driver.click(*owner.CLOSE_POINT)
    return product is not None


def _dried_busy(owner, exc: ScreenTimeout) -> bool:
    text = str(exc)
    return (
        "Không tìm thấy ô top bằng ảnh thư viện o_trong" in text
        or "Máy sấy chỉ có " in text and "/9 ô trống" in text
    )


def _juice_busy(owner, exc: ScreenTimeout) -> bool:
    text = str(exc)
    if "Máy Nước táo có " in text and "/9 ô trống" in text:
        return True
    if "Panel tầng 2 đã mở nhưng chưa xác minh được nuoc_tao hoặc ô top" in text:
        return _probe_product_after_reopen(
            owner, point=owner.MACHINE_POINT, template=owner.PRODUCT_TEMPLATE
        )
    return False


def _fabric_busy(owner, exc: ScreenTimeout) -> bool:
    text = str(exc)
    if "Máy Vải vàng có " in text and "/9 ô trống" in text:
        return True
    if "Panel tầng 3 đã mở nhưng chưa xác minh được vai_vang hoặc ô top" in text:
        return _probe_product_after_reopen(
            owner, point=owner.MACHINE_POINT, template=owner.PRODUCT_TEMPLATE
        )
    if "Không mở/xác minh được panel Vải vàng sau" in text:
        # A completely full/busy machine may expose no o_trong at all. Retry the
        # bounded open transaction after a cooperative wait; Stop still aborts.
        return True
    return False


def _wrap_open(original, *, label: str, busy_check):
    @wraps(original)
    def wrapped(owner, *args, **kwargs):
        wait_attempt = 0
        while True:
            owner.context.ensure_running()
            try:
                return original(owner, *args, **kwargs)
            except ScreenTimeout as exc:
                if not busy_check(owner, exc):
                    raise
                wait_attempt += 1
                _log_wait(owner, label, str(exc), wait_attempt)
                owner.waiter.sleep(_RECHECK_SECONDS)

    return wrapped


def install_production_busy_wait() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    ProductionActions._open_verified_dryer = _wrap_open(
        ProductionActions._open_verified_dryer,
        label="Táo sấy",
        busy_check=_dried_busy,
    )
    AppleJuiceProductionActions._open_verified = _wrap_open(
        AppleJuiceProductionActions._open_verified,
        label="Nước táo",
        busy_check=_juice_busy,
    )
    YellowFabricProductionActions._open_verified = _wrap_open(
        YellowFabricProductionActions._open_verified,
        label="Vải vàng",
        busy_check=_fabric_busy,
    )
