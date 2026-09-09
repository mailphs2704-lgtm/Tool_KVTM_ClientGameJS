# AUTO MULTI DEV — 500x500 CHECKPOINT

Cập nhật: 2026-09-09

Đây là checkpoint ngắn để AI khác resume migration 500x500 mà không phải dựng lại lịch sử.

## Baseline trước migration

```text
branch: develop/multi-auto-dev
base: 6a4407435a46cf063cdff760c2f48db06e426541
```

Baseline user-confirmed/current trước migration: Function 1, Sale/QC, Recipe/Recovery, friend-refresh và ClientJS restart 2h đang ổn. Không sửa business logic trong migration resolution.

## Stage history

### Stage 0 — PLAN/AUDIT — DONE

```text
6e7b83817d246c334e660543ca912b0da2d9734a
```

Tạo `docs/AUTO_MULTI_DEV_500_RESOLUTION_PLAN.md`.

Audit ban đầu xác định:

- input driver đã dùng logical 1000x1000 và scale sang client thật;
- blocker chính là VisionEngine dùng logical zone như frame pixel;
- direct ROI/custom detector cần audit riêng.

**Bổ sung sau audit:** worker thực tế có gọi `adaptive_cv.install_adaptive_matching()` sau shared image bootstrap. Vì VisionEngine mới tự scale explicit, Stage 4 đã thêm neutralizer trước Bridge để tránh double-scale. Không xóa legacy call ở worker vì Bridge/static contract cũ vẫn khóa bootstrap đó; isolated AUTO neutralize nó trước khi vision chạy.

### Stage 1 — VISION CORE — DONE

```text
39020e716cc1d4165a31ea86a169f371c7861208
```

File:

```text
components/clientjs-auto/kvtm_automation/runtime/vision.py
```

Đã làm:

- logical reference 1000x1000;
- logical zone -> frame ROI;
- logical point -> frame;
- frame point/box -> logical;
- template 1000-reference -> actual frame scale;
- `Match.center`/`Match.box` public luôn logical;
- `click=True` giao logical center cho driver nên không double-scale;
- log có logical zone + frame ROI + frame scale.

### Stage 2 — DIRECT ROI / CUSTOM DETECTOR — DONE

```text
469fb46ff161cc186fbc346981edebf448556b34  XUỐNG logical result
f06e53167fe319af95271ac3c285c5ab52fbb30d  production repeated-slot scaling
e922ec803b9582a85285c6693678c14cff0818ec  checkpoint stage 2
```

Đã làm:

- XUỐNG match ở frame thật, 500 dùng scale 0.50, return center/box logical;
- caller `driver.click(*match.center)` scale đúng một lần;
- production `_count_matches()` dùng logical ROI -> frame ROI;
- `o_trong` template resize theo frame scale;
- slot centers đổi về logical trước de-dup;
- `MIN_DISTANCE=34` vẫn là logical units;
- `full_kho`, product anchors, material-error dùng `VisionEngine.find()` nên hưởng Stage 1.

### Stage 3 — STATIC CONTRACT / BUILD GATE — DONE

```text
9e96f4ee14fe4401427edc629694aab3a7b71304  add resolution verifier
faeca8d3fb5f545912435ff241dee0d897d805a0  wire through mandatory asset gate
ed2e1596bd067a3452c1a2dfa2ec563f35369f6f lock 500 before Bridge
4aec26913014fb530f00f890d31d9f301905381a fix direct matcher scan
```

New verifier:

```text
tools/verify_resolution_adaptive_contract.py
```

Mandatory build chain:

```text
BUILD_FULL_PACKAGE.ps1
→ verify_multi_dev_asset_contract.py
→ verify_resolution_adaptive_contract.py
```

PS5.1 wrapper invokes the same authoritative builder, nên cũng nhận gate này.

Expected marker:

```text
AUTO MULTI DEV ADAPTIVE RESOLUTION CONTRACT VERIFIED
logical_reference=1000x1000
production_target=500x500
vision=logical-zone->frame-match->logical-result
driver=logical-input->actual-client-once
client_size=500x500-stable-before-bridge
legacy_adaptive=neutralized-before-bridge
down_floor=500-scale+logical-center
production_slots=frame-scaled+logical-dedup
```

### Stage 4 — ACTUAL CLIENT 500x500 BEFORE BRIDGE — SOURCE DONE

```text
d869b8f27a5debe3e73be541eed2c0cf36b80a17  runtime resolution normalizer
d4c75417825277ad30d7f2da723bf366aa9c8236  normalize AUTO client before Bridge
```

New file:

```text
components/clientjs-auto/kvtm_automation/runtime/resolution.py
```

Contract:

```text
LOGICAL_REFERENCE_SIZE = (1000,1000)
PRODUCTION_CLIENT_SIZE = (500,500)
```

`KVAutomation` chỉ áp 500 khi `context.work_dir` thuộc `auto-multi-dev`; các workflow/diagnostic khác dùng KVAutomation không bị đổi size theo migration này.

Trước `ClientJSDriverFactory.engine()`:

1. neutralize legacy global adaptive matcher;
2. tìm đúng HWND của `context.pid`;
3. resize **client area** đúng 500x500, không đổi desktop position;
4. giữ/recheck 500 ổn định 2 giây;
5. nếu delayed display callback của Multi đổi lại size, resize lại 500;
6. chỉ khi stable mới tạo Bridge V3 và VisionEngine.

Điểm này cũng tự áp cho periodic ClientJS restart vì worker mới của profile restart đi lại cùng `KVAutomation` bootstrap.

## CURRENT STAGE

```text
Stage 5 — BUILD [1] + LIVE SMOKE 500x500
```

Chưa được ghi `500x500 LIVE PASS` trước khi operator test.

### Next exact action

Operator:

```text
đóng Multi DEV + ClientJS
→ KVTM_DEV_CONTROL.bat
→ [1]
```

Đầu build phải dùng HEAD mới nhất (đọc branch trước khi yêu cầu operator).

Static build phải thấy marker adaptive resolution ở trên.

Sau Start AUTO, trước log Bridge V3 phải thấy:

```text
AUTO MULTI DEV display • production client=500x500 • logical reference=1000x1000 • resize ổn định trước Bridge V3
```

Sau đó smoke theo thứ tự:

1. GameSession + exact-main;
2. sale VP + QC;
3. Function 1 Táo sấy;
4. direct Nước táo candidate/probe;
5. Vải vàng + route floor1→floor3;
6. cuối vòng XUỐNG/exact-main;
7. vòng Function kế tiếp;
8. nếu thuận tiện tạo kho đầy: `full_kho` -> sale recovery -> same floor;
9. friend refresh nếu toggle bật.

Nếu FAIL: lấy đoạn log từ `AUTO MULTI DEV display` tới lỗi đầu tiên; sửa đúng detector/template/zone có evidence, không thay business logic hàng loạt.

Nếu PASS: cập nhật `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md` + plan/checkpoint thành `500x500 LIVE PASS`.

## Contract bất biến

```text
source coordinate: logical 1000x1000
production actual client: 500x500
Vision: logical -> frame for matching -> logical result
Driver: logical -> actual input, đúng 1 lần
```

Không đổi Function/Recipe/Recovery/Sale/QC chỉ để đạt 500x500. Không bắt đầu cleanup repo trong migration này.
