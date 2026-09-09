# AUTO MULTI DEV — 500x500 CHECKPOINT

Cập nhật: 2026-09-09

Đây là checkpoint ngắn để AI khác resume migration 500x500 mà không phải dựng lại lịch sử.

## Baseline trước migration

```text
branch: develop/multi-auto-dev
base: 6a4407435a46cf063cdff760c2f48db06e426541
```

Baseline user-confirmed trước migration: Function 1, Sale/QC, Recipe/Recovery, friend-refresh và ClientJS restart 2h đang ổn. Không sửa business logic trong migration resolution.

## Contract bất biến

```text
source/business coordinates: logical 1000x1000
production actual ClientJS: 500x500
Bridge CAPTURE3 delivered to Vision: native 500x500
Vision: logical -> native frame for matching -> logical result
Bridge INPUT4: logical 1000 -> actual client exactly once
```

Không đổi Function/Recipe/Recovery/Sale/QC chỉ để đạt 500x500. Không bắt đầu cleanup repo trong migration này.

## Stage history

### Stage 0 — PLAN/AUDIT — DONE

```text
6e7b83817d246c334e660543ca912b0da2d9734a
```

Tạo `docs/AUTO_MULTI_DEV_500_RESOLUTION_PLAN.md`.

### Stage 1 — VISION CORE — DONE

```text
39020e716cc1d4165a31ea86a169f371c7861208
```

`runtime/vision.py` giữ logical 1000, đổi logical zone/template vào frame thật và đổi match center/box trở lại logical.

### Stage 2 — DIRECT ROI / CUSTOM DETECTOR — DONE

```text
469fb46ff161cc186fbc346981edebf448556b34  XUỐNG logical result
f06e53167fe319af95271ac3c285c5ab52fbb30d  production repeated-slot scaling
e922ec803b9582a85285c6693678c14cff0818ec  checkpoint stage 2
```

Đã scale XUỐNG, `o_trong`, production direct matcher và giữ de-dup distance ở logical units.

### Stage 3 — STATIC CONTRACT / BUILD GATE — DONE

```text
9e96f4ee14fe4401427edc629694aab3a7b71304
faeca8d3fb5f545912435ff241dee0d897d805a0
ed2e1596bd067a3452c1a2dfa2ec563f35369f6f
4aec26913014fb530f00f890d31d9f301905381a
```

Verifier:

```text
tools/verify_resolution_adaptive_contract.py
```

Mandatory chain:

```text
BUILD_FULL_PACKAGE.ps1
→ verify_multi_dev_asset_contract.py
→ verify_resolution_adaptive_contract.py
```

### Stage 4 — ACTUAL CLIENT 500x500 BEFORE BRIDGE — SOURCE DONE

```text
d869b8f27a5debe3e73be541eed2c0cf36b80a17
d4c75417825277ad30d7f2da723bf366aa9c8236
```

`runtime/resolution.py` khóa đúng ClientJS hiện tại ở client-area 500x500 đủ 2 giây trước Bridge, scoped riêng AUTO MULTI DEV. Legacy adaptive matcher được neutralize trong isolated worker để tránh double scaling.

### Stage 4.5 — BUILD #1 FOUND MORE RAW 1000 GEOMETRY — FIXED

Build tại `e953c1d9...` fail đúng gate với direct OpenCV chưa audit:

```text
actions/inventory.py
workflows/auto_builder/image_match.py
```

Fix:

```text
b2b1790e8d28dc3dd9aff665987abb00ba521c69  inventory fingerprint adaptive
3042bf8eeff6896a3d682afc2440a1edb2831fd6  Builder custom image adaptive
bb9ccd61dffdc68c925394d44532ddc021c3d68b  stall direct crop/color adaptive
20b16bf9763753a335b31fa84ef963061cb838d0  extend verifier
440372ac245cc7a14c4c534db785bdd0a7794080  checkpoint build #1
```

Không whitelist mù. Inventory/Builder/Stall đều được đổi thật sang logical->frame geometry.

### Stage 5 — FIRST LIVE 500 SMOKE — FAIL WITH STRONG EVIDENCE

Operator live-test sau build PASS. Window bootstrap báo đúng:

```text
AUTO MULTI DEV display • production client=500x500
• logical reference=1000x1000
• resize ổn định trước Bridge V3
```

Nhưng ngay sau Bridge, **mọi Vision trace vẫn báo**:

```text
Frame: 1000x1000
FrameScale: (1.0000,1.0000)
```

Đây là bằng chứng pipeline chưa thật sự đưa native 500 vào Vision.

Live symptom:

- sale vào quầy được;
- click kho thành phẩm lặp nhưng nhận diện `kho_thanh_pham` có lúc chỉ `0.7199` so với threshold `0.7200`;
- AUTO kết luận sai là không còn VP đúng loại;
- vào Function 1, planting không nhận ra `thu_hoach`, `next_gieo_trai`, `cay_tao` dù route đã tới mốc trồng;
- không hạ threshold hàng loạt vì nhiều template nhỏ cùng giảm score là triệu chứng pipeline/resampling, không phải từng asset độc lập.

#### Root cause xác nhận trong source

`test-candidates/auto-pro-clientjs-temp/engine_driver.py::screenshot()` nhận raw CAPTURE3 theo kích thước client thật, nhưng sau đó legacy code luôn resize ảnh trở lại `reference_size=(1000,1000)` trước khi trả OpenCV/PIL.

Do đó luồng thực tế trước fix là:

```text
ClientJS 500
→ Bridge CAPTURE3 raw 500
→ EngineDriver upscale 500 -> 1000
→ Vision thấy 1000, scale=1.0
→ template 1000 so với ảnh 500 đã phóng mềm
→ small-template score giảm / false miss
```

Input không bị cùng lỗi này: native Bridge INPUT4 nhận logical 0..1000 và tự scale theo `GetClientRect()` về actual client. Vì vậy **không đổi driver reference_size sang 500**.

### Stage 5.1 — NATIVE CAPTURE FIX + FOLLOW-UP RAW ROI AUDIT — SOURCE DONE, WAITING LIVE

Commits:

```text
a4294ca010f09dc4549b6c34868a21470366eab5  preserve native 500 CAPTURE3
908f5275f5954b718d2ad20405e6372203d2c2d8  expose native capture to VisionEngine
da960b945ef8b539b9619af0023d4c031bf97685  AUTO Main sale change ROI adaptive
eaf455ccf8d0b33ea812524c9843dfd1e0ef3aad  resale change ROI adaptive
7a92799a2f4d9dbccda439be2cce5c0a74259152  QC color-probe click centers logical
599dab8a81bd68c227692482066a160a22496ca0  planting diagnostic logical crop
ffe7cac1b7f1479630f119bac053fb23717334a1  lock native 500/static contracts
```

#### `NativeCaptureDriver`

`runtime/resolution.py` thêm adapter scoped AUTO MULTI DEV:

- gọi chính `_capture_shared_bgra()` đã được worker patch sang `CAPTUREW/WRITERMAP2`;
- yêu cầu raw native capture **đúng 500x500**;
- nếu khác 500: fail-close trước business click;
- trả NumPy/PIL native 500, **không resize về 1000**;
- các method input/app/profile khác delegate sang EngineDriver cũ;
- `reference_size` vẫn 1000 để business/input contract không đổi.

`automation.py` wrap EngineDriver ngay sau Bridge, probe một native screenshot trước khi tạo VisionEngine và ghi:

```text
AUTO MULTI DEV capture • native CAPTURE3=500x500
• VisionEngine nhận frame thật
• không upscale về 1000 trước matching
```

Sau đó Vision trace bắt buộc phải chuyển thành:

```text
Frame: 500x500
FrameScale: (0.5000,0.5000)
```

#### Follow-up direct-ROI audit

Khi Vision thật sự bắt đầu nhận frame 500, các direct frame slices từng vô tình chạy được nhờ EngineDriver upscale 1000 cũng phải sửa trước live:

- `auto_main_selling.py`: destructive sale before/after crop dùng logical `SALE_CHANGE_ZONE` -> frame;
- `selling.py`: clear-stall/resale destructive change crop tương tự;
- `stall_advertising.py`: color probe chạy frame pixels nhưng modal-X center đổi frame->logical; free-ad point giữ logical, không pre-scale rồi bị driver scale lần hai;
- `planting.py`: 27 waypoint diagnostic crop logical -> frame thay vì lấy x/y 1000 trực tiếp trên frame 500.

Business policy, threshold và tọa độ logical không đổi.

## CURRENT STAGE

```text
Stage 5.2 — BUILD [1] + LIVE SMOKE native 500
```

**Chưa được ghi `500x500 LIVE PASS`.**

### Next exact action

Operator:

```text
đóng Multi DEV + toàn bộ ClientJS
→ KVTM_DEV_CONTROL.bat
→ [1]
```

Trước khi hướng operator, AI tiếp theo phải fetch branch để lấy HEAD mới nhất.

Build adaptive gate kỳ vọng thêm:

```text
AUTO MULTI DEV ADAPTIVE RESOLUTION CONTRACT VERIFIED
logical_reference=1000x1000
production_target=500x500
bridge_capture=native-500-no-reference-upscale+size-fail-close
vision=logical-zone->native-frame-match->logical-result
driver=logical-input->actual-client-once
client_size=500x500-stable-before-bridge
legacy_adaptive=neutralized-before-bridge
qc_color_probes=frame-roi+logical-click-centers
planting_diagnostic=logical-waypoint-crops
sale_change_verify=logical-roi-on-native-frame
```

Runtime first mandatory evidence:

```text
AUTO MULTI DEV display • production client=500x500 ...
AUTO MULTI DEV capture • native CAPTURE3=500x500 ...
```

Và Vision trace đầu tiên phải là:

```text
Frame: 500x500
FrameScale: (0.5000,0.5000)
```

Nếu vẫn `Frame:1000x1000`, dừng migration và không chỉnh threshold/template.

Nếu đúng native 500, smoke theo thứ tự:

1. GameSession + exact-main;
2. mở quầy → click kho thành phẩm 2 → nhận diện VP;
3. QC đầu/giữa/cuối (non-blocking policy giữ nguyên);
4. planting Táo nhận `thu_hoach` hoặc `next_gieo_trai` + `cay_tao`;
5. Táo sấy production/repair;
6. direct Nước táo candidate/probe;
7. Vải vàng + floor1→floor3;
8. cuối vòng XUỐNG/exact-main;
9. vòng Function tiếp theo;
10. nếu thuận tiện: `full_kho` recovery và friend-refresh.

Nếu FAIL sau khi đã thấy native 500: lấy exact Vision score/zone/frame của detector đầu tiên fail rồi sửa detector/template đó có evidence. Không giảm threshold hàng loạt.

Nếu PASS: cập nhật `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`, plan/checkpoint thành `500x500 LIVE PASS`.
