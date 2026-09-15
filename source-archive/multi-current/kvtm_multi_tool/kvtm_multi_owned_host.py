from __future__ import annotations

import auto_builder_integration
import auto_error_log_integration
import clear_stall_window_position
import client_ownership_integration
import client_video_recorder
import daily_sale_counter_integration
import fps_hardcap_integration
import optional_features_integration
import stall_speed_integration


_ORIGINAL_BUILDER_INSTALL = auto_builder_integration.install_auto_builder_integration
_ORIGINAL_RECORDER_INSTALL = client_video_recorder.install_client_video_recorder


def _install_pre_ui_runtime_integrations(app_cls, core) -> None:
    # These integrations change the configuration schema consumed by the
    # profile/config dialogs. Stable must install them before the DEV host
    # builds any UI wrappers; installing at recorder time is already too late.
    client_ownership_integration.install_client_ownership_integration(app_cls, core)
    clear_stall_window_position.install_clear_stall_window_position(app_cls, core)
    stall_speed_integration.install_stall_speed_integration(app_cls, core)
    _ORIGINAL_BUILDER_INSTALL(app_cls, core)


def _install_runtime_integrations(app_cls, core) -> None:
    # Install after auto_main_profile_settings so this layer owns the final
    # FPS transport/menu methods and routes them to Bridge V3 hard-cap.
    fps_hardcap_integration.install_fps_hardcap_integration(app_cls, core)
    # Observational only: show persistent per-profile daily sale + pirate chest
    # counters in the account-detail panel. It does not alter Function/runtime.
    daily_sale_counter_integration.install_daily_sale_counter_integration(
        app_cls, core
    )
    # Persistent error diagnostics live beside action/detail logs and can be
    # exported as a plain UTF-8 TXT for later fix work.
    auto_error_log_integration.install_auto_error_log_integration(app_cls, core)
    # Optional features live beside the preserved Function selector in AUTO
    # MULTI DEV and freeze per-profile state into each worker run.
    optional_features_integration.install_optional_features_integration(
        app_cls, core
    )
    _ORIGINAL_RECORDER_INSTALL(app_cls, core)


auto_builder_integration.install_auto_builder_integration = (
    _install_pre_ui_runtime_integrations
)
client_video_recorder.install_client_video_recorder = _install_runtime_integrations

from kvtm_multi_dev_host import main


if __name__ == "__main__":
    raise SystemExit(main())
