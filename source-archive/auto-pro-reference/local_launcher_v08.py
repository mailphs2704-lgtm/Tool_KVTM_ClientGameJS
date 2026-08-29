from __future__ import annotations
import traceback

# Importing local_launcher performs all FIXED2 runtime/PyInstaller path setup,
# offline API patches and GUI license patches. Its __main__ block does not run.
from local_launcher import AG
import local_bridge
import local_options_bridge_v08

if __name__ == "__main__":
    try:
        app = AG()
        # Keep the proven TaskManager bridge and add the v0.8 dynamic Tk option
        # bridge. Both are localhost-only and run inside this exact GUI process.
        local_bridge.start_bridge(app)
        local_options_bridge_v08.start_options_bridge(app)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("\nPress Enter to close...")
