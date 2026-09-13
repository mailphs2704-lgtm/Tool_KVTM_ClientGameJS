from __future__ import annotations


__all__ = ["install_stall_speed_integration"]


def install_stall_speed_integration(app_class, core) -> None:
    """Expose the existing shop-drag timing in the MULTI DEV speed dialog.

    The base settings schema already owns ``shop_drag_speed``. MULTI DEV had
    omitted it from its visible tuning-key list, so the clean StallActions kept
    its 0.35s fallback regardless of the operator's intended sale drag speed.
    This layer only promotes the existing key into the DEV dialog; runtime
    consumption is owned by AutoSpeedConfig/KVAutomation.
    """
    del app_class

    core.DEFAULT_AUTO_TUNING.setdefault("shop_drag_speed", 0.35)
    core.AUTO_TUNING_SPECS.setdefault(
        "shop_drag_speed",
        ("Tốc độ kéo quầy", 0.05, 3.0, False),
    )

    keys = tuple(getattr(core, "MULTI_DEV_TUNING_KEYS", ()))
    if "shop_drag_speed" not in keys:
        try:
            index = keys.index("floor_swipe_duration") + 1
        except ValueError:
            keys = ("shop_drag_speed",) + keys
        else:
            keys = keys[:index] + ("shop_drag_speed",) + keys[index:]
        core.MULTI_DEV_TUNING_KEYS = keys

    core.AUTO_LEGACY_TUNING_KEYS = tuple(
        key
        for key in core.DEFAULT_AUTO_TUNING
        if key not in core.MULTI_DEV_TUNING_KEYS
    )

    print(
        "[KVTM DEV] Stall speed integration READY • "
        "shop_drag_speed=VISIBLE • clean runtime=WIRED",
        flush=True,
    )
