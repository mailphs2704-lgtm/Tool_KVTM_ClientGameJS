from __future__ import annotations

import client_ownership_integration
import client_video_recorder
import daily_sale_counter_integration
import fps_hardcap_integration


_ORIGINAL_RECORDER_INSTALL = client_video_recorder.install_client_video_recorder


def _install_runtime_integrations(app_cls, core) -> None:
    client_ownership_integration.install_client_ownership_integration(app_cls, core)
    # Install after auto_main_profile_settings so this layer owns the final
    # FPS transport/menu methods and routes them to Bridge V3 hard-cap.
    fps_hardcap_integration.install_fps_hardcap_integration(app_cls, core)
    # The daily sale counter is observational UI/state only. Install after the
    # final AUTO Main profile layer so it can place the counter directly under
    # the existing sale cadence control without changing Function logic.
    daily_sale_counter_integration.install_daily_sale_counter_integration(
        app_cls, core
    )
    _ORIGINAL_RECORDER_INSTALL(app_cls, core)


client_video_recorder.install_client_video_recorder = _install_runtime_integrations

from kvtm_multi_dev_host import main


if __name__ == "__main__":
    raise SystemExit(main())
