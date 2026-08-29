from __future__ import annotations
import os, sys, traceback, shutil
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
PYC = ROOT / "runtime" / "pyc"
INTERNAL = ROOT / "_internal"

if sys.version_info[:2] != (3, 11):
    raise SystemExit("AUTO KVTM PRO local recovery requires Python 3.11.x. Run: py -3.11 local_launcher.py")

def sync_pyinstaller_package_files():
    """Merge PyInstaller package files into recovered .pyc packages.

    The recovered Python packages live under runtime/pyc, while PyInstaller
    placed native extensions *and package data* under _internal. Normal Python
    does not merge those directories. Besides PIL/_imaging.pyd this affects
    uiautomator2/assets/u2.jar and APK resources required when connecting to a
    device, adbutils/binaries/adb.exe, certifi/cacert.pem, and similar data.
    Copy every file belonging to a package that exists in runtime/pyc.
    """
    copied = 0
    for src in INTERNAL.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(INTERNAL)
        if len(rel.parts) < 2:
            continue
        package_root = PYC / rel.parts[0]
        if not package_root.exists():
            continue
        dst = PYC / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if (not dst.exists()) or src.stat().st_size != dst.stat().st_size:
                shutil.copy2(src, dst)
                copied += 1
        except OSError:
            # Files are also pre-synchronized in the fixed archive. This is a
            # self-repair fallback for incomplete extraction/copy operations.
            pass
    return copied

sync_pyinstaller_package_files()

# Make recovered bytecode and bundled native dependencies importable.
sys.path.insert(0, str(PYC))
sys.path.insert(0, str(INTERNAL))
for sub in ("win32", "win32/lib", "Pythonwin", "pywin32_system32"):
    p = INTERNAL / sub
    if p.exists(): sys.path.insert(0, str(p))
if hasattr(os, "add_dll_directory"):
    for p in (INTERNAL, INTERNAL/"cv2", INTERNAL/"numpy.libs", INTERNAL/"pywin32_system32", INTERNAL/"Pythonwin"):
        if p.exists():
            try: os.add_dll_directory(str(p))
            except OSError: pass
os.environ["PATH"] = str(INTERNAL) + os.pathsep + str(ROOT/"platform-tools") + os.pathsep + os.environ.get("PATH", "")
os.chdir(ROOT)

# Fail early with a useful message if the most common native dependency is broken.
try:
    from PIL import _imaging as _pil_imaging  # noqa: F401
except Exception as exc:
    raise RuntimeError(
        "Pillow native runtime could not be loaded. Re-extract the FIXED package "
        "to a new folder and run RUN_LOCAL.bat. Original error: " + repr(exc)
    ) from exc

import local_api
import gui_base
local_api.install_gui_base(gui_base)

# Import popup module only after API functions have been replaced.
import gui_popups

class LocalLoginPopup:
    """Drop-in login replacement: no key, no server, grants local access."""
    def __init__(self, parent, on_login_success=None, *args, **kwargs):
        self.parent = parent
        self.on_login_success = on_login_success
        self.current_device_id = "LOCAL-DEVICE"
        self.token = "LOCAL-OFFLINE"
        self.auth = local_api.local_profile()
        if on_login_success:
            # Schedule after constructor returns so AutomationGUI.login_popup is assigned first.
            parent.after(100, self._finish_login)
    def _finish_login(self):
        p = local_api.local_profile()
        self.on_login_success(p["name"], p["expired_at"], p["functions"], p["wallet"], p["ref_id"])
    def get_latest_version(self): return None
    def destroy(self): pass
    def protocol(self, *a, **k): pass
    def deiconify(self): pass
    def withdraw(self): pass
    def grab_set(self): pass

# Must patch before gui imports names from gui_popups.
gui_popups.LoginPopup = LocalLoginPopup

import gui
# Defensive: star-imports can snapshot LoginPopup.
gui.LoginPopup = LocalLoginPopup

# Disable recurring server/license/update checks at GUI level as well.
AG = gui.AutomationGUI
AG.get_license_key = lambda self: "LOCAL"
AG.get_device_id = lambda self: "LOCAL-DEVICE"
AG.start_expiration_scheduler = lambda self: None
AG.check_license_validity = lambda self: True
AG.check_key_validity_now = lambda self: True
AG._maybe_show_login_notice = lambda self: None
AG._check_update_after_login = lambda self: None
AG._check_completed_orders_after_login = lambda self: None
AG.send_telegram_notification = lambda self, *a, **k: None
AG.send_registration_renewal_notification = lambda self, *a, **k: None

if __name__ == "__main__":
    try:
        app = AG()
        # Run a localhost-only bridge INSIDE this exact GUI process.
        # The web dashboard now reads/controls the REAL TaskManager that the
        # launcher is using, so a task started from the launcher no longer
        # appears as "DỪNG" on the web.
        import local_bridge
        local_bridge.start_bridge(app)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("\nPress Enter to close...")
