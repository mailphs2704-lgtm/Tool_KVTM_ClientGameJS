from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not (ROOT / "local_launcher.py").is_file():
    raise SystemExit("Hãy giải nén gói Engine Bridge vào thư mục AUTO có local_launcher.py")

sys.path.insert(0, str(ROOT))

import local_launcher  # noqa: E402
import gui  # noqa: E402
import gui_device  # noqa: E402
import uiautomator2 as u2  # noqa: E402
from engine_driver import EngineDriver  # noqa: E402
from adaptive_cv import install_adaptive_matching  # noqa: E402

install_adaptive_matching()

PC_PREFIX = "PC:"
_original_connect = u2.connect


def pc_connect(device_id=None, *args, **kwargs):
    value = str(device_id or "")
    if value.startswith(PC_PREFIX):
        return EngineDriver(int(value[len(PC_PREFIX):]), reference_size=(1000, 1000))
    return _original_connect(device_id, *args, **kwargs)


u2.connect = pc_connect

# Reuse the proven device discovery patches, but prevent its old PCDriver
# connect patch from replacing EngineDriver afterwards.
import pc_auto_launcher as old_bridge  # noqa: E402,F401
u2.connect = pc_connect


if __name__ == "__main__":
    app = gui.AutomationGUI()
    app.mainloop()
