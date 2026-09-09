from __future__ import annotations

"""Static contract for non-blocking free advertisement during AUTO VP sale."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADVERTISING = ROOT / "components/clientjs-auto/kvtm_automation/actions/stall_advertising.py"
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/workflow.py"
STALL = ROOT / "components/clientjs-auto/kvtm_automation/actions/stall.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing AUTO VP advertising contract file: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    advertising = read(ADVERTISING)
    workflow = read(WORKFLOW)
    stall = read(STALL)

    require(advertising, "FILE_FUNCTIONS", "Advertising action function manifest missing")
    require(advertising, "class StallAdvertisingActions", "Advertising action class missing")
    require(advertising, "AD_MARKER_RED_RATIO = 0.035", "Already-advertised marker threshold changed")
    require(advertising, "READY_GREEN_RATIO = 0.30", "Free-ad ready threshold changed")
    require(advertising, "READY_BUTTON_ZONE = (440, 685, 120, 28)", "Free-ad safe click zone changed")
    require(advertising, "READY_BUTTON_POINT = (500, 699)", "Free-ad click point changed")
    require(advertising, "MODAL_CLOSE_ZONE = (585, 280, 45, 45)", "Listing modal X zone changed")
    require(advertising, "MODAL_CLOSE_RED_RATIO = 0.08", "Listing modal X threshold changed")
    require(advertising, "def _slot_has_ad_marker", "Existing-QC marker detector missing")
    require(advertising, "if has_ad:", "Existing-QC skip branch missing")
    require(advertising, "KHÔNG click kiểm tra", "Existing-QC no-click policy marker missing")
    require(advertising, "def _free_ad_ready_center", "Free-ad readiness detector missing")
    require(advertising, "if ready_center is None:", "Cooldown branch missing")
    require(advertising, "self._close_listing_modal()", "Cooldown/modal cleanup missing")
    require(advertising, "self.vision.driver.click(*ready_center)", "Free-ad READY click missing")
    require(advertising, "ACTIVATED_UNVERIFIED", "One-shot nonblocking postcheck missing")
    require(advertising, "không retry click", "Ad activation must not double-click on uncertain render")
    require(advertising, "_checked_physical_slots", "Overlapping-view duplicate-check guard missing")
    require(advertising, "self.stall.listing_is_available(frame, local_slot)", "Advertising candidate is not gated by active listing")
    require(advertising, "self.stall.physical_slot(view, local_slot)", "Advertising does not track physical stall slots")

    # Marker check must happen before opening/clicking a listing.
    if advertising.index("if has_ad:") > advertising.index("self.vision.driver.click(*click_point)"):
        raise AssertionError("Advertising clicks a listing before checking existing QC marker")

    # Paid diamond advertisement is never a legal runtime target. The only ad
    # activation click must be the visually proven green free-ad center.
    forbid(advertising, "driver.click(625, 627)", "Paid diamond advertisement click introduced")
    forbid(advertising, "driver.click(624, 627)", "Paid diamond advertisement click introduced")
    require(advertising, "paid orange diamond button", "Paid-ad exclusion policy marker missing")

    require(stall, "VISIBLE_SLOT_CENTERS", "Stable own-stall slot geometry missing")
    require(stall, "def listing_is_available", "Listing availability guard missing")

    require(workflow, "from ...actions.stall_advertising import StallAdvertisingActions", "Advertising action not wired into sale workflow")
    require(workflow, '1: ("đầu", 1)', "Beginning QC checkpoint changed")
    require(workflow, '2: ("giữa", 10)', "Middle QC checkpoint changed")
    require(workflow, '4: ("cuối", 20)', "End QC checkpoint changed")
    require(workflow, "self._check_advertisement_checkpoint(view)", "Per-view QC checkpoint call missing")
    require(workflow, "except AutomationStopped:", "Stop signal must not be swallowed by optional QC")
    require(workflow, "lỗi non-blocking", "Optional QC failure must remain non-blocking")
    require(workflow, "if not depleted:", "Depleted inventory must stop only listing, not stall traversal")
    forbid(workflow, "if depleted:\n                    break", "Inventory depletion still aborts middle/end QC checks")

    advert_call = workflow.index("self._check_advertisement_checkpoint(view)")
    gold_call = workflow.index("collected += self.auto.stall.collect_own_stall_gold")
    sale_call = workflow.index("attempt = self.sale.sell_next_allowed")
    if not advert_call < gold_call < sale_call:
        raise AssertionError("Sale view order must be QC -> collect gold -> list VP")

    print("AUTO MULTI DEV VP ADVERTISING CONTRACT VERIFIED")
    print("checkpoints=physical-slot-1,10,20")
    print("existing_ad=skip-without-click")
    print("cooldown=close-x-and-continue")
    print("ready=green-free-button-only")
    print("paid_diamond=never-click")
    print("full_stall=advertising-checks-still-run")
    print("ad_failure=non-blocking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
