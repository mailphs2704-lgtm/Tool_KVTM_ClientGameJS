from __future__ import annotations

"""Static contract for passive dual-resolution AUTO MULTI DEV.

AUTO must preserve the ClientJS size selected by the user/profile. CAPTURE3 is
read at its native size and selects either the 500x500 or 1000x1000 recognition
contract. Business/input geometry remains logical 1000x1000 in both modes.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
VISION = CLEAN / "runtime/vision.py"
DRIVER_FACTORY = CLEAN / "runtime/driver.py"
RESOLUTION = CLEAN / "runtime/resolution.py"
AUTOMATION = CLEAN / "automation.py"
PRODUCTION = CLEAN / "actions/production.py"
INVENTORY = CLEAN / "actions/inventory.py"
STALL = CLEAN / "actions/stall.py"
STALL_AD = CLEAN / "actions/stall_advertising.py"
PLANTING = CLEAN / "actions/planting.py"
AUTO_MAIN_SELLING = CLEAN / "actions/auto_main_selling.py"
SELLING = CLEAN / "actions/selling.py"
BUILDER_MATCH = CLEAN / "workflows/auto_builder/image_match.py"

AUDITED_DIRECT_MATCH = {
    Path("runtime/vision.py"),
    Path("runtime/down_floor_button.py"),
    Path("actions/production.py"),
    Path("actions/inventory.py"),
    Path("workflows/auto_builder/image_match.py"),
}


def read_python(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing resolution file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def _scan_direct_matchers() -> None:
    unreviewed: list[str] = []
    for path in CLEAN.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        if "cv2.matchTemplate(" not in text:
            continue
        relative = path.relative_to(CLEAN)
        if relative not in AUDITED_DIRECT_MATCH:
            unreviewed.append(str(relative).replace("\\", "/"))
    if unreviewed:
        raise AssertionError(
            "Unreviewed direct cv2.matchTemplate bypasses VisionEngine: "
            + ", ".join(sorted(unreviewed))
        )


def main() -> int:
    vision = read_python(VISION)
    driver = read_python(DRIVER_FACTORY)
    resolution = read_python(RESOLUTION)
    automation = read_python(AUTOMATION)
    production = read_python(PRODUCTION)
    inventory = read_python(INVENTORY)
    stall = read_python(STALL)
    stall_ad = read_python(STALL_AD)
    planting = read_python(PLANTING)
    auto_main_selling = read_python(AUTO_MAIN_SELLING)
    selling = read_python(SELLING)
    builder_match = read_python(BUILDER_MATCH)

    if driver.count("reference_size=(1000, 1000)") < 2:
        raise AssertionError(
            "Bridge/raw driver input contract must remain logical 1000x1000"
        )

    require(resolution, "LOGICAL_REFERENCE_SIZE = (1000, 1000)",
            "Logical reference changed")
    require(resolution, "SUPPORTED_CLIENT_SIZES = ((500, 500), (1000, 1000))",
            "AUTO must support both existing 500 and 1000 clients")
    require(resolution, "class ClientResolutionContract:",
            "Resolution contract object missing")
    require(resolution, 'name="native-500"', "500 contract missing")
    require(resolution, 'name="native-1000"', "1000 contract missing")
    require(resolution, "def detect_client_resolution(",
            "Passive CAPTURE3 resolution detector missing")
    require(resolution, "class NativeCaptureDriver:",
            "Native CAPTURE3 adapter missing")
    require(resolution, "self.native_size = self.expected_size",
            "Native size is not exposed to recognition actions")
    require(resolution, "AUTO không resize ClientJS",
            "Fail-close no-resize contract message missing")
    forbid(resolution, "SetWindowPos(",
           "AUTO resolution module must never resize a ClientJS window")
    forbid(resolution, "AdjustWindowRectEx", "AUTO resolution module still resizes HWND")
    forbid(resolution, "def _resize_client(", "AUTO resize helper must stay removed")
    forbid(resolution, "def ensure_production_client_size(",
           "AUTO production-size forcing helper must stay removed")
    forbid(resolution, "cv2.resize(",
           "Native CAPTURE3 adapter must not upscale frames")

    require(automation, "disable_legacy_adaptive_matching()",
            "Legacy adaptive matcher is not disabled")
    require(automation, "bundle = self.driver_factory.engine(",
            "Bridge construction missing")
    require(automation, "contract = detect_client_resolution(self.driver)",
            "AUTO does not detect the already-running native size")
    require(automation, "NativeCaptureDriver(",
            "AUTO does not expose native CAPTURE3 to Vision")
    require(automation, "preserve-client-size", "Passive resolution runtime log missing")
    require(automation, "table=", "Selected recognition-table runtime log missing")
    require(automation, "no-resize", "No-resize runtime evidence marker missing")
    forbid(automation, "ensure_production_client_size(",
           "Bắt đầu AUTO must not force ClientJS to 500")
    forbid(automation, "target=PRODUCTION_CLIENT_SIZE",
           "AUTO still binds startup to fixed 500 target")
    bridge_at = automation.index("bundle = self.driver_factory.engine(")
    detect_at = automation.index("contract = detect_client_resolution(self.driver)")
    wrap_at = automation.index("self.driver = NativeCaptureDriver(")
    vision_at = automation.index("self.vision = VisionEngine(")
    if not (bridge_at < detect_at < wrap_at < vision_at):
        raise AssertionError(
            "Required order is Bridge -> passive detect -> native adapter -> Vision"
        )

    require(vision, "REFERENCE_SIZE = (1000, 1000)", "Vision logical reference changed")
    require(vision, "def frame_scales(", "Frame scale helper missing")
    require(vision, "self.logical_zone_to_frame(zone, source)",
            "Vision does not map logical ROI to current native frame")
    require(vision, "template.shape[1] * frame_sx * scale",
            "Vision template width is not native-frame aware")
    require(vision, "template.shape[0] * frame_sy * scale",
            "Vision template height is not native-frame aware")
    require(vision, "center=self.frame_point_to_logical(frame_center, source)",
            "Vision match center is not returned logical")

    require(production, "self.vision.logical_zone_to_frame(zone, frame)",
            "Production direct ROI is not resolution-aware")
    require(inventory, "self.vision.logical_zone_to_frame(",
            "Inventory direct ROI is not resolution-aware")
    require(inventory, "N500_PICKER_THRESHOLD = 0.72",
            "Native500 picker table missing")
    require(inventory, "N1000_PICKER_THRESHOLD = 0.82",
            "Native1000 picker table missing")
    require(inventory, "N500_STORAGE2_ACTIVE_THRESHOLD = 0.46",
            "Native500 storage2 active calibration missing")
    require(inventory, "contract=1000-baseline",
            "Native1000 sale/storage baseline marker missing")
    require(stall, "self.vision.logical_zone_to_frame(",
            "Stall ROI is not resolution-aware")
    require(stall_ad, "self.vision.logical_zone_to_frame(zone, frame)",
            "Advertising ROI is not resolution-aware")
    require(planting, "self.vision.logical_zone_to_frame(",
            "Planting diagnostic ROI is not resolution-aware")
    require(builder_match, "automation.vision.logical_zone_to_frame(",
            "Builder custom-image ROI is not resolution-aware")

    for label, source in (
        ("AUTO Main sale", auto_main_selling),
        ("Selling/resale", selling),
    ):
        require(source, "SALE_CHANGE_ZONE = (180, 330, 640, 430)",
                f"{label} logical sale-change zone missing")
        require(source, "def _sale_change_crop(self):",
                f"{label} resolution-aware sale-change crop missing")
        require(source, "logical_zone_to_frame(",
                f"{label} sale-change crop is not native aware")
        forbid(source, "frame()[330:760, 180:820]",
               f"{label} regressed to direct 1000-frame slicing")

    require(selling, "N500_SALE_DIALOG_THRESHOLD = 0.68",
            "Native500 sale-dialog table missing")
    require(selling, "N1000_SALE_DIALOG_THRESHOLD = 0.78",
            "Native1000 sale-dialog table missing")
    require(auto_main_selling, "N500_EXACT_TEN_THRESHOLD = 0.78",
            "Native500 x10 table missing")
    require(auto_main_selling, "N1000_EXACT_TEN_THRESHOLD = 0.95",
            "Native1000 x10 baseline missing")

    _scan_direct_matchers()

    print("AUTO MULTI DEV DUAL RESOLUTION CONTRACT VERIFIED")
    print("logical_reference=1000x1000")
    print("supported_native=500x500,1000x1000")
    print("startup=preserve-existing-client-size+no-resize")
    print("capture=native-CAPTURE3-no-upscale")
    print("recognition_table=selected-from-native-size")
    print("input=logical1000->actual-client-once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
