from __future__ import annotations
import traceback

from local_launcher import AG
import local_bridge
import local_options_bridge_v08
import local_settings_bridge

if __name__ == "__main__":
    try:
        app = AG()
        local_bridge.start_bridge(app)
        local_options_bridge_v08.start_options_bridge(app)
        local_settings_bridge.start_settings_bridge(app)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("\nPress Enter to close...")
