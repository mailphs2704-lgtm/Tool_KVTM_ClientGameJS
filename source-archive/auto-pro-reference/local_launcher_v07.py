from __future__ import annotations
import traceback

# Importing local_launcher performs all FIXED2 runtime/PyInstaller path setup,
# offline API patches and GUI license patches. Its __main__ block does not run.
from local_launcher import AG
import local_bridge
import local_options_bridge

if __name__ == "__main__":
    try:
        app = AG()
        local_bridge.start_bridge(app)
        local_options_bridge.start_options_bridge(app)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("\nPress Enter to close...")
