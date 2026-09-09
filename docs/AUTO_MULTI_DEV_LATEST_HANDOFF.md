# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-09

Tài liệu này là mốc đọc đầu tiên cho phiên AI kế tiếp của branch `develop/multi-auto-dev`.

## Trạng thái hiện tại

- Branch runtime: `develop/multi-auto-dev`.
- Function 1 baseline: **operator đã chạy nhiều vòng và chốt PASS thực tế** trước các regression mới nhất.
- QC quầy: **operator đã chốt PASS live**.
- Hai regression mới nhất đã được sửa source nhưng cần live-test lại sau build:
  - Bông → Vải vàng: `(257,416)` chỉ lên tầng 2; runtime mới click chậu tầng 4 `(257,191)`.
  - Panel production mở sai máy/tầng: runtime mới phát `WrongProductionMachine`, đóng panel, exact-main recovery rồi quay lại đúng tầng.
- Runtime: isolated worker + Bridge V3.
- Dọn quầy: giữ ổn định, không được trộn logic Dọn quầy vào AUTO Main.
- Cấu hình Multi DEV: lưu persistent tại `%APPDATA%\KVTM Multi DEV`, không phụ thuộc thư mục `dist`.
- Cleanup/repository normalization nếu tiếp tục phải tách khỏi runtime đang PASS; không xóa source chỉ dựa trên tên `source-archive`/`test-candidates` vì builder hiện vẫn có dependency thật ở các vùng đó.

Mốc code quan trọng trước lần cập nhật tài liệu này:

`ffa9336565d00c5bf18b36ddc0c64e1246db8a2f` — `Fix speed verifier for shared fresh-frame panel scan`.

Commit này chỉ sửa verifier stale sau wrong-machine fix, không thay đổi runtime Function 1.

## Function 1 — chuỗi hiện tại

1. exact-main trước scheduler;
2. sale VP của Function + QC đầu/giữa/cuối quầy;
3. trồng/thu Táo;
4. sản xuất 9 Táo sấy;
5. lên tầng 6 xử lý Táo;
6. **goDown(4) thẳng tầng 6 → candidate tầng 2**;
7. bounded probe máy Nước táo, chỉ PASS khi thấy `nuoc_tao` trong vùng thư viện panel;
8. nếu probe miss: đóng panel → background-independent exact-main recovery → `goUp(1)x2` → tầng 2;
9. sản xuất 9 Nước táo + Sửa máy;
10. về exact-main, trồng Bông;
11. **click chậu tầng 4 `(257,191)` từ mốc tầng 1 để camera tới candidate tầng 3**; điểm `(257,416)` đã live-test và chỉ tới tầng 2;
12. production Vải vàng phải thấy đúng `vai_vang`; nếu panel hiện VP khác thì wrong-machine recovery;
13. sản xuất 9 Vải vàng + Sửa máy;
14. recovery về main;
15. PASS 3/3 và tiếp tục scheduler.

## Route Nước táo direct

Đường cũ tốn thời gian:

`floor6 → goDown(4) → floor2 → floor1 → main → floor1 → floor2`

Đường bình thường mới:

`floor6 → goDown(4) → floor2 candidate → nuoc_tao proof → production`

Các khóa an toàn:

- `goDown(4)` không tự chứng minh tầng;
- direct probe tối đa `2` burst x5, mỗi burst `3` recheck;
- miss hoặc `full_kho` trong probe đều đóng panel và fallback, không dùng làm floor proof;
- fallback dùng `go_down_one_toward_main()` + nút XUỐNG + main-boundary hiện tại;
- exact-main phải PASS trước `main_to_floor_2()`;
- warehouse-full recovery chuẩn vẫn giữ nguyên cho production thật.

## Route Bông → Vải vàng

Forensic `adb_controller.goUp` từng ghi nhận:

- mode1 = swipe goUp(1);
- mode2 = click `(257,416)`;
- mode3 = click `(257,191)`;
- mode4 = swipe goUp(4).

**Live correction 2026-09-09:** trong trạng thái Function 1 sau gieo Bông, `(257,416)` chỉ đưa camera lên tầng 2. Muốn tới máy Vải vàng tầng 3 phải click điểm chậu cao hơn ở tầng 4, dùng tọa độ recovered `(257,191)`.

Runtime hiện chạy:

`click (975,316) → click chậu tầng 4 (257,191) → wait 0.70s → wait 0.15s → fresh-frame gate → vai_vang proof`

Không được regression về `(257,416)` hoặc hai lần `goUp(1)`.

## Shared production panel contract

Táo sấy, Nước táo và Vải vàng dùng chung true x5 collection.

Thứ tự bắt buộc sau mỗi burst:

`x5 raw click → vp_collect_delay → fresh frame → panel_state(frame) → target/wrong-machine scan`

Ràng buộc:

- không sleep/capture/check giữa 5 raw click;
- cùng fresh frame sau settle được dùng cho `full_kho`, target VP và wrong-machine VP;
- panel đúng chỉ PASS khi thấy target VP trong `PRODUCT_SEARCH_ZONE`;
- `o_trong` chỉ diagnostic, không chứng minh đúng máy;
- product-image miss tạm thời sau khi đúng panel đã được xác minh vẫn là non-blocking recheck.

Known production anchors hiện gồm:

- `tao_say`;
- `nuoc_tao`;
- `vai_vang`.

## Wrong-machine recovery

Lỗi live đã gặp: panel production đã mở ở **sai tầng**, ví dụ đang cần Vải vàng nhưng panel hiện Nước táo. Logic cũ chỉ thấy `vai_vang` chưa xuất hiện nên tiếp tục burst x5 vô hạn.

Runtime mới:

1. sau mỗi burst x5 + settle, lấy fresh frame;
2. nếu target VP đúng → tiếp tục transaction bình thường;
3. nếu thấy VP production khác trong `tao_say / nuoc_tao / vai_vang` → đóng panel ngay;
4. phát `WrongProductionMachine`;
5. không tin tầng dự kiến hiện tại;
6. invalidate exact-main proof cũ;
7. dùng unknown-floor recovery `goDown(1)` + nút XUỐNG + main-boundary để chứng minh exact-main;
8. từ exact-main đi lại đúng tầng sản xuất yêu cầu;
9. retry đúng production call; lần retry vẫn phải xác minh target VP;
10. wrong-machine recovery tối đa `3` lần để không lặp vô hạn.

Ví dụ Vải vàng mở nhầm Nước táo:

`vai_vang expected → nuoc_tao detected → close panel → exact-main → main→floor1 → click floor4 pot (257,191) → floor3 candidate → vai_vang proof → production`

Wrong-machine recovery **không chạy sale**. `InventoryFull` vẫn là business recovery riêng: exact-main → sale Function VP → quay lại đúng tầng → retry production.

## Exact-main / recovery đa background

Không được dùng background/quầy nhà làm gate exact-main vì mỗi account có background khác nhau.

Hợp đồng hiện tại:

- own farm: fixed HUD (`friend_off` / tín hiệu HUD ổn định);
- exact-main: bằng chứng điều hướng runtime;
- camera không rõ tầng: goDown có kiểm soát;
- hai nhịp goDown liên tiếp có `frame_change <= 6.0` là fallback biên dưới;
- tầng trên có UI `XUỐNG`: sau `goDown(1)` phải **nhận diện nút XUỐNG ở mép dưới rồi click đúng tâm match**, không click mù `(497,978)`;
- recovery chain hỗ trợ tối đa 10 tầng;
- tầng 1 không có nút XUỐNG là trạng thái bình thường.

Build contract phải giữ:

- background world anchor không được quay lại làm runtime exact-main gate;
- blind fixed-coordinate down-floor click bị cấm.

## AUTO bán VP + quảng cáo quầy — LIVE PASS

Mỗi lượt bán VP có ba checkpoint quảng cáo phân bố đầu/giữa/cuối quầy, xấp xỉ physical slot `1 / 10 / 20`.

Tại mỗi checkpoint:

1. tìm listing còn tồn tại;
2. nếu listing đã có dấu QC đỏ thì **không click**;
3. nếu chưa QC thì click listing để mở popup;
4. nếu nút xanh `Đặt quảng cáo` đã hồi thì click đúng nút miễn phí;
5. tuyệt đối không click nút quảng cáo trả phí/kim cương;
6. nếu còn cooldown thì đóng popup bằng X và tiếp tục bán;
7. lỗi nhận diện QC là non-blocking, không được phá sale đã PASS.

Trường hợp quầy full/no empty slot vẫn phải tiếp tục đi hết ba checkpoint quảng cáo và thu vàng.

Contract build riêng:

`tools/verify_auto_vp_advertising_contract.py`

Kỳ vọng log build:

`AUTO MULTI DEV VP ADVERTISING CONTRACT VERIFIED`

## Persistent settings

Nguồn persistent:

`%APPDATA%\KVTM Multi DEV`

Các file quan trọng:

- `profiles.json`;
- `settings.json`;
- `clear-stall-history.jsonl`.

Migration từ package-local `data-dev` chỉ chạy một lần khi persistent file chưa tồn tại và **không overwrite** dữ liệu đã có.

Các speed key độc lập:

- `floor_swipe_duration`;
- `plant_harvest_duration`;
- `vp_collect_delay`;
- `vp_production_delay`;
- `crop_check_interval`.

Saved operator values trong APPDATA là authoritative.

## Speed verifier stale fix — `ffa93365`

Sau khi shared production đổi sang một fresh frame cho cả target/wrong-machine scan, `verify_auto_speed_config_contract.py` cũ vẫn yêu cầu literal:

`warehouse_full, empty_ready = self._panel_state()`

Runtime mới đúng là:

`frame = self.vision.frame()`

`warehouse_full, empty_ready = self._panel_state(frame=frame)`

Vì vậy build ở HEAD `5478129` fail tại speed contract dù runtime logic đúng.

Commit:

`ffa9336565d00c5bf18b36ddc0c64e1246db8a2f`

đã cập nhật verifier để khóa thứ tự:

`x5 → settle → fresh frame → panel check`

và bắt buộc `_find_wrong_product_match()` tồn tại trong shared collect path.

Sau fix, speed gate phải PASS với:

`AUTO MULTI DEV SPEED CONFIG STATIC CONTRACT VERIFIED`

Lần sửa này không đổi Function 1 runtime.

## Fix build khi `dist\...\Multi` bị lock

Lỗi đã gặp trên Windows:

`Remove-Item ... dist\KVTM-ClientJS-Suite-Multi-DEV\Multi ... because it is being used by another process`

Builder hiện có hai lớp bảo vệ:

1. process ownership release trước build — chỉ đóng process thuộc đúng package output;
2. bounded output cleanup retry — tối đa 20 lần, cách 350 ms.

Không cần operator tự Task Manager kill toàn bộ Python nếu process thuộc package cũ.

## Build flow chuẩn

Operator dùng:

`KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`

Không sửa `dist` thủ công.

Các gate quan trọng phải PASS gồm:

- persistent settings contract;
- main-boundary contract;
- VP advertising contract;
- clear-stall contract;
- AUTO Builder contract;
- AUTO Main sale contract;
- planting contract;
- speed contract;
- floor navigation contract;
- Bridge V3 contract;
- production contract;
- asset contract.

Production contract phải in:

- `apple_to_juice=direct-goDown4+bounded-nuoc_tao-proof+exact-main-fallback`
- `wrong_machine=WrongProductionMachine->unknown-floor-exact-main->requested-floor-retry`
- `cotton_to_fabric=floor4-pot-anchor-at-257,191+vai_vang-proof`

Speed contract phải bảo vệ:

- true x5 không inter-click wait/check;
- post-burst `vp_collect_delay`;
- fresh-frame panel scan;
- wrong-machine scan sau settle.

Sau `[1]` PASS mới mở/chạy runtime mới.

## Không được regression

- Không popup lỗi blocking cho AUTO Multi DEV.
- Không retry mù destructive transaction nhiều lần; runtime error phải recover main rồi restart pipeline.
- Không dùng background account làm exact-main gate.
- Không click mù nút xuống tầng.
- Không coi `o_trong` là bằng chứng panel production đúng máy.
- Không xóa persistent settings khi rebuild/update.
- Không click quảng cáo trả phí.
- Không click ô đang có QC khi kiểm tra quảng cáo.
- Không dừng advertisement traversal chỉ vì quầy full hoặc kho hết VP.
- Không quay lại đường vòng `floor6 → main → floor2` khi direct `nuoc_tao` proof đã PASS.
- Không coi goDown(4) tự chứng minh tầng 2.
- Không để direct floor probe click vô hạn khi lệch tầng.
- Không dùng `(257,416)` hoặc hai goUp(1) cho route Bông → tầng 3; phải click chậu tầng 4 `(257,191)`.
- Không để panel production sai máy mở rồi tiếp tục click x5 vô hạn; phải đóng panel và exact-main recovery.
- Không quét target/wrong-machine trên các frame khác nhau sau cùng một burst nếu có thể dùng một fresh frame chung.
- Không đụng luồng Dọn quầy ổn định khi sửa AUTO Main.

## Read-first cho phiên AI kế tiếp

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_MULTI_DEV_FUNCTION_ONE.md`
5. `components/clientjs-auto/kvtm_automation/workflows/auto_function_one/workflow.py`
6. `components/clientjs-auto/kvtm_automation/actions/production.py`
7. `components/clientjs-auto/kvtm_automation/workflows/production_warehouse_recovery.py`
8. `components/clientjs-auto/kvtm_automation/actions/function_one_pass_three_navigation.py`
9. `components/clientjs-auto/kvtm_automation/actions/apple_juice_production.py`
10. `tools/verify_auto_main_production_contract.py`
11. `tools/verify_auto_speed_config_contract.py`
12. `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`
