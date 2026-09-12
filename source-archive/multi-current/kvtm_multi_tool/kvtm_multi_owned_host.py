from __future__ import annotations

"""Resident Multi host with cross-tool ClientJS ownership enabled.

This wrapper deliberately leaves kvtm_multi.py and the proven AUTO runtime untouched.
It decorates the existing recorder installer before kvtm_multi_dev_host.main() creates
MultiDevApp, so launch/adopt/stop ownership is active from the first UI instance.
"""

import client_video_recorder
from client_ownership_integration import install_client_ownership_integration
import kvtm_multi_dev_host


_original_install_client_video_recorder = client_video_recorder.install_client_video_recorder


def _install_runtime_integrations(app_cls, core) -> None:
    install_client_ownership_integration(app_cls, core)
    _original_install_client_video_recorder(app_cls, core)


client_video_recorder.install_client_video_recorder = _install_runtime_integrations


if __name__ == "__main__":
    raise SystemExit(kvtm_multi_dev_host.main())
