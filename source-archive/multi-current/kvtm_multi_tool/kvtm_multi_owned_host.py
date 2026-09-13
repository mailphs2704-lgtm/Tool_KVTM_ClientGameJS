from __future__ import annotations

import clear_stall_window_position
import client_ownership_integration
import client_video_recorder
import daily_sale_counter_integration
import fps_hardcap_integration
import optional_features_integration
import stall_speed_integration


_ORIGINAL_RECORDER_INSTALL = client_video_recorder.install_client_video_recorder


def _install_runtime_integrations(app_cls, core) -> None:
    client_ownership_integration.install_client_ownership_integration(app_cls, core)
    clear_stall_window_position.install_clear_stall_window_position(app_cls, core)
    # MULTI DEV must expose the independent shop-drag timing before its speed
    # dialog is built; clean runtime consumes the same key through AutoSpeedConfig.
    stall_speed_integration.install_stall_speed_integration(app_cls, core)
    # Install after auto_main_profile_settings so this layer owns the final
    # FPS transport/menu methods and routes them to Bridge V3 hard-cap.
    fps_hardcap_integration.install_fps_hardcap_integration(app_cls, core)
    # Observational only: show the persistent per-profile daily sale-turn count
    # in the existing LƯỢT BÁN AUTO account-detail field. It does not alter
    # Function, recovery, Bridge, capture, or scheduler behavior.
    daily_sale_counter_integration.install_daily_sale_counter_integration(
        app_cls, core
    )
    # Optional features live beside the preserved Function selector in AUTO
    # MULTI DEV and freeze per-profile state into each worker run.
    optional_features_integration.install_optional_features_integration(
        app_cls, core
    )
    _ORIGINAL_RECORDER_INSTALL(app_cls, core)


client_video_recorder.install_client_video_recorder = _install_runtime_integrations

from kvtm_multi_dev_host import main


if __name__ == "__main__":
    raise SystemExit(main())
