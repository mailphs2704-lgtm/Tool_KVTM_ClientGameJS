from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "components/clientjs-auto/assets/items"
ASSET_LIBRARY = ROOT / "components/clientjs-auto/kvtm_automation/runtime/assets.py"
REQUIRED_ASSETS = (
    "add_friend",
    "cay_tao",
    "cua_hang",
    "dat_ban",
    "dong_y",
    "friend",
    "friend_off",
    "full_kho",
    "icon_game",
    "icon_home",
    "kho_event",
    "kho_khoang_san",
    "kho_nong_san",
    "kho_tao_say",
    "kho_thanh_pham",
    "kho_tinh_dau_hh",
    "kho_vai_vang",
    "kho_vat_dung",
    "list_friend",
    "lv_up",
    "next_gieo_trai",
    "o_trong",
    "quay_hang",
    "quay_hang_friend",
    "quay_hang_on",
    "quay_trong",
    "sl10",
    "tai_khoan",
    "tai_khoan_on",
    "tao_say",
    "thu_hoach",
    "tinh_dau_hh",
    "vai_vang",
    "vang",
    "x",
    "x_popup_event",
)


def main() -> int:
    library = ASSET_LIBRARY.read_text(encoding="utf-8")
    ast.parse(library, filename=str(ASSET_LIBRARY))
    if 'auto_root / "assets"' in library:
        raise AssertionError("Multi Dev AssetLibrary still falls back to AUTO PRO")
    missing = [
        name for name in REQUIRED_ASSETS
        if not any((ASSET_ROOT / f"{name}{suffix}").is_file()
                   for suffix in (".png", ".jpg", ".jpeg", ".bmp", ".webp"))
    ]
    if missing:
        raise AssertionError("Missing Multi Dev assets: " + ", ".join(missing))
    print("AUTO MULTI DEV SELF-CONTAINED ASSET CONTRACT VERIFIED")
    print(f"asset_count={len(REQUIRED_ASSETS)}")
    print("auto_pro_asset_fallback=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
