# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-09

Tài liệu này là mốc đọc đầu tiên cho phiên AI kế tiếp của branch `develop/multi-auto-dev`.

## Trạng thái hiện tại

- Branch runtime: `develop/multi-auto-dev`.
- Function 1: **operator đã chạy nhiều vòng và chốt PASS thực tế**. Nếu phát sinh regression mới thì xử lý như lỗi riêng, không mở lại toàn bộ Function 1 theo mặc định.
- Runtime: isolated worker + Bridge V3.
- Dọn quầy: giữ ổn định, không được trộn logic Dọn quầy vào AUTO Main.
- Cấu hình Multi DEV: lưu persistent tại `%APPDATA%\KVTM Multi DEV`, không phụ thuộc thư mục `dist`.
- Cleanup/repository normalization nếu tiếp tục phải tách khỏi runtime đang PASS; không xóa source chỉ dựa trên tên `source-archive`/`test-candidates` vì builder hiện vẫn có dependency thật ở các vùng đó.

## Function 1 đã PASS + route tối ưu mới

Chuỗi Function 1 hiện gồm:

1. exact-main trước scheduler;
2. sale VP của Function;
3. trồng/thu Táo;
4. sản xuất 9 Táo sấy;
5. lên tầng 6 xử lý Táo;
6. **goDown(4) thẳng tầng 6 → candidate tầng 2**;
7. bounded probe máy Nước táo, chỉ PASS khi thấy `nuoc_tao` trong vùng thư viện panel;
8. nếu probe miss: đóng panel → background-independent exact-main recovery → `goUp(1)x2` → tầng 2;
9. sản xuất 9 Nước táo;
10. về main, trồng Bông;
11. **click chậu tầng 4 `(257,191)` từ mốc tầng 1 để camera tới tầng 3**; điểm cũ `(257,416)` đã live-test và chỉ tới tầng 2;
12. sản xuất 9 Vải vàng;
13. recovery về main;
14. PASS 3/3 và tiếp tục scheduler.

Các VP sản xuất dùng true x5 click burst để thu thành phẩm. Panel đúng chỉ được chấp nhận khi **ảnh sản phẩm yêu cầu** xuất hiện trong vùng thư viện panel. `o_trong` chỉ là diagnostic. Nếu panel mở nhưng hiện một VP production khác (`tao_say` / `nuoc_tao` / `vai_vang`) thì runtime đóng panel ngay và recovery về exact-main thay vì tiếp tục click x5.

### Route Nước táo direct

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

### Route Bông → Vải vàng

Forensic `adb_controller.goUp` từng ghi nhận:

- mode1 = swipe goUp(1);
- mode2 = click `(257,416)`;
- mode3 = click `(257,191)`;
- mode4 = swipe goUp(4).

**Live correction 2026-09-09:** trong trạng thái Function 1 sau gieo Bông, `(257,416)` chỉ đưa camera lên tầng 2. Muốn tới máy Vải vàng tầng 3 phải click điểm chậu cao hơn ở tầng 4, dùng tọa độ recovered `(257,191)`.

Runtime hiện chạy:

`click (975,316) → click chậu tầng 4 (257,191) → wait 0.70s → wait 0.15s → fresh-frame gate → vai_vang proof`

Không được regression về `(257,416)` hoặc hai lần `goUp(1)`.

### Wrong-machine recovery

Lỗi đã live gặp: panel production đã mở ở **sai tầng**, ví dụ đang cần Vải vàng nhưng panel hiện Nước táo. Logic cũ chỉ thấy target `vai_vang` chưa xuất hiện nên tiếp tục burst x5 vô hạn.

Runtime mới:

1. sau mỗi burst x5, quét target VP trong `PRODUCT_SEARCH_ZONE`;
2. nếu target đúng → tiếp tục transaction bình thường;
3. nếu thấy VP production khác trong `tao_say / nuoc_tao / vai_vang` → đóng panel ngay;
4. phát `WrongProductionMachine`;
5. không tin tầng dự kiến, dùng unknown-floor recovery `goDown(1)` + nút XUỐNG + main-boundary để chứng minh exact-main;
6. từ exact-main đi lại đúng tầng sản xuất yêu cầu;
7. retry đúng production call; lần retry vẫn phải xác minh target VP;
8. wrong-machine recovery tối đa `3` lần để không lặp vô hạn.

Ví dụ Vải vàng mở nhầm Nước táo:

`vai_vang expected → nuoc_tao detected → close panel → exact-main → main→floor1 → click floor4 pot (257,191) → floor3 candidate → vai_vang proof → production`

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

## AUTO bán VP + quảng cáo quầy

Mỗi lượt bán VP có thêm ba checkpoint quảng cáo phân bố đầu/giữa/cuối quầy, xấp xỉ physical slot `1 / 10 / 20`.

Tại mỗi checkpoint:

1. tìm listing còn tồn tại;
2. nếu listing đã có dấu QC đỏ thì **không click**;
3. nếu chưa QC thì click listing để mở popup;
4. nếu nút xanh `Đặt quảng cáo` đã hồi thì click đúng nút miễn phí;
5. tuyệt đối không click nút quảng cáo trả phí/kim cương;
6. nếu còn cooldown thì đóng popup bằng X và tiếp tục bán;
7. lỗi nhận diện QC là non-blocking, không được phá sale đã PASS.

Trường hợp quầy full/no empty slot vẫn phải tiếp tục đi hết ba checkpoint quảng cáo và thu vàng. Mục tiêu là tránh quầy đầy nhưng không có listing được quảng cáo nên không lên bảng tin.

Contract build riêng:

`tools/verify_auto_vp_advertising_contract.py`

Kỳ vọng log build:

`AUTO MULTI DEV VP ADVERTISING CONTRACT VERIFIED`

## Persistent settings

Multi DEV không lưu settings chính trong `dist` nữa.

Nguồn persistent:

`%APPDATA%\KVTM Multi DEV`

Các file quan trọng:

- `profiles.json`;
- `settings.json`;
- `clear-stall-history.jsonl`.

Migration từ package-local `data-dev` chỉ chạy một lần khi persistent file chưa tồn tại và **không overwrite** dữ liệu đã có.

Baseline speed được source khóa:

- floor swipe: `0.350`;
- plant/harvest: `0.035`;
- VP production: `0.070`;
- crop check: `0.100`.

Dọn quầy có baseline self-heal nhưng setting profile đã lưu luôn được ưu tiên.

## Fix build khi `dist\...\Multi` bị lock

Lỗi đã gặp trên Windows:

`Remove-Item ... dist\KVTM-ClientJS-Suite-Multi-DEV\Multi ... because it is being used by another process`

Root cause chính: visible Multi có thể đã đóng nhưng hidden `python/pythonw` resident host hoặc worker cũ vẫn thuộc package output và giữ handle/cwd trong `dist\...\Multi`. Builder cũ chỉ đóng một số `GameClientJS`, chưa release toàn bộ packaged runtime trước khi xóa output.

`packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1` hiện có hai lớp bảo vệ:

1. **process ownership release trước build**
   - chỉ chọn process có `CommandLine` hoặc `ExecutablePath` nằm dưới đúng `$OutputRoot`;
   - thêm descendants của các process đó;
   - không kill Python/ClientJS ngoài project;
   - force-stop packaged runtime cũ và chờ handle release;
2. **bounded output cleanup retry**
   - runtime copy thay one-shot `Remove-Item` bằng tối đa 20 lần retry;
   - mỗi lần cách 350 ms;
   - nếu vẫn fail mới báo rõ external lock/Explorer/antivirus.

Kỳ vọng đầu build sau fix:

- `[DEV] Giai phong ... process runtime cu truoc build...` nếu còn process cũ;
- `[DEV] Packaged runtime handles: RELEASED`;
- `AUTO MULTI DEV old-runtime release: READY`;
- `AUTO MULTI DEV output cleanup retry: READY`;
- `[DEV] Old package output removed after attempt N/20.`

Không cần operator tự Task Manager kill toàn bộ Python nếu process thuộc package cũ; `[1]` phải tự xử lý.

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

Production contract hiện phải in thêm:

- `apple_to_juice=direct-goDown4+bounded-nuoc_tao-proof+exact-main-fallback`
- `wrong_machine=WrongProductionMachine->unknown-floor-exact-main->requested-floor-retry`
- `cotton_to_fabric=floor4-pot-anchor-at-257,191+vai_vang-proof`

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
10. `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`
