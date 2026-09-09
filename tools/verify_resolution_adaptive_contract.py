from __future__ import annotations

"""Static contract for logical-1000 / resizable ClientJS AUTO runtime.

The production target of this migration is 500x500, but business coordinates
must stay in the established 1000x1000 logical space. This verifier intentionally
checks architecture rather than image scores; live template quality is proven by
operator smoke after packaging.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
VISION = CLEAN / "runtime/vision.py"
DRIVER_FACTORY = CLEAN / "runtime/driver.py"
RESOLUTION = CLEAN / "runtime/resolution.py"
AUTOMATION = CLEAN / "automation.py"
DOWN_FLOOR = CLEAN / "runtime/down_floor_button.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
PRODUCTION = CLEAN / "actions/production.py"
INVENTORY = CLEAN / "actions/inventory.py"
STALL = CLEAN / "actions/stall.py"
BUILDER_MATCH = CLEAN / "workflows/auto_builder/image_match.py"

# Direct OpenCV matching is allowed only in modules explicitly audited for the
# logical/frame contract. Every normal action should use VisionEngine.find().
AUDITED_DIRECT_MATCH = {
    Path("runtime/vision.py"),
    Path("runtime/down_floor_button.py"),
    Path("actions/production.py"),
    Path("actions/inventory.py"),
    Path("workflows/auto_builder/image_match.py"),
}


def read_python(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing adaptive-resolution file: {path}")
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
        # Assignment/restoration such as ``cv2.matchTemplate = original`` is not
        # a direct matcher. Only executable calls bypassing VisionEngine matter.
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
    down_floor = read_python(DOWN_FLOOR)
    pass_nav = read_python(PASS_THREE_NAV)
    production = read_python(PRODUCTION)
    inventory = read_python(INVENTORY)
    stall = read_python(STALL)
    builder_match = read_python(BUILDER_MATCH)

    # Input contract: actions continue sending logical 1000 coordinates. The
    # driver owns the one-and-only final logical -> real client conversion.
    if driver.count("reference_size=(1000, 1000)") < 2:
        raise AssertionError(
            "Both raw and Bridge V3 drivers must keep logical reference_size=1000x1000"
        )

    # Production-size normalization is scoped to AUTO MULTI DEV and must happen
    # before Bridge V3 is constructed. The stable window catches Multi's delayed
    # generic display callback when an offline profile was just launched.
    require(resolution, "LOGICAL_REFERENCE_SIZE = (1000, 1000)",
            "Resolution logical reference changed")
    require(resolution, "PRODUCTION_CLIENT_SIZE = (500, 500)",
            "Production ClientJS target must be 500x500")
    require(resolution, "def ensure_production_client_size(",
            "Production client-size normalizer missing")
    require(resolution, "stable_seconds: float = 2.0",
            "Production resize stability guard missing")
    require(resolution, "def disable_legacy_adaptive_matching()",
            "Legacy adaptive matcher neutralizer missing")
    require(resolution, "cv2.matchTemplate = original",
            "Legacy adaptive matcher is not restored to native OpenCV")
    require(automation, 'str(part).casefold() == "auto-multi-dev"',
            "500 production resize is not scoped to AUTO MULTI DEV work-dir")
    require(automation, "disable_legacy_adaptive_matching()",
            "AUTO MULTI DEV does not neutralize legacy double scaling")
    require(automation, "ensure_production_client_size(",
            "AUTO MULTI DEV does not enforce production client size")
    require(automation, "target=PRODUCTION_CLIENT_SIZE",
            "AUTO MULTI DEV normalizer is not bound to canonical 500 target")
    require(automation, "resize ổn định trước Bridge V3",
            "Production resolution readiness log missing")
    disable_at = automation.index("disable_legacy_adaptive_matching()")
    normalize_at = automation.index("ensure_production_client_size(")
    bridge_at = automation.index("bundle = self.driver_factory.engine(")
    if not (disable_at < normalize_at < bridge_at):
        raise AssertionError(
            "Legacy adaptive removal and 500 normalization must finish before Bridge V3"
        )

    # Central vision transform.
    require(vision, "REFERENCE_SIZE = (1000, 1000)",
            "Vision logical reference changed")
    require(vision, "def frame_scales(", "Frame scale helper missing")
    require(vision, "def logical_point_to_frame(",
            "Logical point -> frame helper missing")
    require(vision, "def frame_point_to_logical(",
            "Frame point -> logical helper missing")
    require(vision, "def logical_zone_to_frame(",
            "Logical ROI -> frame helper missing")
    require(vision, "def frame_box_to_logical(",
            "Frame box -> logical helper missing")
    require(vision, "self.logical_zone_to_frame(zone, source)",
            "Vision.find does not scale logical ROI")
    require(vision, "template.shape[1] * frame_sx * scale",
            "Vision template width is not scaled to real frame")
    require(vision, "template.shape[0] * frame_sy * scale",
            "Vision template height is not scaled to real frame")
    require(vision, "center=self.frame_point_to_logical(frame_center, source)",
            "Vision match center is not returned in logical coordinates")
    require(vision, "box=self.frame_box_to_logical(frame_box, source)",
            "Vision match box is not returned in logical coordinates")
    require(vision, "self.driver.click(*best.center)",
            "Vision click path no longer uses logical returned center")
    forbid(vision, "x, y, w, h = map(int, zone)",
           "Legacy frame-pixel interpretation of logical zone returned")

    # Repeated empty-slot counter is a special direct matcher. It must reuse the
    # same transforms and de-duplicate in logical units, otherwise 500x500 would
    # under-count slots because MIN_DISTANCE would accidentally remain 34 pixels.
    require(production, "self.vision.logical_zone_to_frame(zone, frame)",
            "Production repeated-slot ROI is not resolution-aware")
    require(production, "self.vision.frame_scales(frame)",
            "Production repeated-slot template scale missing")
    require(production, "self.vision.frame_point_to_logical(frame_center, frame)",
            "Production repeated-slot centers are not logical")
    require(production, "self.MIN_DISTANCE ** 2", "Logical slot de-dup gate missing")
    forbid(production, "x, y, width, height = zone",
           "Production returned to direct logical-zone frame slicing")

    # Runtime-captured stall fingerprints are already in current frame pixels.
    # Only the inventory ROI and returned click center are transformed. This is
    # intentionally different from static library templates in VisionEngine.
    require(inventory, "self.vision.logical_zone_to_frame(",
            "Inventory fingerprint ROI is not logical->frame")
    require(inventory, "self.INVENTORY_ZONE, frame",
            "Inventory fingerprint does not map the canonical logical zone")
    require(inventory, "self.vision.frame_point_to_logical(",
            "Inventory fingerprint center is not returned logical")
    forbid(inventory, "x, y, width, height = self.INVENTORY_ZONE",
           "Inventory regressed to direct logical-zone frame slicing")

    # Builder zones/click geometry are stored as logical 0..1000. Custom Builder
    # templates use the same reference-space convention and therefore scale into
    # the actual frame before direct OpenCV matching.
    require(builder_match, "automation.vision.logical_zone_to_frame(",
            "Builder recognize-image zone is not resolution-aware")
    require(builder_match, "automation.vision.frame_scales(source)",
            "Builder recognize-image frame scale missing")
    require(builder_match, "image.shape[1] * frame_sx * scale",
            "Builder template width is not frame-scaled")
    require(builder_match, "image.shape[0] * frame_sy * scale",
            "Builder template height is not frame-scaled")
    require(builder_match, "automation.vision.frame_point_to_logical(",
            "Builder match center is not logical")
    require(builder_match, "automation.vision.frame_box_to_logical(",
            "Builder match box is not logical")
    forbid(builder_match, "x, y, w, h = map(int, zone)",
           "Builder regressed to frame-pixel interpretation of logical zone")

    # Sale/friend-stall has direct color/crop logic in addition to VisionEngine.
    # Those ROIs must be mapped from logical geometry and the old 1000-pixel coin
    # count must scale by frame area. 500x500 must also be accepted by scan_view.
    require(stall, "self.vision.logical_zone_to_frame(",
            "Stall direct crop/color ROI is not resolution-aware")
    require(stall, "120.0 * frame_sx * frame_sy",
            "Stall coin pixel threshold is not scaled by frame area")
    require(stall, "if frame_sx < 0.40 or frame_sy < 0.40:",
            "Stall scan does not accept canonical 500x500 frames")
    require(stall, "icon = self.crop_icon(source, local_slot)",
            "Stall scan bypasses resolution-aware icon crop")
    require(stall, "def crop_icon(self, frame: Any, local_slot: int):",
            "Stall logical icon crop helper missing")
    forbid(stall, "if width < 800 or height < 750:",
           "Stall still rejects 500x500 runtime")
    forbid(stall, "roi = frame[top:bottom, cx + 10 : cx + 48]",
           "Stall price-coin ROI still uses raw logical pixels")

    # Dedicated XUỐNG detector already uses proportional ROI and 0.50 base scale
    # for the 500 target. Its public center must be logical before the existing
    # navigation caller sends it to the logical driver.
    require(down_floor, "base_scale = max(0.50",
            "XUỐNG detector no longer supports 500 template scale")
    require(down_floor, "def _frame_point_to_logical(",
            "XUỐNG frame -> logical helper missing")
    require(down_floor, "center=_frame_point_to_logical(",
            "XUỐNG public center is not logical")
    require(down_floor, "box=_frame_box_to_logical(",
            "XUỐNG public box is not logical")
    require(pass_nav, "self.vision.driver.click(*match.center)",
            "XUỐNG navigation no longer clicks detector center")

    _scan_direct_matchers()

    print("AUTO MULTI DEV ADAPTIVE RESOLUTION CONTRACT VERIFIED")
    print("logical_reference=1000x1000")
    print("production_target=500x500")
    print("vision=logical-zone->frame-match->logical-result")
    print("driver=logical-input->actual-client-once")
    print("client_size=500x500-stable-before-bridge")
    print("legacy_adaptive=neutralized-before-bridge")
    print("down_floor=500-scale+logical-center")
    print("production_slots=frame-scaled+logical-dedup")
    print("inventory_fingerprint=current-frame-template+logical-roi-center")
    print("builder_match=logical-zone+frame-scaled-template+logical-result")
    print("stall_scan=logical-crops+area-scaled-coin-threshold+500-accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
